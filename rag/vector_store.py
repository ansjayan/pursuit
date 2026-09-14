




# rag/vector_store.py

import hashlib
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_PATH = Path("data/chroma")

COLLECTION_NAME = "pursuit_profile_chunks"


# ============================================================
# CLIENT / COLLECTION
# ============================================================

def get_client():
    """
    Return the persistent PURSUIT ChromaDB client.
    """

    CHROMA_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    return chromadb.PersistentClient(
        path=str(CHROMA_PATH),
        settings=Settings(
            anonymized_telemetry=False,
        ),
    )


def get_collection():
    """
    Return the main PURSUIT RAG collection.

    ChromaDB's default embedding function is used.
    """

    client = get_client()

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description":
                "PURSUIT user profile evidence chunks"
        },
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    text: Optional[str],
) -> str:
    """
    Normalize whitespace for chunking and hashing.
    """

    if not text:
        return ""

    return " ".join(
        str(text).split()
    ).strip()


# ============================================================
# CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 900,
    overlap: int = 150,
) -> List[str]:
    """
    Split text into overlapping character chunks.

    The chunker is intentionally deterministic so the same
    document always generates the same chunk boundaries.
    """

    text = normalize_text(
        text
    )

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap must be smaller than chunk_size."
        )

    chunks = []

    start = 0

    while start < len(text):

        end = min(
            start + chunk_size,
            len(text),
        )

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        if end >= len(text):
            break

        start = (
            end - overlap
        )

    return chunks


# ============================================================
# HASH HELPERS
# ============================================================

def text_hash(
    text: str,
) -> str:
    """
    Stable SHA-256 hash of normalized text.
    """

    normalized = normalize_text(
        text
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# CHUNK IDS
# ============================================================

def build_chunk_id(
    user_id: int,
    document_id: int,
    chunk_index: int,
    chunk: str,
) -> str:
    """
    Stable chunk ID.

    Includes:
    - user
    - document
    - chunk position
    - content hash

    This prevents duplicate vectors and also makes replacement
    behavior deterministic.
    """

    short_hash = text_hash(
        chunk
    )[:16]

    return (
        f"user_{int(user_id)}"
        f"_doc_{int(document_id)}"
        f"_chunk_{int(chunk_index)}"
        f"_{short_hash}"
    )


# ============================================================
# ADD DOCUMENT CHUNKS
# ============================================================

def add_document_chunks(
    user_id: int,
    document_id: int,
    filename: str,
    text: str,
    file_type: str = "",
    source_label: str = "",
    chunk_size: int = 900,
    overlap: int = 150,
):
    """
    Add one SQLite document's chunks to ChromaDB.

    Returns a list of Chroma chunk IDs.

    SQLite remains the source of truth for documents.
    ChromaDB stores only semantic retrieval chunks.
    """

    chunks = chunk_text(
        text=text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    if not chunks:
        return []

    collection = get_collection()

    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(
        chunks
    ):

        chunk_id = build_chunk_id(
            user_id=user_id,
            document_id=document_id,
            chunk_index=index,
            chunk=chunk,
        )

        ids.append(
            chunk_id
        )

        documents.append(
            chunk
        )

        metadatas.append({
            "user_id":
                int(user_id),

            "document_id":
                int(document_id),

            "filename":
                str(filename or ""),

            "file_type":
                str(file_type or ""),

            "source_label":
                str(source_label or ""),

            "chunk_index":
                int(index),

            "chunk_hash":
                text_hash(
                    chunk
                ),
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return ids


# ============================================================
# EMPTY RESULT
# ============================================================

def empty_query_result():
    """
    Return the same basic shape as Chroma query().
    """

    return {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }


# ============================================================
# SEARCH
# ============================================================

def search_chunks(
    user_id: int,
    query: str,
    n_results: int = 5,
    file_type: Optional[str] = None,
):
    """
    Semantic search over one user's RAG evidence.

    User isolation is always enforced.

    Optional file_type can restrict retrieval to categories
    such as Resume, Certification, Projects, Education, etc.
    """

    query = normalize_text(
        query
    )

    if not query:
        return empty_query_result()

    collection = get_collection()

    if collection.count() == 0:
        return empty_query_result()

    where_filter = {
        "user_id":
            int(user_id)
    }

    if file_type:

        where_filter = {
            "$and": [
                {
                    "user_id":
                        int(user_id)
                },
                {
                    "file_type":
                        str(file_type)
                },
            ]
        }

    requested = max(
        1,
        int(n_results),
    )

    # Determine matching chunk count first so Chroma is never
    # asked for more results than exist for this user's filter.
    matching = collection.get(
        where=where_filter,
        include=[],
    )

    matching_ids = (
        matching.get(
            "ids",
            []
        )
        or []
    )

    matching_count = len(
        matching_ids
    )

    if matching_count == 0:
        return empty_query_result()

    safe_count = min(
        requested,
        matching_count,
    )

    return collection.query(
        query_texts=[
            query
        ],
        n_results=safe_count,
        where=where_filter,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )


# ============================================================
# NORMALIZED EVIDENCE SEARCH
# ============================================================

def search_evidence(
    user_id: int,
    query: str,
    n_results: int = 5,
    file_type: Optional[str] = None,
):
    """
    Preferred retrieval API for agents.

    Converts raw Chroma results into easy-to-use evidence
    dictionaries.
    """

    raw = search_chunks(
        user_id=user_id,
        query=query,
        n_results=n_results,
        file_type=file_type,
    )

    ids = (
        raw.get(
            "ids",
            [[]],
        )[0]
        or []
    )

    documents = (
        raw.get(
            "documents",
            [[]],
        )[0]
        or []
    )

    metadatas = (
        raw.get(
            "metadatas",
            [[]],
        )[0]
        or []
    )

    distances = (
        raw.get(
            "distances",
            [[]],
        )[0]
        or []
    )

    evidence = []

    for index, chunk_id in enumerate(
        ids
    ):

        text = (
            documents[index]
            if index < len(documents)
            else ""
        )

        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        evidence.append({
            "chunk_id":
                chunk_id,

            "text":
                text,

            "distance":
                distance,

            "user_id":
                metadata.get(
                    "user_id"
                ),

            "document_id":
                metadata.get(
                    "document_id"
                ),

            "filename":
                metadata.get(
                    "filename",
                    "",
                ),

            "file_type":
                metadata.get(
                    "file_type",
                    "",
                ),

            "source_label":
                metadata.get(
                    "source_label",
                    "",
                ),

            "chunk_index":
                metadata.get(
                    "chunk_index"
                ),

            "chunk_hash":
                metadata.get(
                    "chunk_hash",
                    "",
                ),
        })

    return evidence


# ============================================================
# GET ONE DOCUMENT'S CHUNKS
# ============================================================

def get_document_chunks(
    user_id: int,
    document_id: int,
):
    """
    Return all vector chunks for a specific user document.
    """

    collection = get_collection()

    return collection.get(
        where={
            "$and": [
                {
                    "user_id":
                        int(user_id)
                },
                {
                    "document_id":
                        int(document_id)
                },
            ]
        },
        include=[
            "documents",
            "metadatas",
        ],
    )


# ============================================================
# GET ALL USER CHUNKS
# ============================================================

def get_user_chunks(
    user_id: int,
):
    """
    Return every RAG chunk belonging to one user.
    """

    collection = get_collection()

    return collection.get(
        where={
            "user_id":
                int(user_id)
        },
        include=[
            "documents",
            "metadatas",
        ],
    )


# ============================================================
# DELETE DOCUMENT CHUNKS
# ============================================================

def delete_document_chunks(
    user_id: int,
    document_id: int,
):
    """
    Delete all Chroma chunks belonging to one SQLite document.
    """

    collection = get_collection()

    collection.delete(
        where={
            "$and": [
                {
                    "user_id":
                        int(user_id)
                },
                {
                    "document_id":
                        int(document_id)
                },
            ]
        }
    )


# ============================================================
# DELETE ALL USER CHUNKS
# ============================================================

def delete_user_chunks(
    user_id: int,
):
    """
    Delete all Chroma data belonging to one user.

    Used before SQLite account deletion.
    """

    collection = get_collection()

    collection.delete(
        where={
            "user_id":
                int(user_id)
        }
    )


# ============================================================
# DOCUMENT COUNT
# ============================================================

def get_document_chunk_count(
    user_id: int,
    document_id: int,
) -> int:
    """
    Return chunk count for one user document.
    """

    result = get_collection().get(
        where={
            "$and": [
                {
                    "user_id":
                        int(user_id)
                },
                {
                    "document_id":
                        int(document_id)
                },
            ]
        },
        include=[],
    )

    return len(
        result.get(
            "ids",
            []
        )
        or []
    )


# ============================================================
# USER COUNT
# ============================================================

def get_user_chunk_count(
    user_id: int,
) -> int:
    """
    Return total Chroma chunks for one user.
    """

    result = get_collection().get(
        where={
            "user_id":
                int(user_id)
        },
        include=[],
    )

    return len(
        result.get(
            "ids",
            []
        )
        or []
    )


# ============================================================
# TOTAL COUNT
# ============================================================

def get_collection_count() -> int:
    """
    Return total collection chunk count.
    """

    return get_collection().count()


# ============================================================
# REBUILD ONE DOCUMENT
# ============================================================

def rebuild_document_chunks(
    user_id: int,
    document_id: int,
    filename: str,
    text: str,
    file_type: str = "",
    source_label: str = "",
    chunk_size: int = 900,
    overlap: int = 150,
):
    """
    Fully replace one document's vectors.

    Used when:
    - Chroma was reset
    - document embeddings need rebuilding
    - chunking settings change during maintenance
    """

    delete_document_chunks(
        user_id=user_id,
        document_id=document_id,
    )

    return add_document_chunks(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        text=text,
        file_type=file_type,
        source_label=source_label,
        chunk_size=chunk_size,
        overlap=overlap,
    )


# ============================================================
# RESET VECTOR STORE
# ============================================================

def reset_vector_store():
    """
    DEVELOPMENT / ADMINISTRATIVE RESET.

    Delete and recreate the PURSUIT collection.
    """

    client = get_client()

    try:

        client.delete_collection(
            name=COLLECTION_NAME
        )

    except Exception:
        pass

    return get_collection()


# ============================================================
# HEALTH / SUMMARY
# ============================================================

def get_vector_store_summary():
    """
    Return vector-store debugging information.
    """

    collection = get_collection()

    return {
        "path":
            str(
                CHROMA_PATH.resolve()
            ),

        "collection":
            COLLECTION_NAME,

        "chunks":
            collection.count(),
    }


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    collection = get_collection()

    print(
        "PURSUIT ChromaDB initialized."
    )

    print(
        f"Path: "
        f"{CHROMA_PATH.resolve()}"
    )

    print(
        f"Collection: "
        f"{COLLECTION_NAME}"
    )

    print(
        f"Chunks: "
        f"{collection.count()}"
    )








# rag/ingestion.py

from io import BytesIO
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from app.database import (
    create_document,
    delete_document,
    get_user_document,
)
from rag.vector_store import (
    add_document_chunks,
    delete_document_chunks,
    rebuild_document_chunks,
)


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
}

SUPPORTED_PDF_EXTENSIONS = {
    ".pdf",
}

SUPPORTED_EXTENSIONS = (
    SUPPORTED_TEXT_EXTENSIONS
    | SUPPORTED_PDF_EXTENSIONS
)


# ============================================================
# TEXT EXTRACTION
# ============================================================

def extract_text_from_text_file(
    file_bytes: bytes,
) -> str:
    """
    Decode TXT / Markdown files.

    UTF-8 is preferred.
    Invalid bytes are ignored rather than crashing ingestion.
    """

    return file_bytes.decode(
        "utf-8",
        errors="ignore",
    )


def extract_text_from_pdf(
    file_bytes: bytes,
) -> str:
    """
    Extract machine-readable text from PDF bytes.

    This does not perform OCR.
    Image-only/scanned PDFs may produce no readable text.
    """

    if not file_bytes:
        return ""

    reader = PdfReader(
        BytesIO(file_bytes)
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):

        page_text = (
            page.extract_text()
            or ""
        )

        page_text = (
            page_text.strip()
        )

        if not page_text:
            continue

        pages.append(
            (
                f"[Page {page_number}]\n"
                f"{page_text}"
            )
        )

    return "\n\n".join(
        pages
    )


def extract_text(
    filename: str,
    file_bytes: bytes,
) -> str:
    """
    Extract text according to file extension.
    """

    if not filename:
        raise ValueError(
            "Filename is required."
        )

    if not file_bytes:
        raise ValueError(
            "Uploaded file is empty."
        )

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    if suffix in SUPPORTED_TEXT_EXTENSIONS:

        return extract_text_from_text_file(
            file_bytes
        )

    if suffix in SUPPORTED_PDF_EXTENSIONS:

        return extract_text_from_pdf(
            file_bytes
        )

    raise ValueError(
        f"Unsupported file type: {suffix}"
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_extracted_text(
    text: str,
) -> str:
    """
    Normalize extracted document text.

    Keeps paragraph structure while removing noisy whitespace.
    """

    if not text:
        return ""

    normalized_lines = []

    previous_blank = False

    for raw_line in text.splitlines():

        cleaned = " ".join(
            raw_line.split()
        ).strip()

        if not cleaned:

            if (
                normalized_lines
                and not previous_blank
            ):
                normalized_lines.append(
                    ""
                )

            previous_blank = True

            continue

        normalized_lines.append(
            cleaned
        )

        previous_blank = False

    return "\n".join(
        normalized_lines
    ).strip()


# ============================================================
# DOCUMENT TYPE NORMALIZATION
# ============================================================

def normalize_file_type(
    file_type: Optional[str],
) -> str:
    """
    Normalize user-facing document type.

    These values are metadata only.
    """

    if not file_type:
        return "OTHER"

    normalized = (
        str(file_type)
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    aliases = {
        "RESUME": "RESUME",
        "CV": "RESUME",

        "CERTIFICATION": "CERTIFICATION",
        "CERTIFICATIONS": "CERTIFICATION",
        "CERTIFICATE": "CERTIFICATION",

        "PROJECT": "PROJECTS",
        "PROJECTS": "PROJECTS",
        "PORTFOLIO": "PROJECTS",

        "EDUCATION": "EDUCATION",
        "ACADEMIC": "EDUCATION",

        "CAREER_GOAL": "CAREER_GOALS",
        "CAREER_GOALS": "CAREER_GOALS",
        "GOALS": "CAREER_GOALS",

        "EXPERIENCE": "EXPERIENCE",
        "WORK_EXPERIENCE": "EXPERIENCE",

        "SKILLS": "SKILLS",

        "OTHER": "OTHER",
    }

    return aliases.get(
        normalized,
        "OTHER",
    )


# ============================================================
# SOURCE LABEL
# ============================================================

def build_source_label(
    filename: str,
    file_type: str,
) -> str:
    """
    Human-readable source label used by retrieved evidence.
    """

    label_type = (
        file_type
        .replace("_", " ")
        .title()
    )

    return (
        f"{label_type}: {filename}"
    )


# ============================================================
# INGEST DOCUMENT
# ============================================================

def ingest_document(
    user_id: int,
    filename: str,
    file_bytes: bytes,
    file_type: str = "OTHER",
):
    """
    Final PURSUIT document ingestion flow.

    Flow:

        upload
          ↓
        validate
          ↓
        extract text
          ↓
        normalize text
          ↓
        SQLite duplicate check / insert
          ↓
        ChromaDB chunk insertion

    Returns:
        {
            "document_id": int,
            "filename": str,
            "file_type": str,
            "text_length": int,
            "chunks_created": int,
            "chunk_ids": [...],
            "duplicate": bool
        }

    Important consistency rule:
    if a new SQLite document is created but Chroma ingestion
    fails, the SQLite document is rolled back.
    """

    if not user_id:
        raise ValueError(
            "user_id is required."
        )

    if not filename:
        raise ValueError(
            "filename is required."
        )

    normalized_file_type = (
        normalize_file_type(
            file_type
        )
    )

    extracted_text = extract_text(
        filename=filename,
        file_bytes=file_bytes,
    )

    extracted_text = (
        normalize_extracted_text(
            extracted_text
        )
    )

    if not extracted_text:

        raise ValueError(
            "No readable text could be extracted "
            "from this document."
        )

    # --------------------------------------------------------
    # SQLite
    # --------------------------------------------------------

    document_result = create_document(
        user_id=user_id,
        filename=filename,
        file_type=normalized_file_type,
        file_path=None,
        extracted_text=extracted_text,
        chroma_document_id=None,
    )

    document_id = (
        document_result[
            "document_id"
        ]
    )

    created = (
        document_result[
            "created"
        ]
    )

    if not document_id:

        raise RuntimeError(
            "Document could not be created."
        )

    # --------------------------------------------------------
    # Exact duplicate
    # --------------------------------------------------------

    if not created:

        return {
            "document_id":
                document_id,

            "filename":
                filename,

            "file_type":
                normalized_file_type,

            "text_length":
                len(extracted_text),

            "chunks_created":
                0,

            "chunk_ids":
                [],

            "duplicate":
                True,
        }

    # --------------------------------------------------------
    # ChromaDB
    # --------------------------------------------------------

    source_label = build_source_label(
        filename=filename,
        file_type=normalized_file_type,
    )

    try:

        chunk_ids = add_document_chunks(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            text=extracted_text,
            file_type=normalized_file_type,
            source_label=source_label,
        )

        if not chunk_ids:

            raise RuntimeError(
                "No ChromaDB chunks were created."
            )

    except Exception:

        # A newly inserted SQLite document without vectors
        # would make retrieval inconsistent.
        #
        # Therefore roll back the SQLite document.
        delete_document(
            user_id=user_id,
            document_id=document_id,
        )

        raise

    return {
        "document_id":
            document_id,

        "filename":
            filename,

        "file_type":
            normalized_file_type,

        "text_length":
            len(extracted_text),

        "chunks_created":
            len(chunk_ids),

        "chunk_ids":
            chunk_ids,

        "duplicate":
            False,
    }


# ============================================================
# DELETE DOCUMENT
# ============================================================

def remove_document(
    user_id: int,
    document_id: int,
):
    """
    Permanently remove one document from:

    1. ChromaDB
    2. SQLite

    Ownership is validated first.
    """

    document = get_user_document(
        user_id=user_id,
        document_id=document_id,
    )

    if not document:

        raise ValueError(
            "Document not found."
        )

    # --------------------------------------------------------
    # Chroma first
    # --------------------------------------------------------

    delete_document_chunks(
        user_id=user_id,
        document_id=document_id,
    )

    # --------------------------------------------------------
    # SQLite second
    # --------------------------------------------------------

    deleted = delete_document(
        user_id=user_id,
        document_id=document_id,
    )

    if not deleted:

        raise RuntimeError(
            "Document could not be removed from SQLite."
        )

    return True


# ============================================================
# REBUILD ONE DOCUMENT
# ============================================================

def reingest_document(
    user_id: int,
    document_id: int,
):
    """
    Rebuild Chroma chunks from SQLite extracted text.

    Useful for:
    - recovery after Chroma reset
    - administrative vector rebuild
    - restoring missing embeddings

    Does not modify the SQLite document.
    """

    document = get_user_document(
        user_id=user_id,
        document_id=document_id,
    )

    if not document:

        raise ValueError(
            "Document not found."
        )

    text = (
        document[
            "extracted_text"
        ]
        or ""
    ).strip()

    if not text:

        raise ValueError(
            "Document has no extracted text."
        )

    file_type = (
        document[
            "file_type"
        ]
        or "OTHER"
    )

    filename = (
        document[
            "filename"
        ]
    )

    source_label = build_source_label(
        filename=filename,
        file_type=file_type,
    )

    chunk_ids = rebuild_document_chunks(
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        text=text,
        file_type=file_type,
        source_label=source_label,
    )

    if not chunk_ids:

        raise RuntimeError(
            "Vector rebuild produced no chunks."
        )

    return {
        "document_id":
            document_id,

        "filename":
            filename,

        "chunks_created":
            len(chunk_ids),

        "chunk_ids":
            chunk_ids,
    }


# ============================================================
# VALIDATE DOCUMENT / VECTOR CONSISTENCY
# ============================================================

def validate_document_ingestion(
    user_id: int,
    document_id: int,
):
    """
    Validate that a SQLite document exists.

    Vector count should be checked by the caller using
    get_document_chunk_count() when required.
    """

    document = get_user_document(
        user_id=user_id,
        document_id=document_id,
    )

    return {
        "exists":
            document is not None,

        "document_id":
            document_id,

        "filename":
            (
                document[
                    "filename"
                ]
                if document
                else None
            ),

        "file_type":
            (
                document[
                    "file_type"
                ]
                if document
                else None
            ),
    }


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    print(
        "PURSUIT document ingestion module ready."
    )

    print(
        "Supported file extensions:"
    )

    for extension in sorted(
        SUPPORTED_EXTENSIONS
    ):

        print(
            f"  {extension}"
        )




        
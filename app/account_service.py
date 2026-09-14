




# app/account_service.py

from app.database import (
    delete_user,
    get_user,
    get_user_documents,
)

from rag.vector_store import (
    delete_document_chunks,
    delete_user_chunks,
)


# ============================================================
# ACCOUNT LOOKUP
# ============================================================

def get_account_summary(
    user_id: int,
):
    """
    Return a lightweight summary used by Account/Profile UI.
    """

    user = get_user(
        user_id
    )

    if not user:
        return None

    documents = get_user_documents(
        user_id
    )

    return {
        "user_id":
            user["id"],

        "name":
            user["name"],

        "email":
            user["email"],

        "document_count":
            len(documents),

        "created_at":
            user["created_at"],
    }


# ============================================================
# DELETE ACCOUNT
# ============================================================

def delete_user_account(
    user_id: int,
):
    """
    Permanently delete a PURSUIT account.

    Flow:

        validate user
            ↓
        remove all ChromaDB chunks
            ↓
        delete SQLite user
            ↓
        SQLite ON DELETE CASCADE removes:
            profile
            documents
            opportunities
            opportunity_sources
            evaluations
            watchlist
            history

    Returns:
        {
            "deleted": True,
            "user_id": int
        }
    """

    user = get_user(
        user_id
    )

    if not user:

        raise ValueError(
            "User account not found."
        )

    # --------------------------------------------------------
    # ChromaDB first
    # --------------------------------------------------------

    delete_user_chunks(
        user_id=user_id
    )

    # --------------------------------------------------------
    # SQLite second
    # --------------------------------------------------------

    deleted = delete_user(
        user_id=user_id
    )

    if not deleted:

        raise RuntimeError(
            "SQLite account deletion failed."
        )

    return {
        "deleted":
            True,

        "user_id":
            user_id,
    }


# ============================================================
# REMOVE ALL USER RAG DATA ONLY
# ============================================================

def clear_user_rag_data(
    user_id: int,
):
    """
    Remove all ChromaDB chunks for a user
    without deleting the SQLite account.

    Useful for administrative recovery or
    rebuilding profile evidence.
    """

    user = get_user(
        user_id
    )

    if not user:

        raise ValueError(
            "User account not found."
        )

    delete_user_chunks(
        user_id=user_id
    )

    return {
        "cleared":
            True,

        "user_id":
            user_id,
    }


# ============================================================
# REMOVE ONE DOCUMENT'S RAG DATA ONLY
# ============================================================

def clear_document_rag_data(
    user_id: int,
    document_id: int,
):
    """
    Remove Chroma chunks for one document
    without deleting the SQLite document row.

    Mainly useful for maintenance/re-ingestion.
    """

    user = get_user(
        user_id
    )

    if not user:

        raise ValueError(
            "User account not found."
        )

    delete_document_chunks(
        user_id=user_id,
        document_id=document_id,
    )

    return {
        "cleared":
            True,

        "user_id":
            user_id,

        "document_id":
            document_id,
    }






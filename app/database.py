














# app/database.py

import hashlib
import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any, Optional
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlparse,
    urlunparse,
)

from app.constants import (
    # Categories
    CATEGORY_OTHER,
    normalize_category,

    # Recommendations
    normalize_recommendation,

    # Workflow
    STATUS_DISCOVERED,
    STATUS_WATCHING,
    STATUS_APPLIED,
    STATUS_NOT_INTERESTED,
    STATUS_ARCHIVED,
    normalize_status,

    # Actions
    ACTION_WATCH,
    ACTION_UNWATCH,
    ACTION_APPLIED,
    ACTION_NOT_INTERESTED,
    ACTION_ARCHIVED,
    ACTION_RESTORED,

    # Work arrangements
    WORK_UNKNOWN,
    normalize_work_arrangement,

    # Activity
    OPPORTUNITY_ACTIVE,
    OPPORTUNITY_CLOSED,
    OPPORTUNITY_UNKNOWN,
    VALID_OPPORTUNITY_ACTIVITY,

    # Sources
    SOURCE_OTHER,
    VALID_SOURCE_TYPES,

    # Scores
    clamp_score,

    # Dashboard
    DASHBOARD_FILTER_ALL,
    DASHBOARD_FILTER_NEW,
    DASHBOARD_FILTER_PURSUE,
    DASHBOARD_FILTER_REVIEW,
    DASHBOARD_FILTER_REJECTED,
    DASHBOARD_FILTER_WATCH,
    DASHBOARD_FILTER_APPLIED,

    # History
    HISTORY_FILTER_ALL,
    HISTORY_FILTER_WATCH,
    HISTORY_FILTER_UNWATCH,
    HISTORY_FILTER_NOT_INTERESTED,
    HISTORY_FILTER_APPLIED,
    HISTORY_FILTER_ARCHIVED,
    HISTORY_FILTER_RESTORED,

    # Sorting
    SORT_NEWEST,
    SORT_OLDEST,
    SORT_HIGHEST_SCORE,
    SORT_LOWEST_SCORE,
)


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("data/pursuit.db")

# ============================================================
# UI WORKFLOW EXTENSIONS
# ============================================================
# INTERESTED is intentionally a user workflow state, separate
# from AI recommendation PURSUE / REVIEW / REJECT.
STATUS_INTERESTED = "INTERESTED"
ACTION_INTERESTED = "INTERESTED"
ACTION_UNINTERESTED = "UNINTERESTED"
DASHBOARD_FILTER_INTERESTED = "Interested"
HISTORY_FILTER_INTERESTED = "Interested"
HISTORY_FILTER_UNINTERESTED = "Uninterested"


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    """
    Return a configured SQLite connection.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    conn = sqlite3.connect(
        DB_PATH,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    conn.execute(
        "PRAGMA journal_mode = WAL"
    )

    conn.execute(
        "PRAGMA synchronous = NORMAL"
    )

    conn.execute(
        "PRAGMA busy_timeout = 5000"
    )

    return conn


# ============================================================
# JSON HELPERS
# ============================================================

def to_json(
    value: Any,
) -> Optional[str]:
    """
    Serialize Python values to JSON text.
    """

    if value is None:
        return None

    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    )


def from_json(
    value: Optional[str],
    default=None,
):
    """
    Parse JSON safely.
    """

    if value in (
        None,
        "",
    ):
        return default

    try:
        return json.loads(
            value
        )

    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return default


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(
    value,
) -> str:
    """
    Normalize surrounding and repeated whitespace.
    """

    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def normalize_identity_text(
    value,
) -> str:
    """
    Normalize text used for dedupe fingerprints.
    """

    return clean_text(
        value
    ).lower()


# ============================================================
# URL HELPERS
# ============================================================

TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
    "src",
    "campaign",
    "campaignid",
    "trk",
    "tracking",
    "trackingid",
    "gh_src",
}


def normalize_url(
    url: Optional[str],
) -> str:
    """
    Canonicalize URLs without removing meaningful job IDs.

    Removes:
    - fragment
    - common tracking parameters
    - default ports
    - trailing slash except domain root
    """

    if not url:
        return ""

    raw = clean_text(
        url
    )

    if not raw:
        return ""

    if "://" not in raw:
        raw = (
            "https://"
            + raw
        )

    try:

        parsed = urlparse(
            raw
        )

        scheme = (
            parsed.scheme.lower()
            or "https"
        )

        hostname = (
            parsed.hostname.lower()
            if parsed.hostname
            else ""
        )

        if not hostname:
            return raw

        netloc = hostname

        if parsed.port:

            is_default_port = (
                scheme == "https"
                and parsed.port == 443
            ) or (
                scheme == "http"
                and parsed.port == 80
            )

            if not is_default_port:
                netloc = (
                    f"{hostname}:"
                    f"{parsed.port}"
                )

        path = (
            parsed.path
            or "/"
        )

        if path != "/":
            path = path.rstrip("/")

        query_items = []

        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        ):

            key_lower = (
                key.lower()
            )

            if (
                key_lower
                in TRACKING_QUERY_KEYS
            ):
                continue

            if key_lower.startswith(
                "utm_"
            ):
                continue

            query_items.append(
                (
                    key,
                    value,
                )
            )

        query = urlencode(
            query_items,
            doseq=True,
        )

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                query,
                "",
            )
        )

    except Exception:
        return raw.rstrip("/")


def get_domain(
    url: Optional[str],
) -> str:
    """
    Return normalized hostname.
    """

    canonical = normalize_url(
        url
    )

    if not canonical:
        return ""

    try:

        parsed = urlparse(
            canonical
        )

        return (
            parsed.hostname
            or ""
        ).lower()

    except Exception:
        return ""


# ============================================================
# HASH HELPERS
# ============================================================

def sha256_text(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def build_content_hash(
    content: str,
) -> str:
    """
    Content hash used for duplicate user documents.
    """

    normalized = (
        content
        if content is not None
        else ""
    )

    return sha256_text(
        normalized
    )


# ============================================================
# OPPORTUNITY IDENTITY
# ============================================================

def build_opportunity_key(
    organization: Optional[str],
    title: Optional[str],
    location: Optional[str] = None,
    external_id: Optional[str] = None,
    canonical_url: Optional[str] = None,
) -> str:
    """
    Build canonical opportunity identity.

    Priority:
    1. organization + external_id
    2. normalized canonical URL
    3. organization + title + location

    This allows:
    - same company to have multiple jobs
    - job IDs to survive URL changes
    - URL-only sources when no external ID exists
    - fallback identity when URLs are weak/missing
    """

    organization_norm = (
        normalize_identity_text(
            organization
        )
    )

    title_norm = (
        normalize_identity_text(
            title
        )
    )

    location_norm = (
        normalize_identity_text(
            location
        )
    )

    external_id_norm = (
        normalize_identity_text(
            external_id
        )
    )

    canonical_url_norm = (
        normalize_url(
            canonical_url
        )
    )

    if external_id_norm:

        base = (
            "external|"
            f"{organization_norm}|"
            f"{external_id_norm}"
        )

    elif canonical_url_norm:

        base = (
            "url|"
            f"{canonical_url_norm}"
        )

    else:

        base = (
            "fallback|"
            f"{organization_norm}|"
            f"{title_norm}|"
            f"{location_norm}"
        )

    return sha256_text(
        base
    )


# ============================================================
# PASSWORD HELPERS
# ============================================================

def hash_password(
    password: str,
):
    """
    PBKDF2 password hash.
    """

    if not password:
        raise ValueError(
            "Password cannot be empty."
        )

    salt = secrets.token_hex(
        16
    )

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(
            "utf-8"
        ),
        salt.encode(
            "utf-8"
        ),
        200_000,
    ).hex()

    return (
        salt,
        password_hash,
    )


def verify_password(
    password: str,
    salt: str,
    password_hash: str,
) -> bool:
    """
    Verify user password.
    """

    calculated = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(
            "utf-8"
        ),
        salt.encode(
            "utf-8"
        ),
        200_000,
    ).hex()

    return secrets.compare_digest(
        calculated,
        password_hash,
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Create final PURSUIT schema.

    This implementation assumes a fresh database.
    """

    with get_connection() as conn:

        # ====================================================
        # USERS
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,

                email TEXT NOT NULL
                    COLLATE NOCASE
                    UNIQUE,

                password_salt TEXT,

                password_hash TEXT,

                auth_provider TEXT NOT NULL
                    DEFAULT 'LOCAL',

                provider_subject TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ====================================================
        # PROFILES
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL
                    UNIQUE,

                career_goal TEXT,

                skills TEXT,

                currently_learning TEXT,

                opportunity_types TEXT,

                work_preferences TEXT,

                learning_value INTEGER
                    NOT NULL DEFAULT 50,

                portfolio_value INTEGER
                    NOT NULL DEFAULT 50,

                compensation_value INTEGER
                    NOT NULL DEFAULT 50,

                career_growth_value INTEGER
                    NOT NULL DEFAULT 50,

                remote_work_value INTEGER
                    NOT NULL DEFAULT 50,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE
            )
            """
        )

        # ====================================================
        # DOCUMENTS
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                filename TEXT NOT NULL,

                file_type TEXT,

                file_path TEXT,

                extracted_text TEXT NOT NULL,

                content_hash TEXT NOT NULL,

                chroma_document_id TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE,

                UNIQUE (
                    user_id,
                    content_hash
                )
            )
            """
        )

        # ====================================================
        # OPPORTUNITIES
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                opportunity_key TEXT NOT NULL,

                external_id TEXT,

                title TEXT NOT NULL,

                organization TEXT,

                category TEXT NOT NULL
                    DEFAULT 'OTHER',

                location TEXT,

                work_arrangement TEXT NOT NULL
                    DEFAULT 'UNKNOWN',

                deadline TEXT,

                reward TEXT,

                description TEXT,

                requirements TEXT NOT NULL
                    DEFAULT '[]',

                eligibility TEXT NOT NULL
                    DEFAULT '[]',

                submission TEXT,

                details TEXT NOT NULL
                    DEFAULT '{}',

                evidence TEXT NOT NULL
                    DEFAULT '[]',

                score INTEGER,

                recommendation TEXT,

                matching_skills TEXT NOT NULL
                    DEFAULT '[]',

                skill_gaps TEXT NOT NULL
                    DEFAULT '[]',

                status TEXT NOT NULL
                    DEFAULT 'DISCOVERED',

                is_new INTEGER NOT NULL
                    DEFAULT 1,

                activity_status TEXT NOT NULL
                    DEFAULT 'UNKNOWN',

                first_found_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_verified_at TEXT,

                closed_at TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE,

                UNIQUE (
                    user_id,
                    opportunity_key
                )
            )
            """
        )

        # ====================================================
        # OPPORTUNITY SOURCES
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_id INTEGER NOT NULL,

                source_type TEXT NOT NULL
                    DEFAULT 'OTHER',

                source_name TEXT,

                external_id TEXT,

                source_url TEXT NOT NULL,

                canonical_url TEXT NOT NULL,

                source_domain TEXT,

                is_primary INTEGER NOT NULL
                    DEFAULT 0,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    opportunity_id
                )
                REFERENCES opportunities(id)
                ON DELETE CASCADE,

                UNIQUE (
                    opportunity_id,
                    canonical_url
                )
            )
            """
        )

        # ====================================================
        # EVALUATIONS
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_id INTEGER NOT NULL,

                personal_fit_score INTEGER,

                learning_value INTEGER,

                portfolio_value INTEGER,

                effort_score INTEGER,

                risk_score INTEGER,

                overall_score INTEGER,

                recommendation TEXT,

                reasoning TEXT,

                why_recommendation TEXT,

                requirements_analysis TEXT,

                personal_fit_analysis TEXT,

                effort_risk_analysis TEXT,

                why_not_analysis TEXT,

                what_could_change_decision TEXT,

                estimated_effort TEXT,

                time_pressure TEXT,

                risks TEXT NOT NULL
                    DEFAULT '[]',

                opportunity_cost TEXT,

                next_actions TEXT NOT NULL
                    DEFAULT '[]',

                research_output TEXT NOT NULL
                    DEFAULT '{}',

                personal_fit_output TEXT NOT NULL
                    DEFAULT '{}',

                value_output TEXT NOT NULL
                    DEFAULT '{}',

                risk_output TEXT NOT NULL
                    DEFAULT '{}',

                decision_output TEXT NOT NULL
                    DEFAULT '{}',

                agent_output TEXT NOT NULL
                    DEFAULT '{}',

                model_info TEXT NOT NULL
                    DEFAULT '{}',

                evaluation_version TEXT NOT NULL
                    DEFAULT '1.0',

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    opportunity_id
                )
                REFERENCES opportunities(id)
                ON DELETE CASCADE
            )
            """
        )

        # ====================================================
        # OPPORTUNITY PIPELINE STATE
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_pipeline_state (
                opportunity_id INTEGER PRIMARY KEY,

                pipeline_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                current_stage TEXT NOT NULL
                    DEFAULT 'DISCOVERY',

                research_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                personal_fit_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                value_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                effort_risk_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                decision_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                research_output TEXT NOT NULL
                    DEFAULT '{}',

                personal_fit_output TEXT NOT NULL
                    DEFAULT '{}',

                value_output TEXT NOT NULL
                    DEFAULT '{}',

                risk_output TEXT NOT NULL
                    DEFAULT '{}',

                decision_output TEXT NOT NULL
                    DEFAULT '{}',

                last_error TEXT,

                last_error_stage TEXT,

                retry_count INTEGER NOT NULL
                    DEFAULT 0,

                started_at TEXT,

                completed_at TEXT,

                last_attempt_at TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    opportunity_id
                )
                REFERENCES opportunities(id)
                ON DELETE CASCADE
            )
            """
        )

        # ====================================================
        # WATCHLIST
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                opportunity_id INTEGER NOT NULL,

                monitoring_enabled INTEGER NOT NULL
                    DEFAULT 1,

                last_checked_at TEXT,

                deadline_changed INTEGER NOT NULL
                    DEFAULT 0,

                requirements_changed INTEGER NOT NULL
                    DEFAULT 0,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE,

                FOREIGN KEY (
                    opportunity_id
                )
                REFERENCES opportunities(id)
                ON DELETE CASCADE,

                UNIQUE (
                    user_id,
                    opportunity_id
                )
            )
            """
        )

        # ====================================================
        # HISTORY
        # ====================================================

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,

                opportunity_id INTEGER NOT NULL,

                old_status TEXT,

                new_status TEXT,

                action TEXT NOT NULL,

                note TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE,

                FOREIGN KEY (
                    opportunity_id
                )
                REFERENCES opportunities(id)
                ON DELETE CASCADE
            )
            """
        )

        # ====================================================
        # INDEXES
        # ====================================================

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_profiles_user
            ON profiles(user_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_documents_user
            ON documents(user_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_user
            ON opportunities(user_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_status
            ON opportunities(
                user_id,
                status
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_recommendation
            ON opportunities(
                user_id,
                recommendation
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_category
            ON opportunities(
                user_id,
                category
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_found
            ON opportunities(
                user_id,
                first_found_at
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_opportunities_activity
            ON opportunities(
                user_id,
                activity_status
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_sources_opportunity
            ON opportunity_sources(
                opportunity_id
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_sources_url
            ON opportunity_sources(
                canonical_url
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_sources_domain
            ON opportunity_sources(
                source_domain
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_evaluations_opportunity
            ON evaluations(
                opportunity_id,
                created_at
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_pipeline_status
            ON opportunity_pipeline_state(
                pipeline_status,
                current_stage
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_watchlist_user
            ON watchlist(
                user_id
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_history_user
            ON opportunity_history(
                user_id,
                created_at
            )
            """
        )

        # External identity columns are additive for older local DBs.
        user_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

        if "auth_provider" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'LOCAL'"
            )

        if "provider_subject" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN provider_subject TEXT"
            )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_users_provider_subject
            ON users(auth_provider, provider_subject)
            WHERE provider_subject IS NOT NULL
            """
        )

        conn.commit()


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(
    name: str,
    email: str,
    password: str,
) -> int:
    """
    Create or enable local-password login for a user.

    Account-linking rule:
    - New email: create a LOCAL user.
    - Existing Google/OIDC user with no local password: attach the new
      PURSUIT password to the SAME user row.
    - Existing user that already has a local password: reject duplicate
      registration.

    The password supplied here is always a PURSUIT password. PURSUIT
    never receives or stores the user's Google password.
    """

    name = clean_text(name)
    email = clean_text(email).lower()

    if not name:
        raise ValueError("Name is required.")

    if not email:
        raise ValueError("Email is required.")

    if not password:
        raise ValueError("Password is required.")

    salt, password_hash = hash_password(password)

    existing = get_user_by_email(email)

    if existing:
        # Google/OIDC-first account: allow the owner to add a PURSUIT
        # password while preserving provider_subject so Google login keeps
        # resolving to this same user_id.
        if not existing["password_salt"] and not existing["password_hash"]:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users
                    SET name = ?,
                        password_salt = ?,
                        password_hash = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        name or existing["name"],
                        salt,
                        password_hash,
                        existing["id"],
                    ),
                )
                conn.commit()

            return int(existing["id"])

        raise ValueError(
            "An account with this email already exists. Log in instead."
        )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (
                name,
                email,
                password_salt,
                password_hash,
                auth_provider
            )
            VALUES (?, ?, ?, ?, 'LOCAL')
            """,
            (
                name,
                email,
                salt,
                password_hash,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_user(
    user_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()


def get_user_by_email(
    email: str,
):
    email = (
        clean_text(
            email
        ).lower()
    )

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (
                email,
            ),
        ).fetchone()


def authenticate_user(
    email: str,
    password: str,
):
    """
    Return user row if credentials are valid.
    """

    user = get_user_by_email(
        email
    )

    if not user:
        return None

    # Password login is only valid for users with local credentials.
    if (
        clean_text(user["auth_provider"] or "LOCAL").upper() != "LOCAL"
        and not user["password_hash"]
    ):
        return None

    if not user["password_salt"] or not user["password_hash"]:
        return None

    if not verify_password(
        password,
        user["password_salt"],
        user["password_hash"],
    ):
        return None

    return user


def get_user_by_external_identity(
    provider: str,
    provider_subject: str,
):
    provider = clean_text(provider).upper()
    provider_subject = clean_text(provider_subject)

    if not provider or not provider_subject:
        return None

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE auth_provider = ?
              AND provider_subject = ?
            LIMIT 1
            """,
            (provider, provider_subject),
        ).fetchone()


def get_or_create_external_user(
    provider: str,
    provider_subject: str,
    email: str,
    name: str,
) -> int:
    """Resolve or create an OAuth/OIDC-backed PURSUIT user."""
    provider = clean_text(provider).upper()
    provider_subject = clean_text(provider_subject)
    email = clean_text(email).lower()
    name = clean_text(name) or email.split("@")[0]

    if not provider or not provider_subject or not email:
        raise ValueError("Provider, provider subject, and email are required.")

    existing = get_user_by_external_identity(provider, provider_subject)
    if existing:
        return int(existing["id"])

    by_email = get_user_by_email(email)
    if by_email:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE users
                SET auth_provider = ?,
                    provider_subject = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (provider, provider_subject, by_email["id"]),
            )
            conn.commit()
        return int(by_email["id"])

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    name, email, password_salt, password_hash,
                    auth_provider, provider_subject
                )
                VALUES (?, ?, NULL, NULL, ?, ?)
                """,
                (name, email, provider, provider_subject),
            )
            conn.commit()
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        # Compatibility for an older DB whose password columns are still NOT NULL.
        # Credentials are cryptographically random and never exposed or accepted as a user password.
        if "NOT NULL constraint failed: users.password" not in str(exc):
            raise
        compat_secret = secrets.token_urlsafe(48)
        salt, password_hash = hash_password(compat_secret)
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (
                    name, email, password_salt, password_hash,
                    auth_provider, provider_subject
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, email, salt, password_hash, provider, provider_subject),
            )
            conn.commit()
            user_id = int(cursor.lastrowid)

    create_or_update_profile(user_id=user_id)
    return user_id


def delete_user(
    user_id: int,
) -> bool:
    """
    Delete user from SQLite.

    Cascades delete:
    - profile
    - documents
    - opportunities
    - sources
    - evaluations
    - watchlist
    - history

    ChromaDB must be cleaned by account_service before this call.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        )

        conn.commit()

        return (
            cursor.rowcount > 0
        )


# ============================================================
# PROFILE FUNCTIONS
# ============================================================

def create_or_update_profile(
    user_id: int,
    career_goal=None,
    skills=None,
    currently_learning=None,
    opportunity_types=None,
    work_preferences=None,
    learning_value=50,
    portfolio_value=50,
    compensation_value=50,
    career_growth_value=50,
    remote_work_value=50,
):
    """
    Create/update structured profile.
    """

    if isinstance(
        opportunity_types,
        list,
    ):

        opportunity_types = (
            ",".join(
                clean_text(item)
                for item
                in opportunity_types
                if clean_text(item)
            )
        )

    def profile_score(
        value,
    ):
        normalized = clamp_score(
            value
        )

        return (
            normalized
            if normalized is not None
            else 50
        )

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO profiles (
                user_id,
                career_goal,
                skills,
                currently_learning,
                opportunity_types,
                work_preferences,
                learning_value,
                portfolio_value,
                compensation_value,
                career_growth_value,
                remote_work_value
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )

            ON CONFLICT(user_id)
            DO UPDATE SET

                career_goal =
                    excluded.career_goal,

                skills =
                    excluded.skills,

                currently_learning =
                    excluded.currently_learning,

                opportunity_types =
                    excluded.opportunity_types,

                work_preferences =
                    excluded.work_preferences,

                learning_value =
                    excluded.learning_value,

                portfolio_value =
                    excluded.portfolio_value,

                compensation_value =
                    excluded.compensation_value,

                career_growth_value =
                    excluded.career_growth_value,

                remote_work_value =
                    excluded.remote_work_value,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                user_id,
                career_goal,
                skills,
                currently_learning,
                opportunity_types,
                work_preferences,

                profile_score(
                    learning_value
                ),

                profile_score(
                    portfolio_value
                ),

                profile_score(
                    compensation_value
                ),

                profile_score(
                    career_growth_value
                ),

                profile_score(
                    remote_work_value
                ),
            ),
        )

        conn.commit()


def get_profile(
    user_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM profiles
            WHERE user_id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()


# ============================================================
# DOCUMENT FUNCTIONS
# ============================================================

def create_document(
    user_id: int,
    filename: str,
    file_type=None,
    file_path=None,
    extracted_text=None,
    chroma_document_id=None,
):
    """
    Insert document metadata/content.

    Exact duplicate content for the same user is reused.

    Returns:
        {
            "document_id": int,
            "created": bool
        }
    """

    filename = clean_text(
        filename
    )

    if not filename:
        raise ValueError(
            "Filename is required."
        )

    extracted_text = (
        extracted_text
        or ""
    )

    content_hash = (
        build_content_hash(
            extracted_text
        )
    )

    with get_connection() as conn:

        existing = conn.execute(
            """
            SELECT id
            FROM documents

            WHERE user_id = ?
              AND content_hash = ?

            LIMIT 1
            """,
            (
                user_id,
                content_hash,
            ),
        ).fetchone()

        if existing:

            return {
                "document_id":
                    existing["id"],

                "created":
                    False,
            }

        cursor = conn.execute(
            """
            INSERT INTO documents (
                user_id,
                filename,
                file_type,
                file_path,
                extracted_text,
                content_hash,
                chroma_document_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                filename,
                file_type,
                file_path,
                extracted_text,
                content_hash,
                chroma_document_id,
            ),
        )

        conn.commit()

        return {
            "document_id":
                cursor.lastrowid,

            "created":
                True,
        }


def get_document(
    document_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM documents
            WHERE id = ?
            """,
            (
                document_id,
            ),
        ).fetchone()


def get_user_document(
    user_id: int,
    document_id: int,
):
    """
    Ownership-safe document lookup.
    """

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM documents

            WHERE id = ?
              AND user_id = ?
            """,
            (
                document_id,
                user_id,
            ),
        ).fetchone()


def get_user_documents(
    user_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM documents

            WHERE user_id = ?

            ORDER BY
                created_at DESC,
                id DESC
            """,
            (
                user_id,
            ),
        ).fetchall()


def delete_document(
    user_id: int,
    document_id: int,
) -> bool:
    """
    Ownership-safe document deletion.
    """

    with get_connection() as conn:

        cursor = conn.execute(
            """
            DELETE FROM documents

            WHERE id = ?
              AND user_id = ?
            """,
            (
                document_id,
                user_id,
            ),
        )

        conn.commit()

        return (
            cursor.rowcount > 0
        )


# ============================================================
# OPPORTUNITY LOOKUPS
# ============================================================

def get_opportunity(
    opportunity_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM opportunities
            WHERE id = ?
            """,
            (
                opportunity_id,
            ),
        ).fetchone()


def get_user_opportunity(
    user_id: int,
    opportunity_id: int,
):
    """
    Ownership-safe opportunity lookup.

    Returns the opportunity together with its preferred source URL
    as ``primary_url`` so all UI surfaces can render Open Original.
    """

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT
                o.*,

                (
                    SELECT s.source_url
                    FROM opportunity_sources s

                    WHERE
                        s.opportunity_id = o.id

                    ORDER BY
                        s.is_primary DESC,
                        s.first_seen_at ASC,
                        s.id ASC

                    LIMIT 1
                ) AS primary_url

            FROM opportunities o

            WHERE o.id = ?
              AND o.user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        ).fetchone()


def get_opportunity_by_key(
    user_id: int,
    opportunity_key: str,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM opportunities

            WHERE user_id = ?
              AND opportunity_key = ?
            """,
            (
                user_id,
                opportunity_key,
            ),
        ).fetchone()


def find_opportunity_by_source_url(
    user_id: int,
    url: str,
):
    """
    Resolve a known opportunity from any source URL.
    """

    canonical_url = normalize_url(
        url
    )

    if not canonical_url:
        return None

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT o.*

            FROM opportunities o

            JOIN opportunity_sources s
              ON s.opportunity_id =
                 o.id

            WHERE o.user_id = ?
              AND s.canonical_url = ?

            LIMIT 1
            """,
            (
                user_id,
                canonical_url,
            ),
        ).fetchone()


# ============================================================
# OPPORTUNITY SOURCES
# ============================================================

def add_opportunity_source(
    opportunity_id: int,
    source_url: str,
    source_type: str = SOURCE_OTHER,
    source_name: Optional[str] = None,
    is_primary: bool = False,
    external_id: Optional[str] = None,
):
    """
    Add or refresh an opportunity source.
    """

    canonical_url = normalize_url(
        source_url
    )

    if not canonical_url:
        raise ValueError(
            "Source URL is required."
        )

    source_type = (
        clean_text(
            source_type
        ).upper()
    )

    if (
        source_type
        not in VALID_SOURCE_TYPES
    ):
        source_type = (
            SOURCE_OTHER
        )

    domain = get_domain(
        canonical_url
    )

    with get_connection() as conn:

        if is_primary:

            conn.execute(
                """
                UPDATE opportunity_sources

                SET
                    is_primary = 0,
                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE opportunity_id = ?
                """,
                (
                    opportunity_id,
                ),
            )

        conn.execute(
            """
            INSERT INTO opportunity_sources (
                opportunity_id,
                source_type,
                source_name,
                external_id,
                source_url,
                canonical_url,
                source_domain,
                is_primary
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(
                opportunity_id,
                canonical_url
            )
            DO UPDATE SET

                source_type =
                    excluded.source_type,

                source_name =
                    COALESCE(
                        excluded.source_name,
                        opportunity_sources.source_name
                    ),

                external_id =
                    COALESCE(
                        excluded.external_id,
                        opportunity_sources.external_id
                    ),

                source_url =
                    excluded.source_url,

                source_domain =
                    excluded.source_domain,

                is_primary =
                    CASE
                        WHEN excluded.is_primary = 1
                        THEN 1
                        ELSE opportunity_sources.is_primary
                    END,

                last_seen_at =
                    CURRENT_TIMESTAMP,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                opportunity_id,
                source_type,
                source_name,
                clean_text(external_id) or None,
                source_url,
                canonical_url,
                domain,
                1 if is_primary else 0,
            ),
        )

        conn.commit()


def get_opportunity_sources(
    opportunity_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM opportunity_sources

            WHERE opportunity_id = ?

            ORDER BY
                is_primary DESC,
                first_seen_at ASC,
                id ASC
            """,
            (
                opportunity_id,
            ),
        ).fetchall()


def get_primary_source(
    opportunity_id: int,
):
    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM opportunity_sources

            WHERE opportunity_id = ?

            ORDER BY
                is_primary DESC,
                first_seen_at ASC,
                id ASC

            LIMIT 1
            """,
            (
                opportunity_id,
            ),
        ).fetchone()


# ============================================================
# CREATE / UPDATE OPPORTUNITY
# ============================================================

def create_or_update_opportunity(
    user_id: int,
    title: str,

    organization: Optional[str] = None,
    category: str = CATEGORY_OTHER,

    source_url: Optional[str] = None,
    source_type: str = SOURCE_OTHER,
    source_name: Optional[str] = None,

    external_id: Optional[str] = None,

    location: Optional[str] = None,
    work_arrangement: Optional[str] = None,

    deadline: Optional[str] = None,
    reward: Optional[str] = None,

    description: Optional[str] = None,

    requirements=None,
    eligibility=None,
    submission=None,
    details=None,
    evidence=None,

    activity_status: str = OPPORTUNITY_UNKNOWN,

    is_primary_source: bool = True,
):
    """
    Canonical opportunity upsert.

    Later agents and Discovery should use this function.
    """

    title = clean_text(
        title
    )

    if not title:
        if normalize_url(source_url):
            title = "Pending research"
        else:
            raise ValueError(
                "Opportunity title or source URL is required."
            )

    organization = clean_text(
        organization
    )

    location = clean_text(
        location
    )

    category = normalize_category(
        category
    )

    work_arrangement = (
        normalize_work_arrangement(
            work_arrangement
        )
    )

    activity_status = (
        clean_text(
            activity_status
        ).upper()
        if activity_status
        else OPPORTUNITY_UNKNOWN
    )

    if (
        activity_status
        not in VALID_OPPORTUNITY_ACTIVITY
    ):
        activity_status = (
            OPPORTUNITY_UNKNOWN
        )

    canonical_url = normalize_url(
        source_url
    )

    opportunity_key = (
        build_opportunity_key(
            organization=organization,
            title=title,
            location=location,
            external_id=external_id,
            canonical_url=canonical_url,
        )
    )

    existing = get_opportunity_by_key(
        user_id=user_id,
        opportunity_key=
            opportunity_key,
    )

    if (
        existing is None
        and canonical_url
    ):
        existing = (
            find_opportunity_by_source_url(
                user_id=user_id,
                url=canonical_url,
            )
        )

    requirements_json = to_json(
        requirements or []
    )

    eligibility_json = to_json(
        eligibility or []
    )

    details_json = to_json(
        details or {}
    )

    evidence_json = to_json(
        evidence or []
    )

    if existing:

        opportunity_id = (
            existing["id"]
        )

        with get_connection() as conn:

            conn.execute(
                """
                UPDATE opportunities

                SET
                    external_id =
                        COALESCE(
                            ?,
                            external_id
                        ),

                    title =
                        CASE
                            WHEN ? <> ''
                            THEN ?
                            ELSE title
                        END,

                    organization =
                        CASE
                            WHEN ? <> ''
                            THEN ?
                            ELSE organization
                        END,

                    category = ?,

                    location =
                        CASE
                            WHEN ? <> ''
                            THEN ?
                            ELSE location
                        END,

                    work_arrangement = ?,

                    deadline =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE deadline
                        END,

                    reward =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE reward
                        END,

                    description =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE description
                        END,

                    requirements = ?,

                    eligibility = ?,

                    submission =
                        CASE
                            WHEN ? IS NOT NULL
                            THEN ?
                            ELSE submission
                        END,

                    details = ?,

                    evidence = ?,

                    activity_status = ?,

                    last_seen_at =
                        CURRENT_TIMESTAMP,

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    external_id,

                    title,
                    title,

                    organization,
                    organization,

                    category,

                    location,
                    location,

                    work_arrangement,

                    deadline,
                    deadline,

                    reward,
                    reward,

                    description,
                    description,

                    requirements_json,
                    eligibility_json,

                    submission,
                    submission,

                    details_json,
                    evidence_json,

                    activity_status,

                    opportunity_id,
                ),
            )

            conn.commit()

    else:

        with get_connection() as conn:

            cursor = conn.execute(
                """
                INSERT INTO opportunities (
                    user_id,
                    opportunity_key,
                    external_id,
                    title,
                    organization,
                    category,
                    location,
                    work_arrangement,
                    deadline,
                    reward,
                    description,
                    requirements,
                    eligibility,
                    submission,
                    details,
                    evidence,
                    status,
                    activity_status
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    user_id,
                    opportunity_key,
                    external_id,
                    title,
                    organization,
                    category,
                    location,
                    work_arrangement,
                    deadline,
                    reward,
                    description,
                    requirements_json,
                    eligibility_json,
                    submission,
                    details_json,
                    evidence_json,
                    STATUS_DISCOVERED,
                    activity_status,
                ),
            )

            opportunity_id = (
                cursor.lastrowid
            )

            conn.commit()

    if source_url:

        add_opportunity_source(
            opportunity_id=
                opportunity_id,

            source_url=
                source_url,

            source_type=
                source_type,

            source_name=
                source_name,

            is_primary=
                is_primary_source,

            external_id=
                external_id,
        )

    ensure_pipeline_state(
        opportunity_id
    )

    return opportunity_id


# ============================================================
# OPPORTUNITY EVALUATION SUMMARY
# ============================================================

def update_opportunity_evaluation(
    opportunity_id: int,
    score=None,
    recommendation=None,
    matching_skills=None,
    skill_gaps=None,
):
    """
    Update headline Dashboard evaluation fields.
    """

    score = clamp_score(
        score
    )

    if recommendation is not None:

        recommendation = (
            normalize_recommendation(
                recommendation
            )
        )

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE opportunities

            SET
                score = ?,
                recommendation = ?,
                matching_skills = ?,
                skill_gaps = ?,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                score,
                recommendation,

                to_json(
                    matching_skills
                    or []
                ),

                to_json(
                    skill_gaps
                    or []
                ),

                opportunity_id,
            ),
        )

        conn.commit()


def mark_opportunity_seen(
    user_id: int,
    opportunity_id: int,
):
    """
    Clear the Dashboard 'new' marker.
    """

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE opportunities

            SET
                is_new = 0,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        )

        conn.commit()


def mark_opportunity_verified(
    opportunity_id: int,
    activity_status: Optional[str] = None,
):
    """
    Mark successful Research verification.

    A successful fetch does not automatically mean the
    opportunity is ACTIVE. If Research explicitly supplies
    ACTIVE/CLOSED/UNKNOWN, persist it; otherwise preserve the
    current activity status.
    """

    normalized_activity = None

    if activity_status is not None:
        candidate = clean_text(
            activity_status
        ).upper()

        if candidate in VALID_OPPORTUNITY_ACTIVITY:
            normalized_activity = candidate

    with get_connection() as conn:

        if normalized_activity is None:
            conn.execute(
                """
                UPDATE opportunities

                SET
                    last_verified_at =
                        CURRENT_TIMESTAMP,

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    opportunity_id,
                ),
            )

        else:
            conn.execute(
                """
                UPDATE opportunities

                SET
                    last_verified_at =
                        CURRENT_TIMESTAMP,

                    activity_status = ?,

                    closed_at =
                        CASE
                            WHEN ? = 'CLOSED'
                            THEN COALESCE(
                                closed_at,
                                CURRENT_TIMESTAMP
                            )
                            ELSE NULL
                        END,

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    normalized_activity,
                    normalized_activity,
                    opportunity_id,
                ),
            )

        conn.commit()


def mark_opportunity_closed(
    opportunity_id: int,
):
    """
    Mark an opportunity as closed/stale.
    """

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE opportunities

            SET
                activity_status =
                    'CLOSED',

                closed_at =
                    CURRENT_TIMESTAMP,

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                opportunity_id,
            ),
        )

        conn.commit()


# ============================================================
# EVALUATIONS
# ============================================================

def create_evaluation(
    opportunity_id: int,

    personal_fit_score=None,
    learning_value=None,
    portfolio_value=None,
    effort_score=None,
    risk_score=None,
    overall_score=None,

    recommendation=None,

    reasoning=None,
    why_recommendation=None,

    requirements_analysis=None,
    personal_fit_analysis=None,
    effort_risk_analysis=None,

    why_not_analysis=None,
    what_could_change_decision=None,

    estimated_effort=None,
    time_pressure=None,

    risks=None,
    opportunity_cost=None,

    next_actions=None,

    research_output=None,
    personal_fit_output=None,
    risk_output=None,
    decision_output=None,
    agent_output=None,

    model_info=None,

    evaluation_version="1.0",

    value_output=None,
):
    """
    Insert immutable evaluation snapshot.

    Never overwrite previous evaluations.
    """

    personal_fit_score = (
        clamp_score(
            personal_fit_score
        )
    )

    learning_value = (
        clamp_score(
            learning_value
        )
    )

    portfolio_value = (
        clamp_score(
            portfolio_value
        )
    )

    effort_score = (
        clamp_score(
            effort_score
        )
    )

    risk_score = (
        clamp_score(
            risk_score
        )
    )

    overall_score = (
        clamp_score(
            overall_score
        )
    )

    if recommendation is not None:

        recommendation = (
            normalize_recommendation(
                recommendation
            )
        )

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO evaluations (
                opportunity_id,

                personal_fit_score,
                learning_value,
                portfolio_value,
                effort_score,
                risk_score,
                overall_score,

                recommendation,

                reasoning,
                why_recommendation,

                requirements_analysis,
                personal_fit_analysis,
                effort_risk_analysis,

                why_not_analysis,
                what_could_change_decision,

                estimated_effort,
                time_pressure,

                risks,
                opportunity_cost,

                next_actions,

                research_output,
                personal_fit_output,
                value_output,
                risk_output,
                decision_output,
                agent_output,

                model_info,

                evaluation_version
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                opportunity_id,

                personal_fit_score,
                learning_value,
                portfolio_value,
                effort_score,
                risk_score,
                overall_score,

                recommendation,

                reasoning,
                why_recommendation,

                to_json(
                    requirements_analysis
                    if requirements_analysis is not None
                    else []
                ),

                to_json(
                    personal_fit_analysis
                    if personal_fit_analysis is not None
                    else {}
                ),

                to_json(
                    effort_risk_analysis
                    if effort_risk_analysis is not None
                    else {}
                ),

                why_not_analysis,
                what_could_change_decision,

                estimated_effort,
                time_pressure,

                to_json(
                    risks
                    or []
                ),

                opportunity_cost,

                to_json(
                    next_actions
                    or []
                ),

                to_json(
                    research_output
                    or {}
                ),

                to_json(
                    personal_fit_output
                    or {}
                ),

                to_json(
                    value_output
                    or {}
                ),

                to_json(
                    risk_output
                    or {}
                ),

                to_json(
                    decision_output
                    or {}
                ),

                to_json(
                    agent_output
                    or {}
                ),

                to_json(
                    model_info
                    or {}
                ),

                evaluation_version,
            ),
        )

        conn.commit()

        return cursor.lastrowid


def get_latest_evaluation(
    opportunity_id: int,
):
    """
    Return newest evaluation snapshot.
    """

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM evaluations

            WHERE opportunity_id = ?

            ORDER BY
                created_at DESC,
                id DESC

            LIMIT 1
            """,
            (
                opportunity_id,
            ),
        ).fetchone()


def get_evaluations(
    opportunity_id: int,
):
    """
    Full re-evaluation history.
    """

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM evaluations

            WHERE opportunity_id = ?

            ORDER BY
                created_at DESC,
                id DESC
            """,
            (
                opportunity_id,
            ),
        ).fetchall()


# ============================================================
# PIPELINE STATE
# ============================================================

PIPELINE_STATUS_PENDING = "PENDING"
PIPELINE_STATUS_RUNNING = "RUNNING"
PIPELINE_STATUS_FAILED = "FAILED"
PIPELINE_STATUS_COMPLETED = "COMPLETED"

PIPELINE_STAGE_DISCOVERY = "DISCOVERY"
PIPELINE_STAGE_RESEARCH = "RESEARCH"
PIPELINE_STAGE_PERSONAL_FIT = "PERSONAL_FIT"
PIPELINE_STAGE_VALUE = "VALUE"
PIPELINE_STAGE_EFFORT_RISK = "EFFORT_RISK"
PIPELINE_STAGE_DECISION = "DECISION"
PIPELINE_STAGE_COMPLETED = "COMPLETED"

VALID_PIPELINE_STATUSES = {
    PIPELINE_STATUS_PENDING,
    PIPELINE_STATUS_RUNNING,
    PIPELINE_STATUS_FAILED,
    PIPELINE_STATUS_COMPLETED,
}

PIPELINE_STAGE_COLUMNS = {
    PIPELINE_STAGE_RESEARCH: (
        "research_status",
        "research_output",
    ),
    PIPELINE_STAGE_PERSONAL_FIT: (
        "personal_fit_status",
        "personal_fit_output",
    ),
    PIPELINE_STAGE_VALUE: (
        "value_status",
        "value_output",
    ),
    PIPELINE_STAGE_EFFORT_RISK: (
        "effort_risk_status",
        "risk_output",
    ),
    PIPELINE_STAGE_DECISION: (
        "decision_status",
        "decision_output",
    ),
}


def ensure_pipeline_state(
    opportunity_id: int,
):
    """Create the resumable pipeline-state row if absent."""

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO opportunity_pipeline_state (
                opportunity_id
            )
            VALUES (?)
            ON CONFLICT(opportunity_id)
            DO NOTHING
            """,
            (
                opportunity_id,
            ),
        )
        conn.commit()

    return get_pipeline_state(
        opportunity_id
    )


def get_pipeline_state(
    opportunity_id: int,
):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM opportunity_pipeline_state
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            ),
        ).fetchone()


def mark_pipeline_stage_started(
    opportunity_id: int,
    stage: str,
):
    """Mark one agent stage as RUNNING."""

    stage = clean_text(stage).upper()

    if stage not in PIPELINE_STAGE_COLUMNS:
        raise ValueError(
            f"Unsupported pipeline stage: {stage}"
        )

    status_column, _ = (
        PIPELINE_STAGE_COLUMNS[stage]
    )

    ensure_pipeline_state(
        opportunity_id
    )

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE opportunity_pipeline_state
            SET
                pipeline_status = ?,
                current_stage = ?,
                {status_column} = ?,
                last_error = NULL,
                last_error_stage = NULL,
                started_at = COALESCE(
                    started_at,
                    CURRENT_TIMESTAMP
                ),
                last_attempt_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE opportunity_id = ?
            """,
            (
                PIPELINE_STATUS_RUNNING,
                stage,
                PIPELINE_STATUS_RUNNING,
                opportunity_id,
            ),
        )
        conn.commit()


def mark_pipeline_stage_completed(
    opportunity_id: int,
    stage: str,
    output=None,
):
    """Persist one completed agent output immediately."""

    stage = clean_text(stage).upper()

    if stage not in PIPELINE_STAGE_COLUMNS:
        raise ValueError(
            f"Unsupported pipeline stage: {stage}"
        )

    status_column, output_column = (
        PIPELINE_STAGE_COLUMNS[stage]
    )

    ensure_pipeline_state(
        opportunity_id
    )

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE opportunity_pipeline_state
            SET
                pipeline_status = ?,
                current_stage = ?,
                {status_column} = ?,
                {output_column} = ?,
                last_error = NULL,
                last_error_stage = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE opportunity_id = ?
            """,
            (
                PIPELINE_STATUS_RUNNING,
                stage,
                PIPELINE_STATUS_COMPLETED,
                to_json(output or {}),
                opportunity_id,
            ),
        )
        conn.commit()


def mark_pipeline_stage_failed(
    opportunity_id: int,
    stage: str,
    error,
):
    """Record a failed stage without losing earlier outputs."""

    stage = clean_text(stage).upper()

    if stage not in PIPELINE_STAGE_COLUMNS:
        raise ValueError(
            f"Unsupported pipeline stage: {stage}"
        )

    status_column, _ = (
        PIPELINE_STAGE_COLUMNS[stage]
    )

    ensure_pipeline_state(
        opportunity_id
    )

    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE opportunity_pipeline_state
            SET
                pipeline_status = ?,
                current_stage = ?,
                {status_column} = ?,
                last_error = ?,
                last_error_stage = ?,
                retry_count = retry_count + 1,
                last_attempt_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE opportunity_id = ?
            """,
            (
                PIPELINE_STATUS_FAILED,
                stage,
                PIPELINE_STATUS_FAILED,
                clean_text(error),
                stage,
                opportunity_id,
            ),
        )
        conn.commit()


def mark_pipeline_completed(
    opportunity_id: int,
):
    ensure_pipeline_state(
        opportunity_id
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE opportunity_pipeline_state
            SET
                pipeline_status = 'COMPLETED',
                current_stage = 'COMPLETED',
                decision_status = 'COMPLETED',
                last_error = NULL,
                last_error_stage = NULL,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            ),
        )
        conn.commit()


def reset_pipeline_state(
    opportunity_id: int,
):
    """Reset agent processing only; does not delete the opportunity."""

    ensure_pipeline_state(
        opportunity_id
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE opportunity_pipeline_state
            SET
                pipeline_status = 'PENDING',
                current_stage = 'DISCOVERY',
                research_status = 'PENDING',
                personal_fit_status = 'PENDING',
                value_status = 'PENDING',
                effort_risk_status = 'PENDING',
                decision_status = 'PENDING',
                research_output = '{}',
                personal_fit_output = '{}',
                value_output = '{}',
                risk_output = '{}',
                decision_output = '{}',
                last_error = NULL,
                last_error_stage = NULL,
                retry_count = 0,
                started_at = NULL,
                completed_at = NULL,
                last_attempt_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE opportunity_id = ?
            """,
            (
                opportunity_id,
            ),
        )
        conn.commit()


def get_resumable_pipeline_opportunities(
    user_id: int,
    limit: int = 50,
):
    """Return opportunities whose agent pipeline is not complete."""

    limit = max(
        1,
        min(int(limit), 500),
    )

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                o.*,
                p.pipeline_status,
                p.current_stage,
                p.research_status,
                p.personal_fit_status,
                p.value_status,
                p.effort_risk_status,
                p.decision_status,
                p.last_error,
                p.last_error_stage,
                p.retry_count,
                p.last_attempt_at
            FROM opportunities o
            JOIN opportunity_pipeline_state p
              ON p.opportunity_id = o.id
            WHERE o.user_id = ?
              AND p.pipeline_status <> 'COMPLETED'
              AND o.status NOT IN (
                  'NOT_INTERESTED',
                  'ARCHIVED'
              )
            ORDER BY
                COALESCE(
                    p.last_attempt_at,
                    o.created_at
                ) ASC,
                o.id ASC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()


# ============================================================
# HISTORY
# ============================================================

def add_history(
    user_id: int,
    opportunity_id: int,
    old_status: Optional[str],
    new_status: Optional[str],
    action: str,
    note: Optional[str] = None,
):
    """
    Add workflow audit event.
    """

    with get_connection() as conn:

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note,
            ),
        )

        conn.commit()


def set_opportunity_status(
    user_id: int,
    opportunity_id: int,
    new_status: str,
    action: str,
    note: Optional[str] = None,
):
    """
    Ownership-safe workflow status transition.
    """

    new_status = normalize_status(
        new_status
    )

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT status

            FROM opportunities

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        ).fetchone()

        if not row:
            raise ValueError(
                "Opportunity not found."
            )

        old_status = (
            row["status"]
        )

        if old_status == new_status:
            return False

        conn.execute(
            """
            UPDATE opportunities

            SET
                status = ?,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
              AND user_id = ?
            """,
            (
                new_status,
                opportunity_id,
                user_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note,
            ),
        )

        conn.commit()

        return True


# ============================================================
# WATCHLIST
# ============================================================

def add_to_watchlist(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Add opportunity to Watch.
    """

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT status

            FROM opportunities

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        ).fetchone()

        if not row:
            raise ValueError(
                "Opportunity not found."
            )

        old_status = (
            row["status"]
        )

        conn.execute(
            """
            INSERT INTO watchlist (
                user_id,
                opportunity_id
            )

            VALUES (?, ?)

            ON CONFLICT(
                user_id,
                opportunity_id
            )
            DO UPDATE SET

                monitoring_enabled = 1,

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                user_id,
                opportunity_id,
            ),
        )

        conn.execute(
            """
            UPDATE opportunities

            SET
                status =
                    'WATCHING',

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        )

        if (
            old_status
            != STATUS_WATCHING
        ):

            conn.execute(
                """
                INSERT INTO opportunity_history (
                    user_id,
                    opportunity_id,
                    old_status,
                    new_status,
                    action,
                    note
                )

                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    opportunity_id,
                    old_status,
                    STATUS_WATCHING,
                    ACTION_WATCH,
                    note,
                ),
            )

        conn.commit()


def remove_from_watchlist(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Remove Watch state.

    Workflow returns to DISCOVERED.
    """

    with get_connection() as conn:

        opportunity = conn.execute(
            """
            SELECT status

            FROM opportunities

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        ).fetchone()

        if not opportunity:
            raise ValueError(
                "Opportunity not found."
            )

        conn.execute(
            """
            DELETE FROM watchlist

            WHERE user_id = ?
              AND opportunity_id = ?
            """,
            (
                user_id,
                opportunity_id,
            ),
        )

        conn.execute(
            """
            UPDATE opportunities

            SET
                status =
                    'DISCOVERED',

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                opportunity["status"],
                STATUS_DISCOVERED,
                ACTION_UNWATCH,
                note,
            ),
        )

        conn.commit()


def get_watchlist(
    user_id: int,
):
    """
    Return active watchlist.
    """

    with get_connection() as conn:

        return conn.execute(
            """
            SELECT

                o.*,

                w.monitoring_enabled,

                w.last_checked_at,

                w.deadline_changed,

                w.requirements_changed,

                w.created_at
                    AS watch_created_at,

                (
                    SELECT s.source_url

                    FROM opportunity_sources s

                    WHERE
                        s.opportunity_id =
                            o.id

                    ORDER BY
                        s.is_primary DESC,
                        s.first_seen_at ASC,
                        s.id ASC

                    LIMIT 1

                ) AS primary_url

            FROM watchlist w

            JOIN opportunities o
              ON o.id =
                 w.opportunity_id

            WHERE w.user_id = ?
              AND w.monitoring_enabled = 1

            ORDER BY
                w.created_at DESC,
                w.id DESC
            """,
            (
                user_id,
            ),
        ).fetchall()


# ============================================================
# INTERESTED
# ============================================================

def mark_interested(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """Mark an opportunity as user INTERESTED."""

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT status
            FROM opportunities
            WHERE id = ? AND user_id = ?
            """,
            (opportunity_id, user_id),
        ).fetchone()

        if not row:
            raise ValueError("Opportunity not found.")

        old_status = row["status"]

        if old_status == STATUS_INTERESTED:
            return False

        # Interested and Watching are mutually exclusive workflow
        # states. Remove any watchlist row when moving to Interested.
        conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND opportunity_id = ?",
            (user_id, opportunity_id),
        )

        conn.execute(
            """
            UPDATE opportunities
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (STATUS_INTERESTED, opportunity_id, user_id),
        )

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id, opportunity_id, old_status, new_status, action, note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                old_status,
                STATUS_INTERESTED,
                ACTION_INTERESTED,
                note,
            ),
        )
        conn.commit()
        return True


def remove_interested(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """Return an INTERESTED opportunity to DISCOVERED."""

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT status
            FROM opportunities
            WHERE id = ? AND user_id = ?
            """,
            (opportunity_id, user_id),
        ).fetchone()

        if not row:
            raise ValueError("Opportunity not found.")

        old_status = row["status"]
        if old_status != STATUS_INTERESTED:
            return False

        conn.execute(
            """
            UPDATE opportunities
            SET status = 'DISCOVERED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (opportunity_id, user_id),
        )

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id, opportunity_id, old_status, new_status, action, note
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                old_status,
                STATUS_DISCOVERED,
                ACTION_UNINTERESTED,
                note,
            ),
        )
        conn.commit()
        return True


def get_interested_opportunities(
    user_id: int,
    date_from=None,
    date_to=None,
    sort_by: str = SORT_NEWEST,
    search_text: Optional[str] = None,
):
    """Return opportunities explicitly marked INTERESTED by the user."""

    conditions = [
        "o.user_id = ?",
        "o.status = 'INTERESTED'",
    ]
    params = [user_id]

    if date_from is not None:
        conditions.append("DATE(o.first_found_at) >= DATE(?)")
        params.append(str(date_from))

    if date_to is not None:
        conditions.append("DATE(o.first_found_at) <= DATE(?)")
        params.append(str(date_to))

    if search_text:
        term = "%" + clean_text(search_text) + "%"
        conditions.append(
            "(o.title LIKE ? OR o.organization LIKE ? OR o.location LIKE ? OR o.description LIKE ?)"
        )
        params.extend([term, term, term, term])

    order_map = {
        SORT_NEWEST: "o.first_found_at DESC, o.id DESC",
        SORT_OLDEST: "o.first_found_at ASC, o.id ASC",
        SORT_HIGHEST_SCORE: (
            "CASE WHEN o.score IS NULL THEN 1 ELSE 0 END, "
            "o.score DESC, o.first_found_at DESC"
        ),
        SORT_LOWEST_SCORE: (
            "CASE WHEN o.score IS NULL THEN 1 ELSE 0 END, "
            "o.score ASC, o.first_found_at DESC"
        ),
    }
    order_clause = order_map.get(sort_by, order_map[SORT_NEWEST])

    query = f"""
        SELECT
            o.*,
            (
                SELECT s.source_url
                FROM opportunity_sources s
                WHERE s.opportunity_id = o.id
                ORDER BY s.is_primary DESC, s.first_seen_at ASC, s.id ASC
                LIMIT 1
            ) AS primary_url
        FROM opportunities o
        WHERE {" AND ".join(conditions)}
        ORDER BY {order_clause}
    """

    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


# ============================================================
# WORKFLOW ACTIONS
# ============================================================

def mark_not_interested(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Remove from active Dashboard and Watchlist.
    """

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT status

            FROM opportunities

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        ).fetchone()

        if not row:
            raise ValueError(
                "Opportunity not found."
            )

        old_status = (
            row["status"]
        )

        conn.execute(
            """
            DELETE FROM watchlist

            WHERE user_id = ?
              AND opportunity_id = ?
            """,
            (
                user_id,
                opportunity_id,
            ),
        )

        conn.execute(
            """
            UPDATE opportunities

            SET
                status =
                    'NOT_INTERESTED',

                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
              AND user_id = ?
            """,
            (
                opportunity_id,
                user_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO opportunity_history (
                user_id,
                opportunity_id,
                old_status,
                new_status,
                action,
                note
            )

            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                opportunity_id,
                old_status,
                STATUS_NOT_INTERESTED,
                ACTION_NOT_INTERESTED,
                note,
            ),
        )

        conn.commit()


def mark_applied(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Mark opportunity APPLIED.
    """

    return set_opportunity_status(
        user_id=user_id,
        opportunity_id=
            opportunity_id,
        new_status=
            STATUS_APPLIED,
        action=
            ACTION_APPLIED,
        note=note,
    )


def archive_opportunity(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Archive opportunity.
    """

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM watchlist

            WHERE user_id = ?
              AND opportunity_id = ?
            """,
            (
                user_id,
                opportunity_id,
            ),
        )

        conn.commit()

    return set_opportunity_status(
        user_id=user_id,
        opportunity_id=
            opportunity_id,
        new_status=
            STATUS_ARCHIVED,
        action=
            ACTION_ARCHIVED,
        note=note,
    )


def restore_opportunity(
    user_id: int,
    opportunity_id: int,
    note: Optional[str] = None,
):
    """
    Restore an archived/not-interested opportunity
    to DISCOVERED.
    """

    return set_opportunity_status(
        user_id=user_id,
        opportunity_id=
            opportunity_id,
        new_status=
            STATUS_DISCOVERED,
        action=
            ACTION_RESTORED,
        note=note,
    )


# ============================================================
# USER OPPORTUNITIES
# ============================================================

def get_user_opportunities(
    user_id: int,
    include_inactive_workflow=False,
):
    """
    General opportunity listing.
    """

    with get_connection() as conn:

        if include_inactive_workflow:

            query = """
                SELECT *
                FROM opportunities

                WHERE user_id = ?

                ORDER BY
                    first_found_at DESC,
                    id DESC
            """

        else:

            query = """
                SELECT *
                FROM opportunities

                WHERE user_id = ?

                  AND status NOT IN (
                      'NOT_INTERESTED',
                      'ARCHIVED'
                  )

                ORDER BY
                    first_found_at DESC,
                    id DESC
            """

        return conn.execute(
            query,
            (
                user_id,
            ),
        ).fetchall()


# ============================================================
# DASHBOARD QUERY
# ============================================================

def get_dashboard_opportunities(
    user_id: int,

    filter_name: str =
        DASHBOARD_FILTER_ALL,

    category: Optional[str] = None,

    date_from=None,
    date_to=None,

    sort_by: str =
        SORT_NEWEST,

    search_text: Optional[str] = None,
):
    """
    Main active Dashboard query.

    NOT_INTERESTED and ARCHIVED are excluded.
    """

    conditions = [
        "o.user_id = ?",

        """
        o.status NOT IN (
            'NOT_INTERESTED',
            'ARCHIVED'
        )
        """,
    ]

    params = [
        user_id,
    ]

    normalized_filter = (
        clean_text(
            filter_name
        ).lower()
    )

    if (
        normalized_filter
        == DASHBOARD_FILTER_NEW.lower()
    ):

        conditions.append(
            """
            o.status = 'DISCOVERED'
            AND o.is_new = 1
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_PURSUE.lower()
    ):

        conditions.append(
            """
            o.recommendation =
                'PURSUE'
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_REVIEW.lower()
    ):

        conditions.append(
            """
            o.recommendation =
                'REVIEW'
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_REJECTED.lower()
    ):

        conditions.append(
            """
            o.recommendation =
                'REJECT'
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_INTERESTED.lower()
    ):

        conditions.append(
            """
            o.status =
                'INTERESTED'
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_WATCH.lower()
    ):

        conditions.append(
            """
            o.status =
                'WATCHING'
            """
        )

    elif (
        normalized_filter
        == DASHBOARD_FILTER_APPLIED.lower()
    ):

        conditions.append(
            """
            o.status =
                'APPLIED'
            """
        )

    if category:

        category = (
            normalize_category(
                category
            )
        )

        conditions.append(
            "o.category = ?"
        )

        params.append(
            category
        )

    if date_from is not None:

        conditions.append(
            """
            DATE(o.first_found_at)
            >= DATE(?)
            """
        )

        params.append(
            str(date_from)
        )

    if date_to is not None:

        conditions.append(
            """
            DATE(o.first_found_at)
            <= DATE(?)
            """
        )

        params.append(
            str(date_to)
        )

    if search_text:

        term = (
            "%"
            + clean_text(
                search_text
            )
            + "%"
        )

        conditions.append(
            """
            (
                o.title LIKE ?
                OR o.organization LIKE ?
                OR o.location LIKE ?
                OR o.description LIKE ?
            )
            """
        )

        params.extend(
            [
                term,
                term,
                term,
                term,
            ]
        )

    order_map = {

        SORT_NEWEST:
            """
            o.first_found_at DESC,
            o.id DESC
            """,

        SORT_OLDEST:
            """
            o.first_found_at ASC,
            o.id ASC
            """,

        SORT_HIGHEST_SCORE:
            """
            CASE
                WHEN o.score IS NULL
                THEN 1
                ELSE 0
            END,
            o.score DESC,
            o.first_found_at DESC
            """,

        SORT_LOWEST_SCORE:
            """
            CASE
                WHEN o.score IS NULL
                THEN 1
                ELSE 0
            END,
            o.score ASC,
            o.first_found_at DESC
            """,
    }

    order_clause = (
        order_map.get(
            sort_by,
            order_map[
                SORT_NEWEST
            ],
        )
    )

    query = f"""
        SELECT

            o.*,

            (
                SELECT s.source_url

                FROM opportunity_sources s

                WHERE
                    s.opportunity_id =
                        o.id

                ORDER BY
                    s.is_primary DESC,
                    s.first_seen_at ASC,
                    s.id ASC

                LIMIT 1

            ) AS primary_url

        FROM opportunities o

        WHERE
            {" AND ".join(conditions)}

        ORDER BY
            {order_clause}
    """

    with get_connection() as conn:

        return conn.execute(
            query,
            params,
        ).fetchall()


# ============================================================
# HISTORY QUERY
# ============================================================

def get_history(
    user_id: int,

    action_filter: str =
        HISTORY_FILTER_ALL,

    date_from=None,
    date_to=None,

    sort_by: str =
        SORT_NEWEST,

    search_text: Optional[str] = None,
):
    """
    Query workflow history.
    """

    conditions = [
        "h.user_id = ?",
    ]

    params = [
        user_id,
    ]

    action_map = {

        HISTORY_FILTER_INTERESTED:
            ACTION_INTERESTED,

        HISTORY_FILTER_UNINTERESTED:
            ACTION_UNINTERESTED,

        HISTORY_FILTER_WATCH:
            ACTION_WATCH,

        HISTORY_FILTER_UNWATCH:
            ACTION_UNWATCH,

        HISTORY_FILTER_NOT_INTERESTED:
            ACTION_NOT_INTERESTED,

        HISTORY_FILTER_APPLIED:
            ACTION_APPLIED,

        HISTORY_FILTER_ARCHIVED:
            ACTION_ARCHIVED,

        HISTORY_FILTER_RESTORED:
            ACTION_RESTORED,
    }

    if action_filter in action_map:

        conditions.append(
            "h.action = ?"
        )

        params.append(
            action_map[
                action_filter
            ]
        )

    if date_from is not None:

        conditions.append(
            """
            DATE(h.created_at)
            >= DATE(?)
            """
        )

        params.append(
            str(date_from)
        )

    if date_to is not None:

        conditions.append(
            """
            DATE(h.created_at)
            <= DATE(?)
            """
        )

        params.append(
            str(date_to)
        )

    if search_text:

        term = (
            "%"
            + clean_text(
                search_text
            )
            + "%"
        )

        conditions.append(
            """
            (
                o.title LIKE ?
                OR o.organization LIKE ?
                OR h.note LIKE ?
            )
            """
        )

        params.extend(
            [
                term,
                term,
                term,
            ]
        )

    if sort_by == SORT_OLDEST:

        order_clause = (
            """
            h.created_at ASC,
            h.id ASC
            """
        )

    else:

        order_clause = (
            """
            h.created_at DESC,
            h.id DESC
            """
        )

    query = f"""
        SELECT

            h.id
                AS history_id,

            h.old_status,
            h.new_status,
            h.action,
            h.note,

            h.created_at
                AS action_date,

            o.id
                AS opportunity_id,

            o.title,
            o.organization,
            o.category,

            o.location,
            o.work_arrangement,

            o.deadline,
            o.reward,

            o.score,
            o.recommendation,

            o.activity_status,

            (
                SELECT s.source_url

                FROM opportunity_sources s

                WHERE
                    s.opportunity_id =
                        o.id

                ORDER BY
                    s.is_primary DESC,
                    s.first_seen_at ASC,
                    s.id ASC

                LIMIT 1

            ) AS primary_url

        FROM opportunity_history h

        JOIN opportunities o
          ON o.id =
             h.opportunity_id

        WHERE
            {" AND ".join(conditions)}

        ORDER BY
            {order_clause}
    """

    with get_connection() as conn:

        return conn.execute(
            query,
            params,
        ).fetchall()


# ============================================================
# DASHBOARD METRICS
# ============================================================

def get_dashboard_metrics(
    user_id: int,
):
    """
    Metrics for active opportunities.
    """

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT

                COUNT(*)
                    AS opportunities,

                SUM(
                    CASE
                        WHEN
                            status =
                                'DISCOVERED'

                            AND
                            is_new = 1

                        THEN 1
                        ELSE 0
                    END
                )
                    AS new,

                SUM(
                    CASE
                        WHEN
                            recommendation =
                                'PURSUE'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS pursue,

                SUM(
                    CASE
                        WHEN
                            recommendation =
                                'REVIEW'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS review,

                SUM(
                    CASE
                        WHEN
                            recommendation =
                                'REJECT'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS rejected,

                SUM(
                    CASE
                        WHEN
                            status =
                                'INTERESTED'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS interested,

                SUM(
                    CASE
                        WHEN
                            status =
                                'WATCHING'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS watching,

                SUM(
                    CASE
                        WHEN
                            status =
                                'APPLIED'

                        THEN 1
                        ELSE 0
                    END
                )
                    AS applied

            FROM opportunities

            WHERE user_id = ?

              AND status NOT IN (
                  'NOT_INTERESTED',
                  'ARCHIVED'
              )
            """,
            (
                user_id,
            ),
        ).fetchone()

        return {
            "opportunities":
                row["opportunities"]
                or 0,

            "new":
                row["new"]
                or 0,

            "pursue":
                row["pursue"]
                or 0,

            "review":
                row["review"]
                or 0,

            "rejected":
                row["rejected"]
                or 0,

            "interested":
                row["interested"]
                or 0,

            "watching":
                row["watching"]
                or 0,

            "applied":
                row["applied"]
                or 0,
        }


# ============================================================
# TEST / SEED DATE HELPERS
# ============================================================

def set_opportunity_first_found(
    opportunity_id: int,
    timestamp,
):
    """
    Seed/test helper for date-filter testing.
    """

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE opportunities

            SET
                first_found_at = ?,
                last_seen_at = ?,
                updated_at =
                    CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                timestamp,
                timestamp,
                opportunity_id,
            ),
        )

        conn.commit()


def set_history_date(
    history_id: int,
    timestamp,
):
    """
    Seed/test helper.
    """

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE opportunity_history

            SET created_at = ?

            WHERE id = ?
            """,
            (
                timestamp,
                history_id,
            ),
        )

        conn.commit()


# ============================================================
# DATABASE SUMMARY
# ============================================================

def get_database_summary():
    """
    Debug helper.
    """

    tables = [
        "users",
        "profiles",
        "documents",
        "opportunities",
        "opportunity_sources",
        "evaluations",
        "opportunity_pipeline_state",
        "watchlist",
        "opportunity_history",
    ]

    summary = {}

    with get_connection() as conn:

        for table in tables:

            count = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM {table}
                """
            ).fetchone()[0]

            summary[
                table
            ] = count

    return summary


# ============================================================
# DEVELOPMENT RESET
# ============================================================

def reset_database():
    """
    DEVELOPMENT ONLY.

    Deletes the SQLite file and recreates schema.
    """

    if DB_PATH.exists():
        DB_PATH.unlink()

    init_db()


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    init_db()

    print(
        "PURSUIT SQLite database initialized."
    )

    print(
        f"Path: {DB_PATH.resolve()}"
    )

    print()

    for (
        table,
        count,
    ) in get_database_summary().items():

        print(
            f"{table}: {count}"
        )







        





# app/constants.py


# ============================================================
# OPPORTUNITY CATEGORIES
# ============================================================

CATEGORY_JOB = "JOB"
CATEGORY_FREELANCE = "FREELANCE"
CATEGORY_HACKATHON = "HACKATHON"
CATEGORY_GRANT = "GRANT"
CATEGORY_PROGRAM = "PROGRAM"
CATEGORY_OTHER = "OTHER"

VALID_CATEGORIES = {
    CATEGORY_JOB,
    CATEGORY_FREELANCE,
    CATEGORY_HACKATHON,
    CATEGORY_GRANT,
    CATEGORY_PROGRAM,
    CATEGORY_OTHER,
}


# Friendly UI labels

CATEGORY_LABELS = {
    CATEGORY_JOB: "Job",
    CATEGORY_FREELANCE: "Freelance",
    CATEGORY_HACKATHON: "Hackathon & Competition",
    CATEGORY_GRANT: "Grant & Funding",
    CATEGORY_PROGRAM: "Program & Learning",
    CATEGORY_OTHER: "Other",
}


# ============================================================
# AI RECOMMENDATIONS
# ============================================================

RECOMMENDATION_PURSUE = "PURSUE"
RECOMMENDATION_REVIEW = "REVIEW"
RECOMMENDATION_REJECT = "REJECT"

VALID_RECOMMENDATIONS = {
    RECOMMENDATION_PURSUE,
    RECOMMENDATION_REVIEW,
    RECOMMENDATION_REJECT,
}


RECOMMENDATION_LABELS = {
    RECOMMENDATION_PURSUE: "Pursue",
    RECOMMENDATION_REVIEW: "Review",
    RECOMMENDATION_REJECT: "Reject",
}


# ============================================================
# WORKFLOW STATUS
# ============================================================

STATUS_DISCOVERED = "DISCOVERED"
STATUS_WATCHING = "WATCHING"
STATUS_APPLIED = "APPLIED"
STATUS_NOT_INTERESTED = "NOT_INTERESTED"
STATUS_ARCHIVED = "ARCHIVED"

VALID_STATUSES = {
    STATUS_DISCOVERED,
    STATUS_WATCHING,
    STATUS_APPLIED,
    STATUS_NOT_INTERESTED,
    STATUS_ARCHIVED,
}


STATUS_LABELS = {
    STATUS_DISCOVERED: "New",
    STATUS_WATCHING: "Watching",
    STATUS_APPLIED: "Applied",
    STATUS_NOT_INTERESTED: "Not Interested",
    STATUS_ARCHIVED: "Archived",
}


# ============================================================
# HISTORY ACTIONS
# ============================================================

ACTION_WATCH = "WATCH"
ACTION_UNWATCH = "UNWATCH"
ACTION_APPLIED = "APPLIED"
ACTION_NOT_INTERESTED = "NOT_INTERESTED"
ACTION_ARCHIVED = "ARCHIVED"
ACTION_RESTORED = "RESTORED"

VALID_HISTORY_ACTIONS = {
    ACTION_WATCH,
    ACTION_UNWATCH,
    ACTION_APPLIED,
    ACTION_NOT_INTERESTED,
    ACTION_ARCHIVED,
    ACTION_RESTORED,
}


ACTION_LABELS = {
    ACTION_WATCH: "Watch",
    ACTION_UNWATCH: "Unwatch",
    ACTION_APPLIED: "Applied",
    ACTION_NOT_INTERESTED: "Not Interested",
    ACTION_ARCHIVED: "Archived",
    ACTION_RESTORED: "Restored",
}


# ============================================================
# WORK ARRANGEMENT
# ============================================================

WORK_REMOTE = "REMOTE"
WORK_HYBRID = "HYBRID"
WORK_ONSITE = "ONSITE"
WORK_UNKNOWN = "UNKNOWN"

VALID_WORK_ARRANGEMENTS = {
    WORK_REMOTE,
    WORK_HYBRID,
    WORK_ONSITE,
    WORK_UNKNOWN,
}


WORK_ARRANGEMENT_LABELS = {
    WORK_REMOTE: "Remote",
    WORK_HYBRID: "Hybrid",
    WORK_ONSITE: "On-site",
    WORK_UNKNOWN: "Unknown",
}


# ============================================================
# SOURCE TYPES
# ============================================================

SOURCE_EMPLOYER = "EMPLOYER"
SOURCE_ATS = "ATS"
SOURCE_PROGRAM = "PROGRAM"
SOURCE_HACKATHON = "HACKATHON"
SOURCE_GRANT = "GRANT"
SOURCE_FREELANCE = "FREELANCE"
SOURCE_OTHER = "OTHER"

VALID_SOURCE_TYPES = {
    SOURCE_EMPLOYER,
    SOURCE_ATS,
    SOURCE_PROGRAM,
    SOURCE_HACKATHON,
    SOURCE_GRANT,
    SOURCE_FREELANCE,
    SOURCE_OTHER,
}


# ============================================================
# OPPORTUNITY ACTIVITY STATE
# ============================================================

OPPORTUNITY_ACTIVE = "ACTIVE"
OPPORTUNITY_CLOSED = "CLOSED"
OPPORTUNITY_UNKNOWN = "UNKNOWN"

VALID_OPPORTUNITY_ACTIVITY = {
    OPPORTUNITY_ACTIVE,
    OPPORTUNITY_CLOSED,
    OPPORTUNITY_UNKNOWN,
}


# ============================================================
# PERSONAL FIT STATUS
# ============================================================

FIT_MATCH = "MATCH"
FIT_PARTIAL = "PARTIAL"
FIT_NO_MATCH = "NO_MATCH"
FIT_UNKNOWN = "UNKNOWN"

VALID_FIT_STATUSES = {
    FIT_MATCH,
    FIT_PARTIAL,
    FIT_NO_MATCH,
    FIT_UNKNOWN,
}


FIT_STATUS_LABELS = {
    FIT_MATCH: "Match",
    FIT_PARTIAL: "Partial",
    FIT_NO_MATCH: "No Match",
    FIT_UNKNOWN: "Unknown",
}


# ============================================================
# RISK SEVERITY
# ============================================================

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"

VALID_RISK_LEVELS = {
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
}


# ============================================================
# EFFORT LEVEL
# ============================================================

EFFORT_LOW = "LOW"
EFFORT_MEDIUM = "MEDIUM"
EFFORT_HIGH = "HIGH"
EFFORT_UNKNOWN = "UNKNOWN"

VALID_EFFORT_LEVELS = {
    EFFORT_LOW,
    EFFORT_MEDIUM,
    EFFORT_HIGH,
    EFFORT_UNKNOWN,
}


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_recommendation(value):
    """
    Convert model/UI variants into canonical DB values.

    Examples:
        pursue -> PURSUE
        Review -> REVIEW
        INVESTIGATE -> REVIEW
        rejected -> REJECT
    """

    if value is None:
        return None

    normalized = str(value).strip().upper()

    aliases = {
        "PURSUE": RECOMMENDATION_PURSUE,
        "PURSUED": RECOMMENDATION_PURSUE,

        "REVIEW": RECOMMENDATION_REVIEW,
        "INVESTIGATE": RECOMMENDATION_REVIEW,
        "INVESTIGATION": RECOMMENDATION_REVIEW,

        "REJECT": RECOMMENDATION_REJECT,
        "REJECTED": RECOMMENDATION_REJECT,
    }

    result = aliases.get(normalized)

    if result is None:
        raise ValueError(
            f"Unknown recommendation: {value}"
        )

    return result


def normalize_status(value):
    """
    Convert workflow variants into canonical DB values.
    """

    if value is None:
        return STATUS_DISCOVERED

    normalized = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    aliases = {
        "NEW": STATUS_DISCOVERED,
        "DISCOVERED": STATUS_DISCOVERED,

        "WATCH": STATUS_WATCHING,
        "WATCHING": STATUS_WATCHING,

        "APPLY": STATUS_APPLIED,
        "APPLIED": STATUS_APPLIED,

        "NOT_INTERESTED": STATUS_NOT_INTERESTED,
        "NOTINTERESTED": STATUS_NOT_INTERESTED,

        "ARCHIVE": STATUS_ARCHIVED,
        "ARCHIVED": STATUS_ARCHIVED,
    }

    result = aliases.get(normalized)

    if result is None:
        raise ValueError(
            f"Unknown opportunity status: {value}"
        )

    return result


def normalize_category(value):
    """
    Normalize agent/search category variants.
    """

    if value is None:
        return CATEGORY_OTHER

    normalized = (
        str(value)
        .strip()
        .upper()
        .replace("&", "AND")
        .replace("/", " ")
        .replace("-", " ")
    )

    normalized = " ".join(
        normalized.split()
    )

    aliases = {
        "JOB": CATEGORY_JOB,
        "JOBS": CATEGORY_JOB,
        "EMPLOYMENT": CATEGORY_JOB,
        "INTERNSHIP": CATEGORY_JOB,

        "FREELANCE": CATEGORY_FREELANCE,
        "FREELANCING": CATEGORY_FREELANCE,
        "CONTRACT": CATEGORY_FREELANCE,
        "CONTRACT WORK": CATEGORY_FREELANCE,

        "HACKATHON": CATEGORY_HACKATHON,
        "HACKATHONS": CATEGORY_HACKATHON,
        "COMPETITION": CATEGORY_HACKATHON,
        "COMPETITIONS": CATEGORY_HACKATHON,
        "HACKATHONS AND COMPETITIONS":
            CATEGORY_HACKATHON,

        "GRANT": CATEGORY_GRANT,
        "GRANTS": CATEGORY_GRANT,
        "FUNDING": CATEGORY_GRANT,
        "GRANTS AND FUNDING":
            CATEGORY_GRANT,

        "PROGRAM": CATEGORY_PROGRAM,
        "PROGRAMS": CATEGORY_PROGRAM,
        "LEARNING": CATEGORY_PROGRAM,
        "TRAINING": CATEGORY_PROGRAM,
        "COURSE": CATEGORY_PROGRAM,
        "FELLOWSHIP": CATEGORY_PROGRAM,
        "SCHOLARSHIP": CATEGORY_PROGRAM,
        "PROGRAMS AND LEARNING":
            CATEGORY_PROGRAM,

        "OTHER": CATEGORY_OTHER,
        "UNKNOWN": CATEGORY_OTHER,
    }

    return aliases.get(
        normalized,
        CATEGORY_OTHER,
    )


def normalize_work_arrangement(value):
    """
    Normalize remote/hybrid/on-site variants.
    """

    if not value:
        return WORK_UNKNOWN

    normalized = (
        str(value)
        .strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

    aliases = {
        "REMOTE": WORK_REMOTE,
        "WORKFROMHOME": WORK_REMOTE,
        "WFH": WORK_REMOTE,

        "HYBRID": WORK_HYBRID,

        "ONSITE": WORK_ONSITE,
        "ONSITEONLY": WORK_ONSITE,
        "OFFICE": WORK_ONSITE,

        "UNKNOWN": WORK_UNKNOWN,
    }

    return aliases.get(
        normalized,
        WORK_UNKNOWN,
    )


def normalize_fit_status(value):
    """
    Normalize Personal Agent fit labels.
    """

    if not value:
        return FIT_UNKNOWN

    normalized = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
    )

    aliases = {
        "MATCH": FIT_MATCH,
        "MATCHED": FIT_MATCH,

        "PARTIAL": FIT_PARTIAL,
        "PARTIAL_MATCH": FIT_PARTIAL,

        "NO_MATCH": FIT_NO_MATCH,
        "NOMATCH": FIT_NO_MATCH,
        "NOT_MATCHED": FIT_NO_MATCH,

        "UNKNOWN": FIT_UNKNOWN,
        "UNCLEAR": FIT_UNKNOWN,
    }

    return aliases.get(
        normalized,
        FIT_UNKNOWN,
    )


def normalize_risk_level(value):
    if not value:
        return RISK_LOW

    normalized = str(value).strip().upper()

    aliases = {
        "LOW": RISK_LOW,
        "MEDIUM": RISK_MEDIUM,
        "MODERATE": RISK_MEDIUM,
        "HIGH": RISK_HIGH,
    }

    return aliases.get(
        normalized,
        RISK_LOW,
    )


def normalize_effort_level(value):
    if not value:
        return EFFORT_UNKNOWN

    normalized = str(value).strip().upper()

    aliases = {
        "LOW": EFFORT_LOW,
        "MEDIUM": EFFORT_MEDIUM,
        "MODERATE": EFFORT_MEDIUM,
        "HIGH": EFFORT_HIGH,
        "UNKNOWN": EFFORT_UNKNOWN,
    }

    return aliases.get(
        normalized,
        EFFORT_UNKNOWN,
    )


# ============================================================
# SCORE HELPERS
# ============================================================

MIN_SCORE = 0
MAX_SCORE = 100

PURSUE_THRESHOLD = 70
REVIEW_THRESHOLD = 50


def clamp_score(value):
    """
    Safely force numeric scores into 0..100.
    """

    if value is None:
        return None

    try:
        score = int(
            round(float(value))
        )

    except (TypeError, ValueError):
        return None

    return max(
        MIN_SCORE,
        min(
            MAX_SCORE,
            score,
        ),
    )


def recommendation_from_score(score):
    """
    Deterministic recommendation.

    70-100 -> PURSUE
    50-69  -> REVIEW
    0-49   -> REJECT
    """

    score = clamp_score(
        score
    )

    if score is None:
        return None

    if score >= PURSUE_THRESHOLD:
        return RECOMMENDATION_PURSUE

    if score >= REVIEW_THRESHOLD:
        return RECOMMENDATION_REVIEW

    return RECOMMENDATION_REJECT


# ============================================================
# UI FILTER VALUES
# ============================================================

DASHBOARD_FILTER_ALL = "All"
DASHBOARD_FILTER_NEW = "New"
DASHBOARD_FILTER_PURSUE = "Pursue"
DASHBOARD_FILTER_REVIEW = "Review"
DASHBOARD_FILTER_REJECTED = "Rejected"
DASHBOARD_FILTER_WATCH = "Watch"
DASHBOARD_FILTER_APPLIED = "Applied"
DASHBOARD_FILTER_INTERESTED = "Interested"

DASHBOARD_FILTERS = [
    DASHBOARD_FILTER_ALL,
    DASHBOARD_FILTER_NEW,
    DASHBOARD_FILTER_PURSUE,
    DASHBOARD_FILTER_REVIEW,
    DASHBOARD_FILTER_REJECTED,
    DASHBOARD_FILTER_INTERESTED,
    DASHBOARD_FILTER_WATCH,
    DASHBOARD_FILTER_APPLIED,
]

DATE_FILTER_ALL = "All time"
DATE_FILTER_TODAY = "Today"
DATE_FILTER_7_DAYS = "Last 7 days"
DATE_FILTER_30_DAYS = "Last 30 days"
DATE_FILTER_THIS_MONTH = "This month"
DATE_FILTER_CUSTOM = "Custom range"

DATE_FILTERS = [
    DATE_FILTER_ALL,
    DATE_FILTER_TODAY,
    DATE_FILTER_7_DAYS,
    DATE_FILTER_30_DAYS,
    DATE_FILTER_THIS_MONTH,
    DATE_FILTER_CUSTOM,
]


SORT_NEWEST = "Newest first"
SORT_OLDEST = "Oldest first"
SORT_HIGHEST_SCORE = "Highest score"
SORT_LOWEST_SCORE = "Lowest score"

DASHBOARD_SORT_OPTIONS = [
    SORT_NEWEST,
    SORT_OLDEST,
    SORT_HIGHEST_SCORE,
    SORT_LOWEST_SCORE,
]


HISTORY_FILTER_ALL = "All"
HISTORY_FILTER_WATCH = "Watch"
HISTORY_FILTER_UNWATCH = "Unwatch"
HISTORY_FILTER_NOT_INTERESTED = "Not Interested"
HISTORY_FILTER_APPLIED = "Applied"
HISTORY_FILTER_ARCHIVED = "Archived"
HISTORY_FILTER_RESTORED = "Restored"

HISTORY_FILTERS = [
    HISTORY_FILTER_ALL,
    HISTORY_FILTER_WATCH,
    HISTORY_FILTER_UNWATCH,
    HISTORY_FILTER_NOT_INTERESTED,
    HISTORY_FILTER_APPLIED,
    HISTORY_FILTER_ARCHIVED,
    HISTORY_FILTER_RESTORED,
]









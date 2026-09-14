




# agents/discovery_agent.py

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from strands import tool

from app.constants import (
    CATEGORY_FREELANCE,
    CATEGORY_GRANT,
    CATEGORY_HACKATHON,
    CATEGORY_JOB,
    CATEGORY_OTHER,
    CATEGORY_PROGRAM,
    SOURCE_ATS,
    SOURCE_EMPLOYER,
    SOURCE_FREELANCE,
    SOURCE_GRANT,
    SOURCE_HACKATHON,
    SOURCE_OTHER,
    SOURCE_PROGRAM,
    normalize_category,
)

from app.database import (
    find_opportunity_by_source_url,
    get_profile,
    normalize_url,
)

from config.models import (
    create_pursuit_agent,
)

from tools.web_research import (
    search_web,
)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MAX_OPPORTUNITIES = 10
MAX_FINAL_OPPORTUNITIES = 25

MAX_SEARCH_QUERIES = 40
SEARCH_RESULTS_PER_QUERY = 8
MAX_CANDIDATES_PER_QUERY = 5

ENABLE_FIRST_PASS_FAIRNESS = True


DEFAULT_DISCOVERY_CATEGORIES = [
    CATEGORY_JOB,
    CATEGORY_FREELANCE,
    CATEGORY_HACKATHON,
    CATEGORY_GRANT,
    CATEGORY_PROGRAM,
]


DEFAULT_JOB_LOCATIONS = [
    "",
    "India",
    "Remote",
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kochi",
]


JOB_ROLES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "ML Engineer",
    "Generative AI Engineer",
    "Applied AI Engineer",
    "LLM Engineer",
    "AI Platform Engineer",
    "ML Platform Engineer",
    "Data Engineer",
    "Cloud Data Engineer",
    "Data Platform Engineer",
    "Analytics Engineer",
    "MLOps Engineer",
    "AI Infrastructure Engineer",
    "Machine Learning Platform Engineer",
    "Python Engineer",
    "Backend Engineer",
]


FREELANCE_ROLES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Data Engineer",
    "Python Developer",
    "RAG Developer",
    "LLM Developer",
    "MLOps Engineer",
]


KNOWN_SKILLS = [
    "Python",
    "SQL",
    "PyTorch",
    "TensorFlow",
    "AWS",
    "Azure",
    "GCP",
    "FastAPI",
    "RAG",
    "LLM",
    "Generative AI",
    "Docker",
    "Kubernetes",
    "Spark",
    "Databricks",
    "Airflow",
    "Kafka",
    "dbt",
    "PostgreSQL",
    "Vector Database",
    "MLOps",
]


MAX_PROFILE_SKILLS = 8
MAX_SKILL_PAIR_QUERIES = 6


ATS_SEARCH_DOMAINS = [
    "job-boards.greenhouse.io",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "jobs.smartrecruiters.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
]


ATS_DOMAINS = {
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "jobvite.com",
}


PRIORITY_EMPLOYER_DOMAINS = [
    "amazon.jobs",
    "careers.microsoft.com",
    "careers.google.com",
    "careers.ibm.com",
    "jobs.apple.com",
    "nvidia.com",
    "careers.salesforce.com",
    "oracle.com",
    "careers.adobe.com",
    "careers.servicenow.com",
    "careers.sap.com",
    "careers.atlassian.com",
    "careers.uber.com",
    "careers.walmart.com",
    "careers.jpmorgan.com",
    "accenture.com",
    "careers.capgemini.com",
    "careers.cognizant.com",
    "infosys.com",
    "tcs.com",
    "careers.freshworks.com",
]


SECONDARY_PLATFORM_DOMAINS = {
    "linkedin.com",
    "indeed.com",
    "foundit.in",
    "monsterindia.com",
    "internshala.com",
    "dice.com",
    "builtin.com",
    "naukri.com",
    "hirist.tech",
    "glassdoor.com",
    "glassdoor.co.in",
    "wellfound.com",
}


HARD_BLOCKED_DOMAINS = {
    "jooble.org",
    "jobrapido.com",
    "careerjet.com",
    "talent.com",
    "simplyhired.com",
    "ziprecruiter.com",
    "remoterocketship.com",
    "jointaro.com",
}


SOCIAL_DOMAINS = {
    "x.com",
    "twitter.com",
    "facebook.com",
    "instagram.com",
    "threads.net",
}


UI_CATEGORY_MAP = {
    "Jobs": CATEGORY_JOB,
    "Job": CATEGORY_JOB,
    "JOB": CATEGORY_JOB,

    "Freelance": CATEGORY_FREELANCE,
    "FREELANCE": CATEGORY_FREELANCE,

    "Hackathons & Competitions": CATEGORY_HACKATHON,
    "Hackathon": CATEGORY_HACKATHON,
    "HACKATHON": CATEGORY_HACKATHON,

    "Grants & Funding": CATEGORY_GRANT,
    "Grant": CATEGORY_GRANT,
    "GRANT": CATEGORY_GRANT,

    "Programs & Learning": CATEGORY_PROGRAM,
    "Program": CATEGORY_PROGRAM,
    "PROGRAM": CATEGORY_PROGRAM,

    "Other": CATEGORY_OTHER,
    "OTHER": CATEGORY_OTHER,
}


# ============================================================
# STRANDS STRUCTURED OUTPUT
# ============================================================

class DiscoveryCandidate(BaseModel):

    title: str = ""
    organization: str = ""
    category: str = ""

    external_id: str = ""

    source_url: str = ""

    location: str = ""

    work_arrangement: str = "UNKNOWN"

    deadline: str = ""
    reward: str = ""

    description: str = ""

    requirements: list[str] = Field(
        default_factory=list
    )

    eligibility: list[str] = Field(
        default_factory=list
    )

    submission: str = ""

    details: dict[str, Any] = Field(
        default_factory=dict
    )

    evidence: list[str] = Field(
        default_factory=list
    )

    activity_status: str = "UNKNOWN"


class DiscoveryBatch(BaseModel):

    opportunities: list[
        DiscoveryCandidate
    ] = Field(
        default_factory=list
    )


# ============================================================
# HELPERS
# ============================================================

def clean_text(
    value,
) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def clean_string_list(
    value,
) -> list[str]:

    if not isinstance(
        value,
        list,
    ):
        return []

    output = []

    for item in value:

        text = clean_text(
            item
        )

        if (
            text
            and text not in output
        ):
            output.append(
                text
            )

    return output


def normalize_requested_category(
    value,
) -> str:

    if not value:
        return CATEGORY_OTHER

    if value in UI_CATEGORY_MAP:

        return UI_CATEGORY_MAP[
            value
        ]

    return normalize_category(
        value
    )


def get_domain(
    url: str,
) -> str:

    try:

        parsed = urlparse(
            clean_text(url)
        )

        return (
            parsed.netloc
            .lower()
            .removeprefix(
                "www."
            )
        )

    except Exception:

        return ""


def domain_matches(
    domain: str,
    candidates,
) -> bool:

    domain = (
        clean_text(
            domain
        )
        .lower()
        .removeprefix(
            "www."
        )
    )

    if not domain:
        return False

    return any(
        domain == candidate
        or domain.endswith(
            "." + candidate
        )
        for candidate
        in candidates
    )


def is_valid_opportunity_url(
    url: str,
) -> bool:

    url = clean_text(
        url
    )

    if not url:
        return False

    try:

        parsed = urlparse(
            url
        )

    except Exception:

        return False

    return (
        parsed.scheme
        in {
            "http",
            "https",
        }
        and bool(
            parsed.netloc
        )
        and bool(
            parsed.hostname
        )
    )


# ============================================================
# REAL STRANDS TOOL
# ============================================================

@tool
def search_opportunity_web(
    query: str,
    max_results: int = SEARCH_RESULTS_PER_QUERY,
) -> str:
    """
    Search the public web for professional opportunities.

    The PURSUIT Discovery Agent uses this tool to find fresh,
    actionable opportunity candidates.

    Args:
        query:
            Web search query describing the opportunity.

        max_results:
            Maximum number of search results.

    Returns:
        Search result text containing titles, URLs and summaries.
    """

    query = clean_text(
        query
    )

    if not query:

        return (
            "NO SEARCH QUERY PROVIDED."
        )

    max_results = max(
        1,
        min(
            int(
                max_results
            ),
            SEARCH_RESULTS_PER_QUERY,
        ),
    )

    try:

        result = search_web(
            query=
                query,

            max_results=
                max_results,

            region=
                "wt-wt",
        )

    except Exception as exc:

        return (
            "WEB SEARCH FAILED.\n"
            f"Reason: {clean_text(exc)}"
        )

    if not result:

        return (
            "NO SEARCH RESULTS."
        )

    return str(
        result
    )


# ============================================================
# PROFILE CONTEXT
# ============================================================

def get_profile_context(
    user_id: int,
) -> dict:

    profile = get_profile(
        user_id
    )

    if not profile:

        return {
            "goal":
                "AI Engineer",

            "skills":
                "",

            "currently_learning":
                "",

            "opportunity_types":
                [],
        }

    opportunity_types = []

    raw_types = (
        profile[
            "opportunity_types"
        ]
    )

    if raw_types:

        if isinstance(
            raw_types,
            str,
        ):

            opportunity_types = [
                normalize_requested_category(
                    item.strip()
                )
                for item
                in raw_types.split(
                    ","
                )
                if item.strip()
            ]

        elif isinstance(
            raw_types,
            (list, tuple),
        ):

            opportunity_types = [
                normalize_requested_category(
                    item
                )
                for item
                in raw_types
                if item
            ]

    return {
        "goal":
            clean_text(
                profile[
                    "career_goal"
                ]
            ),

        "skills":
            clean_text(
                profile[
                    "skills"
                ]
            ),

        "currently_learning":
            clean_text(
                profile[
                    "currently_learning"
                ]
            ),

        "opportunity_types":
            opportunity_types,
    }


def extract_profile_skills(
    profile_context: dict,
) -> list[str]:

    text = " ".join([
        profile_context.get(
            "skills",
            "",
        ),
        profile_context.get(
            "currently_learning",
            "",
        ),
    ]).lower()

    found = []

    for skill in KNOWN_SKILLS:

        if (
            skill.lower()
            in text
            and skill not in found
        ):

            found.append(
                skill
            )

    return found[
        :MAX_PROFILE_SKILLS
    ]


def extract_goal_roles(
    profile_context: dict,
) -> list[str]:

    goal = clean_text(
        profile_context.get(
            "goal"
        )
    )

    if not goal:
        return []

    goal_lower = (
        goal.lower()
    )

    role_library = list(
        dict.fromkeys(
            JOB_ROLES
            + FREELANCE_ROLES
        )
    )

    matched = []

    for role in role_library:

        if (
            role.lower()
            in goal_lower
        ):

            matched.append(
                role
            )

    if not matched:

        for piece in re.split(
            r"[,/|;]+",
            goal,
        ):

            piece = clean_text(
                piece
            )

            if (
                piece
                and len(piece)
                <= 60
            ):

                matched.append(
                    piece
                )

    return list(
        dict.fromkeys(
            matched
        )
    )[:8]


# ============================================================
# QUERY GENERATION
# ============================================================

def make_query(
    query,
    category,
    family,
    priority,
):

    return {
        "query":
            clean_text(
                query
            ),

        "category":
            category,

        "family":
            family,

        "priority":
            int(
                priority
            ),
    }


def build_job_queries(
    profile_context,
    skills,
    search_preferences,
):

    queries = []

    roles = list(
        dict.fromkeys(
            extract_goal_roles(
                profile_context
            )
            + JOB_ROLES
        )
    )

    # --------------------------------------------------------
    # ATS
    # --------------------------------------------------------

    for role in roles[:6]:

        for domain in (
            ATS_SEARCH_DOMAINS
        ):

            queries.append(
                make_query(
                    f'site:{domain} "{role}"',

                    CATEGORY_JOB,

                    "ats_role",

                    100,
                )
            )

    # --------------------------------------------------------
    # Major employer sites
    # --------------------------------------------------------

    for role in roles[:4]:

        for domain in (
            PRIORITY_EMPLOYER_DOMAINS
        ):

            queries.append(
                make_query(
                    f'site:{domain} "{role}"',

                    CATEGORY_JOB,

                    "employer_role",

                    95,
                )
            )

    locations = list(
        DEFAULT_JOB_LOCATIONS
    )

    if search_preferences:

        locations.insert(
            0,
            search_preferences,
        )

    # --------------------------------------------------------
    # Role + location
    # --------------------------------------------------------

    for role in roles[:8]:

        for location in (
            locations[:4]
        ):

            if location:

                query = (
                    f'"{role}" '
                    f'"{location}" '
                    "hiring apply"
                )

            else:

                query = (
                    f'"{role}" '
                    "hiring apply"
                )

            queries.append(
                make_query(
                    query,

                    CATEGORY_JOB,

                    "role_location",

                    80,
                )
            )

    # --------------------------------------------------------
    # Role + skill
    # --------------------------------------------------------

    for role in roles[:6]:

        for skill in skills[:5]:

            queries.append(
                make_query(
                    f'"{role}" '
                    f'"{skill}" hiring',

                    CATEGORY_JOB,

                    "role_skill",

                    75,
                )
            )

    # --------------------------------------------------------
    # Skill pairs
    # --------------------------------------------------------

    pair_count = 0

    for (
        first,
        second,
    ) in combinations(
        skills,
        2,
    ):

        if (
            pair_count
            >= MAX_SKILL_PAIR_QUERIES
        ):

            break

        queries.append(
            make_query(
                f'"{first}" '
                f'"{second}" '
                "engineer jobs",

                CATEGORY_JOB,

                "skill_pair",

                65,
            )
        )

        pair_count += 1

    return queries


def build_freelance_queries(
    profile_context,
    skills,
    search_preferences,
):

    queries = []

    roles = list(
        dict.fromkeys(
            extract_goal_roles(
                profile_context
            )
            + FREELANCE_ROLES
        )
    )

    for role in roles[:8]:

        queries.extend([
            make_query(
                f'"{role}" '
                "freelance project apply",

                CATEGORY_FREELANCE,

                "freelance_role",

                90,
            ),

            make_query(
                f'"{role}" '
                "contract project remote",

                CATEGORY_FREELANCE,

                "freelance_contract",

                85,
            ),
        ])

    for skill in skills[:5]:

        queries.append(
            make_query(
                f'"{skill}" '
                "freelance project "
                "contract apply",

                CATEGORY_FREELANCE,

                "freelance_skill",

                70,
            )
        )

    return queries


def build_hackathon_queries(
    skills,
):

    queries = [
        make_query(
            "AI hackathon registration 2026",
            CATEGORY_HACKATHON,
            "hackathon_general",
            100,
        ),

        make_query(
            "machine learning hackathon registration 2026",
            CATEGORY_HACKATHON,
            "hackathon_general",
            95,
        ),

        make_query(
            "generative AI hackathon submissions 2026",
            CATEGORY_HACKATHON,
            "hackathon_general",
            95,
        ),

        make_query(
            "AI competition challenge registration 2026",
            CATEGORY_HACKATHON,
            "hackathon_general",
            90,
        ),

        make_query(
            "Devpost AI hackathon 2026",
            CATEGORY_HACKATHON,
            "hackathon_platform",
            85,
        ),
    ]

    for skill in skills[:4]:

        queries.append(
            make_query(
                f'"{skill}" '
                "hackathon challenge registration",

                CATEGORY_HACKATHON,

                "hackathon_skill",

                75,
            )
        )

    return queries


def build_grant_queries(
    skills,
):

    queries = [
        make_query(
            "AI grant applications open 2026",
            CATEGORY_GRANT,
            "grant_general",
            100,
        ),

        make_query(
            "technology innovation grant applications open 2026",
            CATEGORY_GRANT,
            "grant_general",
            95,
        ),

        make_query(
            "open source AI grant funding applications",
            CATEGORY_GRANT,
            "grant_general",
            95,
        ),

        make_query(
            "machine learning research grant applications 2026",
            CATEGORY_GRANT,
            "grant_general",
            90,
        ),
    ]

    for skill in skills[:4]:

        queries.append(
            make_query(
                f'"{skill}" '
                "grant funding apply",

                CATEGORY_GRANT,

                "grant_skill",

                75,
            )
        )

    return queries


def build_program_queries(
    skills,
):

    queries = [
        make_query(
            "AI fellowship applications open 2026",
            CATEGORY_PROGRAM,
            "program_general",
            100,
        ),

        make_query(
            "AI engineering program applications open 2026",
            CATEGORY_PROGRAM,
            "program_general",
            95,
        ),

        make_query(
            "machine learning fellowship apply 2026",
            CATEGORY_PROGRAM,
            "program_general",
            95,
        ),

        make_query(
            "data engineering training program applications 2026",
            CATEGORY_PROGRAM,
            "program_general",
            90,
        ),

        make_query(
            "developer accelerator program applications 2026",
            CATEGORY_PROGRAM,
            "program_general",
            85,
        ),
    ]

    for skill in skills[:4]:

        queries.append(
            make_query(
                f'"{skill}" '
                "program fellowship application",

                CATEGORY_PROGRAM,

                "program_skill",

                75,
            )
        )

    return queries


def build_other_queries(
    profile_context,
):

    goal = (
        profile_context.get(
            "goal"
        )
        or "technology"
    )

    return [
        make_query(
            f'"{goal}" '
            "opportunity applications open",

            CATEGORY_OTHER,

            "other_general",

            70,
        ),

        make_query(
            f'"{goal}" '
            "competition fellowship grant",

            CATEGORY_OTHER,

            "other_general",

            65,
        ),
    ]


def build_queries_by_category(
    profile_context,
    selected_types,
    search_preferences,
):

    skills = extract_profile_skills(
        profile_context
    )

    output = {}

    for category in selected_types:

        if category == CATEGORY_JOB:

            queries = build_job_queries(
                profile_context,
                skills,
                search_preferences,
            )

        elif category == CATEGORY_FREELANCE:

            queries = build_freelance_queries(
                profile_context,
                skills,
                search_preferences,
            )

        elif category == CATEGORY_HACKATHON:

            queries = build_hackathon_queries(
                skills
            )

        elif category == CATEGORY_GRANT:

            queries = build_grant_queries(
                skills
            )

        elif category == CATEGORY_PROGRAM:

            queries = build_program_queries(
                skills
            )

        else:

            queries = build_other_queries(
                profile_context
            )

        # Deduplicate query strings.

        unique = {}

        for item in queries:

            key = (
                item[
                    "query"
                ]
                .casefold()
            )

            previous = (
                unique.get(
                    key
                )
            )

            if (
                previous is None
                or item["priority"]
                > previous["priority"]
            ):

                unique[
                    key
                ] = item

        category_queries = list(
            unique.values()
        )

        category_queries.sort(
            key=lambda item:
                item[
                    "priority"
                ],
            reverse=True,
        )

        output[
            category
        ] = category_queries

    return output


def schedule_queries_round_robin(
    queries_by_category,
    selected_types,
    max_queries,
):

    positions = {
        category: 0
        for category
        in selected_types
    }

    scheduled = []

    while (
        len(scheduled)
        < max_queries
    ):

        made_progress = False

        for category in selected_types:

            queries = (
                queries_by_category.get(
                    category,
                    [],
                )
            )

            position = (
                positions[
                    category
                ]
            )

            if (
                position
                >= len(
                    queries
                )
            ):

                continue

            scheduled.append(
                queries[
                    position
                ]
            )

            positions[
                category
            ] += 1

            made_progress = True

            if (
                len(scheduled)
                >= max_queries
            ):

                break

        if not made_progress:

            break

    return scheduled


def build_search_queries(
    profile_context,
    requested_types=None,
    search_preferences="",
):

    # Explicit UI request always wins.

    if requested_types is not None:

        selected_types = list(
            requested_types
        )

    else:

        selected_types = list(
            profile_context.get(
                "opportunity_types",
                [],
            )
        )

        if not selected_types:

            selected_types = list(
                DEFAULT_DISCOVERY_CATEGORIES
            )

    normalized_types = []

    for item in selected_types:

        category = (
            normalize_requested_category(
                item
            )
        )

        if (
            category
            not in normalized_types
        ):

            normalized_types.append(
                category
            )

    if not normalized_types:

        return [], []

    queries_by_category = (
        build_queries_by_category(
            profile_context=
                profile_context,

            selected_types=
                normalized_types,

            search_preferences=
                search_preferences,
        )
    )

    queries = (
        schedule_queries_round_robin(
            queries_by_category=
                queries_by_category,

            selected_types=
                normalized_types,

            max_queries=
                MAX_SEARCH_QUERIES,
        )
    )

    return (
        queries,
        normalized_types,
    )


# ============================================================
# STRANDS DISCOVERY AGENT
# ============================================================

DISCOVERY_AGENT_INSTRUCTIONS = """
You discover real, actionable professional opportunities.

You have a web-search tool named search_opportunity_web.

For every discovery request:

1. Call search_opportunity_web using the supplied search query.
2. Inspect only evidence returned by that tool.
3. Return individual actionable opportunities.
4. Never invent URLs.
5. Never invent organizations.
6. Never turn personal profiles into opportunities.
7. Never return generic listing/search/category pages.
8. Never infer requirements, deadlines, rewards, eligibility,
   location, or work arrangement from general knowledge.
9. Leave unsupported fields empty.
10. Return only opportunities matching the requested category.

JOB:
Return individual job postings, not job-board landing pages or
LinkedIn personal profiles.

FREELANCE:
Return individual projects/contracts.

HACKATHON:
Return individual hackathons, competitions, or challenges.

GRANT:
Return individual funding opportunities.

PROGRAM:
Return individual fellowships, accelerators, cohorts, or
professional learning programs.

activity_status:
ACTIVE only when evidence explicitly says applications are open.
CLOSED only when evidence explicitly says closed/expired.
Otherwise UNKNOWN.
"""


def create_discovery_agent():

    return create_pursuit_agent(
        name=
            "Discovery Agent",

        instructions=
            DISCOVERY_AGENT_INSTRUCTIONS,

        tier=
            "fast",

        tools=[
            search_opportunity_web,
        ],
    )


def run_discovery_query(
    *,
    query: str,
    category: str,
) -> list[dict]:

    agent = (
        create_discovery_agent()
    )

    prompt = f"""
Find professional opportunities for this exact search.

SEARCH QUERY:
{query}

REQUESTED CATEGORY:
{category}

You MUST call search_opportunity_web.

Return no more than {MAX_CANDIDATES_PER_QUERY} opportunities.

Do not return:

- personal profiles
- articles
- tutorials
- generic job-board pages
- search pages
- category pages
- URL-less opportunities

Every returned opportunity must belong to:

{category}
"""

    try:

        result = agent(
            prompt,

            structured_output_model=
                DiscoveryBatch,
        )

    except Exception as exc:

        print(
            "[Discovery] Strands "
            "agent failed."
        )

        print(
            f"[Discovery] Error: {exc}"
        )

        return []

    structured = getattr(
        result,
        "structured_output",
        None,
    )

    if not isinstance(
        structured,
        DiscoveryBatch,
    ):

        return []

    return [
        candidate.model_dump()
        for candidate
        in structured.opportunities[
            :MAX_CANDIDATES_PER_QUERY
        ]
    ]


# ============================================================
# DETERMINISTIC FILTERING
# ============================================================

def is_hard_blocked_source(
    url: str,
) -> bool:

    return domain_matches(
        get_domain(
            url
        ),
        HARD_BLOCKED_DOMAINS,
    )


def is_person_or_social_page(
    url: str,
) -> bool:

    url_lower = (
        clean_text(
            url
        )
        .lower()
    )

    domain = get_domain(
        url
    )

    if domain_matches(
        domain,
        SOCIAL_DOMAINS,
    ):

        return True

    if domain_matches(
        domain,
        {
            "linkedin.com"
        },
    ):

        return (
            "/jobs/view/"
            not in url_lower
        )

    return False


def classify_source_type(
    url,
    category,
):

    domain = get_domain(
        url
    )

    if domain_matches(
        domain,
        ATS_DOMAINS,
    ):

        return SOURCE_ATS

    if domain_matches(
        domain,
        SECONDARY_PLATFORM_DOMAINS,
    ):

        return SOURCE_OTHER

    if category == CATEGORY_FREELANCE:

        return SOURCE_FREELANCE

    if category == CATEGORY_HACKATHON:

        return SOURCE_HACKATHON

    if category == CATEGORY_GRANT:

        return SOURCE_GRANT

    if category == CATEGORY_PROGRAM:

        return SOURCE_PROGRAM

    if category == CATEGORY_JOB:

        return SOURCE_EMPLOYER

    return SOURCE_OTHER


def source_quality_rank(
    url,
):

    domain = get_domain(
        url
    )

    if domain_matches(
        domain,
        ATS_DOMAINS,
    ):

        return 100

    if domain_matches(
        domain,
        set(
            PRIORITY_EMPLOYER_DOMAINS
        ),
    ):

        return 95

    if domain_matches(
        domain,
        {
            "linkedin.com",
            "indeed.com",
            "dice.com",
            "builtin.com",
        },
    ):

        return 65

    return 80


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_work_arrangement(
    value,
) -> str:

    text = (
        clean_text(
            value
        )
        .upper()
        .replace(
            "-",
            "",
        )
        .replace(
            "_",
            "",
        )
        .replace(
            " ",
            "",
        )
    )

    aliases = {
        "REMOTE":
            "REMOTE",

        "REMOTEFIRST":
            "REMOTE",

        "WORKFROMHOME":
            "REMOTE",

        "WFH":
            "REMOTE",

        "HYBRID":
            "HYBRID",

        "ONSITE":
            "ONSITE",

        "ONLOCATION":
            "ONSITE",

        "OFFICE":
            "ONSITE",

        "UNKNOWN":
            "UNKNOWN",

        "":
            "UNKNOWN",
    }

    return aliases.get(
        text,
        "UNKNOWN",
    )


def normalize_activity_status(
    value,
) -> str:

    text = (
        clean_text(
            value
        )
        .upper()
    )

    if text in {
        "ACTIVE",
        "OPEN",
        "OPEN FOR APPLICATIONS",
        "ACCEPTING APPLICATIONS",
    }:

        return "ACTIVE"

    if text in {
        "CLOSED",
        "EXPIRED",
        "POSITION FILLED",
        "APPLICATIONS CLOSED",
        "NO LONGER ACCEPTING APPLICATIONS",
    }:

        return "CLOSED"

    return "UNKNOWN"


def normalize_candidate(
    candidate: dict,
    requested_category: str,
    query: str,
) -> dict | None:

    if not isinstance(
        candidate,
        dict,
    ):

        return None

    source_url = clean_text(
        candidate.get(
            "source_url"
        )
    )

    if not is_valid_opportunity_url(
        source_url
    ):

        return None

    if is_hard_blocked_source(
        source_url
    ):

        return None

    if is_person_or_social_page(
        source_url
    ):

        return None

    category = (
        normalize_requested_category(
            candidate.get(
                "category"
            )
            or requested_category
        )
    )

    if (
        category
        != requested_category
    ):

        return None

    title = clean_text(
        candidate.get(
            "title"
        )
    )

    if not title:

        return None

    organization = clean_text(
        candidate.get(
            "organization"
        )
    )

    if (
        category
        == CATEGORY_JOB
        and not organization
    ):

        return None

    return {
        "title":
            title,

        "organization":
            organization,

        "category":
            category,

        "external_id":
            clean_text(
                candidate.get(
                    "external_id"
                )
            ),

        "source_url":
            source_url,

        "source_type":
            classify_source_type(
                source_url,
                category,
            ),

        "location":
            clean_text(
                candidate.get(
                    "location"
                )
            ),

        "work_arrangement":
            normalize_work_arrangement(
                candidate.get(
                    "work_arrangement"
                )
            ),

        "deadline":
            clean_text(
                candidate.get(
                    "deadline"
                )
            ),

        "reward":
            clean_text(
                candidate.get(
                    "reward"
                )
            ),

        "description":
            clean_text(
                candidate.get(
                    "description"
                )
            ),

        "requirements":
            clean_string_list(
                candidate.get(
                    "requirements"
                )
            ),

        "eligibility":
            clean_string_list(
                candidate.get(
                    "eligibility"
                )
            ),

        "submission":
            clean_text(
                candidate.get(
                    "submission"
                )
            ),

        "details":
            (
                candidate.get(
                    "details"
                )
                if isinstance(
                    candidate.get(
                        "details"
                    ),
                    dict,
                )
                else {}
            ),

        "evidence":
            clean_string_list(
                candidate.get(
                    "evidence"
                )
            ),

        "activity_status":
            normalize_activity_status(
                candidate.get(
                    "activity_status"
                )
            ),

        "_discovery_meta": {
            "search_query":
                query,

            "requested_category":
                requested_category,

            "source_url":
                source_url,

            "framework":
                "Strands Agents SDK",

            "tool":
                "search_opportunity_web",
        },
    }


# ============================================================
# CROSS-SOURCE DEDUPLICATION
# ============================================================

LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "pvt",
    "private",
    "corp",
    "corporation",
    "company",
    "co",
}


def normalize_organization(
    value,
):

    text = (
        clean_text(
            value
        )
        .lower()
    )

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    return " ".join(
        word
        for word
        in text.split()
        if word
        not in LEGAL_SUFFIXES
    )


def normalize_role_title(
    value,
):

    text = (
        clean_text(
            value
        )
        .lower()
    )

    text = re.sub(
        r"[^a-z0-9+#\s]",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def title_similarity(
    first,
    second,
):

    first = normalize_role_title(
        first
    )

    second = normalize_role_title(
        second
    )

    if not first or not second:

        return 0.0

    if first == second:

        return 1.0

    return SequenceMatcher(
        None,
        first,
        second,
    ).ratio()


def same_cross_source_opportunity(
    first,
    second,
):

    first_org = normalize_organization(
        first.get(
            "organization"
        )
    )

    second_org = normalize_organization(
        second.get(
            "organization"
        )
    )

    if (
        not first_org
        or not second_org
    ):

        return False

    if first_org != second_org:

        return False

    if (
        first.get(
            "category"
        )
        != second.get(
            "category"
        )
    ):

        return False

    return (
        title_similarity(
            first.get(
                "title"
            ),
            second.get(
                "title"
            ),
        )
        >= 0.82
    )


def candidate_quality_score(
    opportunity,
):

    score = source_quality_rank(
        opportunity.get(
            "source_url",
            "",
        )
    )

    if opportunity.get(
        "external_id"
    ):

        score += 8

    if opportunity.get(
        "organization"
    ):

        score += 8

    if opportunity.get(
        "location"
    ):

        score += 4

    requirements = (
        opportunity.get(
            "requirements",
            [],
        )
    )

    if isinstance(
        requirements,
        list,
    ):

        score += min(
            len(
                requirements
            )
            * 2,
            12,
        )

    return score


def merge_cross_source_duplicates(
    opportunities,
):

    groups = []

    for opportunity in opportunities:

        canonical_url = normalize_url(
            opportunity.get(
                "source_url",
                "",
            )
        )

        matching_group = None

        for group in groups:

            current = (
                group[
                    "canonical"
                ]
            )

            current_url = normalize_url(
                current.get(
                    "source_url",
                    "",
                )
            )

            if (
                canonical_url
                and canonical_url
                == current_url
            ):

                matching_group = group
                break

            if same_cross_source_opportunity(
                current,
                opportunity,
            ):

                matching_group = group
                break

        if matching_group is None:

            groups.append({
                "canonical":
                    opportunity,

                "members": [
                    opportunity
                ],
            })

            continue

        matching_group[
            "members"
        ].append(
            opportunity
        )

        if (
            candidate_quality_score(
                opportunity
            )
            >
            candidate_quality_score(
                matching_group[
                    "canonical"
                ]
            )
        ):

            matching_group[
                "canonical"
            ] = opportunity

    merged = []

    for group in groups:

        canonical = (
            group[
                "canonical"
            ]
        )

        metadata = (
            canonical.setdefault(
                "_discovery_meta",
                {},
            )
        )

        alternate_sources = []

        canonical_url = normalize_url(
            canonical.get(
                "source_url",
                "",
            )
        )

        seen_urls = set()

        if canonical_url:

            seen_urls.add(
                canonical_url
            )

        for member in (
            group[
                "members"
            ]
        ):

            if member is canonical:

                continue

            member_url = (
                member.get(
                    "source_url",
                    "",
                )
            )

            normalized = normalize_url(
                member_url
            )

            if (
                not normalized
                or normalized
                in seen_urls
            ):

                continue

            seen_urls.add(
                normalized
            )

            alternate_sources.append({
                "url":
                    member_url,

                "source_type":
                    member.get(
                        "source_type",
                        SOURCE_OTHER,
                    ),

                "domain":
                    get_domain(
                        member_url
                    ),
            })

        metadata[
            "alternate_sources"
        ] = alternate_sources

        metadata[
            "duplicate_source_count"
        ] = len(
            alternate_sources
        )

        merged.append(
            canonical
        )

    return merged


# ============================================================
# FAIRNESS
# ============================================================

def calculate_first_pass_quotas(
    selected_types: list[str],
    max_opportunities: int,
) -> dict[str, int]:

    if not selected_types:

        return {}

    quotas = {
        category: 0
        for category
        in selected_types
    }

    base = (
        max_opportunities
        // len(
            selected_types
        )
    )

    remainder = (
        max_opportunities
        % len(
            selected_types
        )
    )

    for (
        index,
        category,
    ) in enumerate(
        selected_types
    ):

        quotas[
            category
        ] = (
            base
            + (
                1
                if index
                < remainder
                else 0
            )
        )

    return quotas


def opportunity_counts_by_category(
    opportunities,
):

    counts = defaultdict(
        int
    )

    for opportunity in opportunities:

        counts[
            opportunity.get(
                "category",
                CATEGORY_OTHER,
            )
        ] += 1

    return dict(
        counts
    )


# ============================================================
# PUBLIC DISCOVERY AGENT
# ============================================================

def discover_opportunities(
    user_id: int,
    requested_types=None,
    max_opportunities: int = DEFAULT_MAX_OPPORTUNITIES,
    search_preferences: str = "",
):

    max_opportunities = max(
        1,
        min(
            int(
                max_opportunities
            ),
            MAX_FINAL_OPPORTUNITIES,
        ),
    )

    profile_context = (
        get_profile_context(
            user_id
        )
    )

    (
        query_items,
        selected_types,
    ) = build_search_queries(
        profile_context=
            profile_context,

        requested_types=
            requested_types,

        search_preferences=
            search_preferences,
    )

    print(
        "[Discovery] Framework: "
        "Strands Agents SDK"
    )

    print(
        "[Discovery] Requested target: "
        f"{max_opportunities}"
    )

    print(
        "[Discovery] Categories: "
        + (
            ", ".join(
                selected_types
            )
            if selected_types
            else "(none)"
        )
    )

    if not selected_types:

        return []

    quotas = (
        calculate_first_pass_quotas(
            selected_types=
                selected_types,

            max_opportunities=
                max_opportunities,
        )
    )

    print(
        "[Discovery] Fair first-pass quotas: "
        + ", ".join(
            f"{category}={quota}"
            for category, quota
            in quotas.items()
        )
    )

    opportunities = []

    category_search_turns = {
        category: 0
        for category
        in selected_types
    }

    # ========================================================
    # SEARCH LOOP
    # ========================================================

    for (
        index,
        query_item,
    ) in enumerate(
        query_items,
        start=1,
    ):

        opportunities = (
            merge_cross_source_duplicates(
                opportunities
            )
        )

        if (
            len(
                opportunities
            )
            >= max_opportunities
        ):

            break

        query = (
            query_item[
                "query"
            ]
        )

        category = (
            query_item[
                "category"
            ]
        )

        family = (
            query_item[
                "family"
            ]
        )

        category_search_turns[
            category
        ] += 1

        print(
            f"[Discovery] Search "
            f"{index}/"
            f"{len(query_items)} "
            f"[{category}/{family}]: "
            f"{query}"
        )

        # ----------------------------------------------------
        # REAL STRANDS AGENT:
        #
        # Agent → @tool → web search → structured output
        # ----------------------------------------------------

        candidates = (
            run_discovery_query(
                query=
                    query,

                category=
                    category,
            )
        )

        for candidate in candidates:

            opportunities = (
                merge_cross_source_duplicates(
                    opportunities
                )
            )

            if (
                len(
                    opportunities
                )
                >= max_opportunities
            ):

                break

            first_pass_complete = all(
                category_search_turns[
                    selected_category
                ] >= 1
                for selected_category
                in selected_types
            )

            counts = (
                opportunity_counts_by_category(
                    opportunities
                )
            )

            # Before every category has had one search turn,
            # prevent one category from using all result slots.
            if (
                ENABLE_FIRST_PASS_FAIRNESS
                and not first_pass_complete
                and counts.get(
                    category,
                    0,
                )
                >= quotas.get(
                    category,
                    0,
                )
            ):

                continue

            normalized = (
                normalize_candidate(
                    candidate=
                        candidate,

                    requested_category=
                        category,

                    query=
                        query,
                )
            )

            if normalized is None:

                continue

            source_url = (
                normalized[
                    "source_url"
                ]
            )

            # Never rediscover an opportunity already in
            # this user's PURSUIT history.
            if find_opportunity_by_source_url(
                user_id=
                    user_id,

                url=
                    source_url,
            ):

                print(
                    "[Discovery] "
                    "Skipping existing: "
                    f"{source_url}"
                )

                continue

            opportunities.append(
                normalized
            )

            opportunities = (
                merge_cross_source_duplicates(
                    opportunities
                )
            )

            counts = (
                opportunity_counts_by_category(
                    opportunities
                )
            )

            count_text = ", ".join(
                f"{item}="
                f"{counts.get(item, 0)}"
                for item
                in selected_types
            )

            print(
                "[Discovery] Unique: "
                f"{len(opportunities)}/"
                f"{max_opportunities}"
                f" ({count_text})"
            )

            if (
                len(
                    opportunities
                )
                >= max_opportunities
            ):

                print(
                    "[Discovery] Requested "
                    "opportunity count reached. "
                    "Stopping immediately."
                )

                break

        if (
            len(
                opportunities
            )
            >= max_opportunities
        ):

            break

    # ========================================================
    # FINAL CANONICAL RESULTS
    # ========================================================

    opportunities = (
        merge_cross_source_duplicates(
            opportunities
        )
    )

    opportunities.sort(
        key=
            candidate_quality_score,

        reverse=True,
    )

    opportunities = (
        opportunities[
            :max_opportunities
        ]
    )

    counts = (
        opportunity_counts_by_category(
            opportunities
        )
    )

    print()

    print(
        "[Discovery] Returning "
        f"{len(opportunities)}/"
        f"{max_opportunities} "
        "unique actionable "
        "opportunity/opportunities."
    )

    for category in selected_types:

        print(
            f"[Discovery] {category}: "
            f"{counts.get(category, 0)}"
        )

    return opportunities


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    import json
    import sys

    user_id = 1

    if len(
        sys.argv
    ) > 1:

        user_id = int(
            sys.argv[1]
        )

    print(
        "Starting Strands-powered "
        "PURSUIT Discovery Agent..."
    )

    opportunities = (
        discover_opportunities(
            user_id=
                user_id,

            requested_types=[
                CATEGORY_JOB,
            ],

            max_opportunities=
                2,
        )
    )

    print(
        f"\nDiscovered "
        f"{len(opportunities)} "
        "opportunities.\n"
    )

    for (
        index,
        opportunity,
    ) in enumerate(
        opportunities,
        start=1,
    ):

        print(
            f"Opportunity {index}"
        )

        print(
            json.dumps(
                opportunity,
                indent=2,
                ensure_ascii=False,
            )
        )

        print(
            "-" * 70
        )





        
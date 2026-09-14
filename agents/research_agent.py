




# agents/research_agent.py

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from strands import tool

from config.models import create_pursuit_agent
from tools.web_research import fetch_webpage


# ============================================================
# CONFIGURATION
# ============================================================

MAX_WEBPAGE_LENGTH = 14000


# ============================================================
# HELPERS
# ============================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def clean_string_list(value) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    output = []

    for item in value:
        text = clean_text(item)

        if (
            text
            and text not in output
        ):
            output.append(
                text
            )

    return output


def clean_dict(value) -> dict:
    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def get_source_url(
    opportunity: dict,
) -> str:
    """
    source_url is canonical.

    'url' is supported only for compatibility with manual
    or older pipeline input.
    """

    return clean_text(
        opportunity.get(
            "source_url"
        )
        or opportunity.get(
            "url"
        )
    )


# ============================================================
# NORMALIZATION
# ============================================================

VALID_CATEGORIES = {
    "JOB",
    "FREELANCE",
    "HACKATHON",
    "GRANT",
    "PROGRAM",
    "OTHER",
}


def normalize_category(
    value,
) -> str:

    text = (
        clean_text(value)
        .upper()
    )

    aliases = {
        "JOB":
            "JOB",

        "JOBS":
            "JOB",

        "EMPLOYMENT":
            "JOB",

        "FREELANCE":
            "FREELANCE",

        "CONTRACT":
            "FREELANCE",

        "HACKATHON":
            "HACKATHON",

        "COMPETITION":
            "HACKATHON",

        "CHALLENGE":
            "HACKATHON",

        "GRANT":
            "GRANT",

        "FUNDING":
            "GRANT",

        "PROGRAM":
            "PROGRAM",

        "FELLOWSHIP":
            "PROGRAM",

        "OTHER":
            "OTHER",
    }

    result = aliases.get(
        text,
        "OTHER",
    )

    if result not in VALID_CATEGORIES:
        return "OTHER"

    return result


VALID_WORK_ARRANGEMENTS = {
    "REMOTE",
    "HYBRID",
    "ONSITE",
    "UNKNOWN",
}


def normalize_work_arrangement(
    value,
) -> str:

    text = (
        clean_text(value)
        .upper()
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
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

    result = aliases.get(
        text,
        "UNKNOWN",
    )

    if (
        result
        not in VALID_WORK_ARRANGEMENTS
    ):
        return "UNKNOWN"

    return result


VALID_ACTIVITY_STATUSES = {
    "ACTIVE",
    "CLOSED",
    "UNKNOWN",
}


def normalize_activity_status(
    value,
) -> str:

    text = (
        clean_text(value)
        .upper()
    )

    if text in {
        "ACTIVE",
        "OPEN",
        "OPEN FOR APPLICATIONS",
        "ACCEPTING APPLICATIONS",
        "AVAILABLE",
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


# ============================================================
# STRANDS STRUCTURED OUTPUT
# ============================================================

class ResearchResult(BaseModel):
    """
    Canonical Research Agent output.
    """

    title: str = ""

    organization: str = ""

    category: str = ""

    external_id: str = ""

    source_url: str = ""

    source_type: str = ""

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


# ============================================================
# REAL STRANDS TOOL
# ============================================================

@tool
def fetch_opportunity_webpage(
    url: str,
) -> str:
    """
    Fetch the webpage for one professional opportunity.

    Use this tool to verify opportunity facts before returning
    a researched opportunity.

    Args:
        url:
            Direct URL of the opportunity.

    Returns:
        The fetched webpage text, or an explicit fetch-failure
        message.

    Important:
        A fetch failure does NOT mean that the opportunity is
        closed, invalid, or inactive.
    """

    url = clean_text(
        url
    )

    if not url:

        return (
            "WEBPAGE FETCH UNAVAILABLE.\n"
            "Reason: no URL was supplied.\n"
            "Do not infer that the opportunity is closed."
        )

    try:

        webpage = fetch_webpage(
            url,
            max_length=
                MAX_WEBPAGE_LENGTH,
        )

    except Exception as exc:

        print(
            "[Research] Webpage fetch failed "
            f"for {url}: {exc}"
        )

        return (
            "WEBPAGE FETCH UNAVAILABLE.\n"
            f"URL: {url}\n"
            f"Reason: {clean_text(exc)}\n"
            "Use supplied Discovery data only.\n"
            "Do not infer that the opportunity is closed, "
            "expired, fake, or invalid."
        )

    if not webpage:

        return (
            "WEBPAGE FETCH UNAVAILABLE.\n"
            f"URL: {url}\n"
            "Reason: fetched webpage was empty.\n"
            "Use supplied Discovery data only.\n"
            "Do not infer that the opportunity is closed."
        )

    return str(
        webpage
    )


# ============================================================
# RESEARCH AGENT
# ============================================================

RESEARCH_AGENT_INSTRUCTIONS = """
You research and verify ONE professional opportunity.

You have a tool named:

fetch_opportunity_webpage

You MUST use that tool before producing the final researched
opportunity.

Evidence priority:

1. The fetched opportunity webpage
2. The supplied Discovery data
3. Nothing else

Never use general knowledge to fill missing facts.

Your job is to identify explicit facts useful for deciding
whether a person should pursue the opportunity.

STRICT FACT RULES

- Never invent facts.
- Never infer qualifications from a job title.
- Never infer salary.
- Never infer deadline.
- Never infer work arrangement.
- Never infer eligibility.
- Never infer location from company headquarters.
- Never infer activity status merely because the webpage exists.
- Never infer CLOSED because webpage fetching failed.

REQUIREMENTS are especially important.

requirements must contain ONLY explicit candidate/participant
requirements.

Do NOT convert responsibilities into requirements.

Do NOT convert technologies merely mentioned in a description
into requirements unless the source explicitly presents them as
required/preferred qualifications, skills, experience, or
prerequisites.

activity_status:

ACTIVE:
only when the evidence explicitly indicates that applications,
registration, submissions, or the opportunity are currently open.

CLOSED:
only when evidence explicitly says closed, expired, filled,
or no longer accepting applications.

Otherwise:
UNKNOWN.
"""


def create_research_agent():
    """
    Create PURSUIT's Strands-powered Research Agent.
    """

    return create_pursuit_agent(
        name=
            "Research Agent",

        instructions=
            RESEARCH_AGENT_INSTRUCTIONS,

        tier=
            "fast",

        tools=[
            fetch_opportunity_webpage,
        ],
    )


# ============================================================
# DETERMINISTIC FALLBACK
# ============================================================

def build_discovery_fallback(
    opportunity: dict,
) -> dict:
    """
    Safe fallback if the Strands agent/model itself fails.

    No new facts are created.
    """

    url = get_source_url(
        opportunity
    )

    return {
        "title":
            clean_text(
                opportunity.get(
                    "title"
                )
            ),

        "organization":
            clean_text(
                opportunity.get(
                    "organization"
                )
            ),

        "category":
            normalize_category(
                opportunity.get(
                    "category"
                )
            ),

        "external_id":
            clean_text(
                opportunity.get(
                    "external_id"
                )
            ),

        "source_url":
            url,

        "source_type":
            clean_text(
                opportunity.get(
                    "source_type"
                )
            )
            or "OTHER",

        "location":
            clean_text(
                opportunity.get(
                    "location"
                )
            ),

        "work_arrangement":
            normalize_work_arrangement(
                opportunity.get(
                    "work_arrangement"
                )
            ),

        "deadline":
            clean_text(
                opportunity.get(
                    "deadline"
                )
            ),

        "reward":
            clean_text(
                opportunity.get(
                    "reward"
                )
            ),

        "description":
            clean_text(
                opportunity.get(
                    "description"
                )
            ),

        "requirements":
            clean_string_list(
                opportunity.get(
                    "requirements"
                )
            ),

        "eligibility":
            clean_string_list(
                opportunity.get(
                    "eligibility"
                )
            ),

        "submission":
            clean_text(
                opportunity.get(
                    "submission"
                )
            ),

        "details":
            clean_dict(
                opportunity.get(
                    "details"
                )
            ),

        "evidence":
            clean_string_list(
                opportunity.get(
                    "evidence"
                )
            ),

        "activity_status":
            normalize_activity_status(
                opportunity.get(
                    "activity_status"
                )
            ),

        "_research_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Research Agent",

            "tool":
                "fetch_opportunity_webpage",

            "used_discovery_fallback":
                True,

            "input_url":
                url,
        },
    }


# ============================================================
# MAIN RESEARCH WORKFLOW
# ============================================================

def research_opportunity(
    opportunity: dict,
) -> dict:
    """
    Research and verify one opportunity through Strands.

    Pipeline contract remains unchanged:

        dict -> dict
    """

    if not isinstance(
        opportunity,
        dict,
    ):

        raise TypeError(
            "opportunity must be a dictionary."
        )

    source_url = get_source_url(
        opportunity
    )

    if not source_url:

        raise ValueError(
            "Opportunity source_url is required "
            "for research."
        )

    # --------------------------------------------------------
    # Create genuine Strands Research Agent
    # --------------------------------------------------------

    agent = create_research_agent()

    prompt = f"""
Research and verify this professional opportunity.

AUTHORITATIVE SOURCE URL:

{source_url}

DISCOVERY DATA:

{json.dumps(
    opportunity,
    indent=2,
    ensure_ascii=False,
)}

INSTRUCTIONS

1. You MUST call fetch_opportunity_webpage with exactly:

{source_url}

2. Use the fetched webpage as primary evidence.

3. Use DISCOVERY DATA only as secondary evidence.

4. If webpage fetching fails, rely only on DISCOVERY DATA.

5. source_url MUST remain exactly:

{source_url}


FIELD RULES

title
- explicit opportunity title only

organization
- actual employer, organizer, institution, or client
- do not infer it from general knowledge

category
Return exactly one:
JOB
FREELANCE
HACKATHON
GRANT
PROGRAM
OTHER

external_id
- explicit job/requisition/challenge/grant/program ID
- otherwise preserve Discovery external_id
- otherwise empty

source_url
- always preserve the authoritative URL above

source_type
- preserve Discovery source_type unless evidence clearly
  supports something better

location
- explicit opportunity location only

work_arrangement
Return exactly one:
REMOTE
HYBRID
ONSITE
UNKNOWN

deadline
- explicit deadline only

reward
- explicit salary, compensation, budget, prize, funding,
  stipend, or reward only

description
- concise factual opportunity-specific summary

requirements
- ONLY explicit requirements
- required skills
- required experience
- required qualifications
- required education
- required technical capabilities
- required participation conditions
- explicitly preferred requirements may be retained if they
  are clearly presented as candidate qualifications
- DO NOT convert responsibilities into requirements

eligibility
- explicit eligibility rules only

submission
- explicit application/submission instructions only

details
Include useful opportunity-specific facts that do not fit other
fields, such as:
- responsibilities
- employment type
- team
- project duration
- deliverables
- hackathon tracks
- judging criteria
- program duration
- cohort dates
- funding conditions

Do not include generic company history.

evidence
- short factual statements supporting the researched record
- do not invent citations

activity_status
Return exactly one:
ACTIVE
CLOSED
UNKNOWN

A webpage existing is NOT enough to mark ACTIVE.

A webpage fetch failure is NOT evidence of CLOSED.

Return the structured ResearchResult.
"""

    # ========================================================
    # STRANDS INVOCATION + STRUCTURED OUTPUT
    # ========================================================

    try:

        result = agent(
            prompt,
            structured_output_model=
                ResearchResult,
        )

    except Exception as exc:

        print(
            "[Research] Strands Research Agent failed "
            f"for {source_url}: {exc}"
        )

        return build_discovery_fallback(
            opportunity
        )

    structured = getattr(
        result,
        "structured_output",
        None,
    )

    if not isinstance(
        structured,
        ResearchResult,
    ):

        print(
            "[Research] No valid structured output. "
            "Using Discovery fallback."
        )

        return build_discovery_fallback(
            opportunity
        )

    researched = (
        structured.model_dump()
    )

    # ========================================================
    # DEFENSIVE NORMALIZATION
    # ========================================================

    title = (
        clean_text(
            researched.get(
                "title"
            )
        )
        or clean_text(
            opportunity.get(
                "title"
            )
        )
    )

    organization = (
        clean_text(
            researched.get(
                "organization"
            )
        )
        or clean_text(
            opportunity.get(
                "organization"
            )
        )
    )

    category = normalize_category(
        researched.get(
            "category"
        )
        or opportunity.get(
            "category"
        )
    )

    external_id = (
        clean_text(
            researched.get(
                "external_id"
            )
        )
        or clean_text(
            opportunity.get(
                "external_id"
            )
        )
    )

    source_type = (
        clean_text(
            researched.get(
                "source_type"
            )
        )
        or clean_text(
            opportunity.get(
                "source_type"
            )
        )
        or "OTHER"
    )

    location = (
        clean_text(
            researched.get(
                "location"
            )
        )
        or clean_text(
            opportunity.get(
                "location"
            )
        )
    )

    work_arrangement = (
        normalize_work_arrangement(
            researched.get(
                "work_arrangement"
            )
            or opportunity.get(
                "work_arrangement"
            )
        )
    )

    deadline = (
        clean_text(
            researched.get(
                "deadline"
            )
        )
        or clean_text(
            opportunity.get(
                "deadline"
            )
        )
    )

    reward = (
        clean_text(
            researched.get(
                "reward"
            )
        )
        or clean_text(
            opportunity.get(
                "reward"
            )
        )
    )

    description = (
        clean_text(
            researched.get(
                "description"
            )
        )
        or clean_text(
            opportunity.get(
                "description"
            )
        )
    )

    requirements = (
        clean_string_list(
            researched.get(
                "requirements"
            )
        )
    )

    # Discovery facts are still valid secondary evidence.
    if not requirements:

        requirements = (
            clean_string_list(
                opportunity.get(
                    "requirements"
                )
            )
        )

    eligibility = (
        clean_string_list(
            researched.get(
                "eligibility"
            )
        )
    )

    if not eligibility:

        eligibility = (
            clean_string_list(
                opportunity.get(
                    "eligibility"
                )
            )
        )

    submission = (
        clean_text(
            researched.get(
                "submission"
            )
        )
        or clean_text(
            opportunity.get(
                "submission"
            )
        )
    )

    details = clean_dict(
        researched.get(
            "details"
        )
    )

    if not details:

        details = clean_dict(
            opportunity.get(
                "details"
            )
        )

    evidence = clean_string_list(
        researched.get(
            "evidence"
        )
    )

    if not evidence:

        evidence = clean_string_list(
            opportunity.get(
                "evidence"
            )
        )

    activity_status = (
        normalize_activity_status(
            researched.get(
                "activity_status"
            )
        )
    )

    if activity_status == "UNKNOWN":

        discovery_status = (
            normalize_activity_status(
                opportunity.get(
                    "activity_status"
                )
            )
        )

        if (
            discovery_status
            != "UNKNOWN"
        ):

            activity_status = (
                discovery_status
            )

    # ========================================================
    # FINAL PIPELINE CONTRACT
    # ========================================================

    return {
        "title":
            title,

        "organization":
            organization,

        "category":
            category,

        "external_id":
            external_id,

        # Never allow the model to replace this.
        "source_url":
            source_url,

        "source_type":
            source_type,

        "location":
            location,

        "work_arrangement":
            work_arrangement,

        "deadline":
            deadline,

        "reward":
            reward,

        "description":
            description,

        "requirements":
            requirements,

        "eligibility":
            eligibility,

        "submission":
            submission,

        "details":
            details,

        "evidence":
            evidence,

        "activity_status":
            activity_status,

        "_research_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Research Agent",

            "tool":
                "fetch_opportunity_webpage",

            "used_discovery_fallback":
                False,

            "input_url":
                source_url,
        },
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    sample = {
        "title":
            "Example AI Engineer",

        "organization":
            "Example Company",

        "category":
            "JOB",

        "external_id":
            "",

        "source_url":
            "https://example.com/jobs/123",

        "source_type":
            "EMPLOYER",

        "location":
            "",

        "work_arrangement":
            "UNKNOWN",

        "deadline":
            "",

        "reward":
            "",

        "description":
            "",

        "requirements":
            [],

        "eligibility":
            [],

        "submission":
            "",

        "details":
            {},

        "evidence":
            [],

        "activity_status":
            "UNKNOWN",
    }

    result = research_opportunity(
        sample
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )



    
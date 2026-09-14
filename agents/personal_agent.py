




# agents/personal_agent.py

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from strands import tool

from config.models import create_pursuit_agent
from rag.vector_store import search_chunks


# ============================================================
# CONFIGURATION
# ============================================================

RAG_RESULTS = 5


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
            output.append(text)

    return output


# ============================================================
# STRUCTURED OUTPUT
# ============================================================

class RequirementAssessment(BaseModel):
    requirement: str = ""
    status: str = "Unknown"
    evidence: str = ""


class PersonalFitResult(BaseModel):
    requirements: list[
        RequirementAssessment
    ] = Field(
        default_factory=list
    )

    matching_skills: list[str] = Field(
        default_factory=list
    )

    skill_gaps: list[str] = Field(
        default_factory=list
    )

    profile_evidence: list[str] = Field(
        default_factory=list
    )

    personal_fit_score: int = 0


# ============================================================
# REAL STRANDS RAG TOOL
# ============================================================

@tool
def search_profile_evidence(
    user_id: int,
    query: str,
    n_results: int = RAG_RESULTS,
) -> str:
    """
    Search the user's professional profile evidence stored in
    ChromaDB.

    Use this tool when evaluating whether the user satisfies
    explicit opportunity requirements.

    Args:
        user_id:
            PURSUIT user ID.

        query:
            Requirement or qualification evidence to search for.

        n_results:
            Maximum number of relevant ChromaDB chunks.

    Returns:
        Relevant profile/document evidence.

    Important:
        Absence of evidence does NOT prove that the user lacks
        a qualification.
    """

    query = clean_text(
        query
    )

    if not query:
        return "NO PROFILE QUERY PROVIDED."

    try:
        results = search_chunks(
            user_id=user_id,
            query=query,
            n_results=max(
                1,
                min(
                    int(n_results),
                    10,
                ),
            ),
        )

    except Exception as exc:
        return (
            "PROFILE SEARCH UNAVAILABLE.\n"
            f"Reason: {clean_text(exc)}\n"
            "Do not treat unavailable profile evidence as "
            "a confirmed deficiency."
        )

    documents = results.get(
        "documents",
        [[]],
    )

    if not documents:
        return "NO RELEVANT PROFILE EVIDENCE FOUND."

    if (
        isinstance(
            documents,
            list,
        )
        and documents
        and isinstance(
            documents[0],
            list,
        )
    ):
        documents = documents[0]

    cleaned = []

    for document in documents:
        text = clean_text(
            document
        )

        if text:
            cleaned.append(
                text
            )

    if not cleaned:
        return "NO RELEVANT PROFILE EVIDENCE FOUND."

    return "\n\n--- PROFILE EVIDENCE ---\n\n".join(
        cleaned
    )


# ============================================================
# STRANDS PERSONAL AGENT
# ============================================================

PERSONAL_AGENT_INSTRUCTIONS = """
You are PURSUIT's Personal Intelligence Agent.

You compare explicit opportunity requirements against evidence
from the user's professional profile.

You have a tool named:

search_profile_evidence

You MUST use this tool to retrieve relevant evidence before
evaluating requirements.

STRICT RULES

Evaluate ONLY explicit opportunity requirements.

Never create requirements from:
- opportunity title
- responsibilities
- description
- organization
- likely expectations
- general knowledge

Requirement status:

Match
Use only when retrieved profile evidence explicitly supports the
complete requirement.

Partial
Use only when evidence explicitly supports part of the
requirement.

No Match
Use only when retrieved evidence explicitly proves the user does
not satisfy the requirement.

Unknown
Use when profile evidence is absent, incomplete, unclear, or
insufficient.

IMPORTANT

Missing evidence is NOT No Match.

Missing evidence is NOT automatically a skill gap.

skill_gaps may contain a requirement only when its status is:
- Partial
- No Match

Never add Unknown requirements to skill_gaps.

Do not add education qualifications such as degrees to
skill_gaps.

Every matching skill must be supported by profile evidence.

profile_evidence should contain only evidence actually used.

Never invent user qualifications.

personal_fit_score should reflect only evaluated explicit
requirements.

Unknown requirements should not be treated as failures.
"""


def create_personal_agent():
    return create_pursuit_agent(
        name=
            "Personal Intelligence Agent",

        instructions=
            PERSONAL_AGENT_INSTRUCTIONS,

        tier=
            "reasoning",

        tools=[
            search_profile_evidence,
        ],
    )


# ============================================================
# SCORE
# ============================================================

def calculate_personal_fit_score(
    requirements: list[dict],
) -> int:
    """
    Deterministic personal-fit score.

    Unknown requirements are excluded from the denominator.

    Match    = 1.0
    Partial  = 0.5
    No Match = 0.0
    Unknown  = excluded
    """

    if not requirements:
        return 0

    score = 0.0
    evaluable = 0

    for item in requirements:

        if not isinstance(
            item,
            dict,
        ):
            continue

        status = clean_text(
            item.get(
                "status"
            )
        )

        if status == "Unknown":
            continue

        evaluable += 1

        if status == "Match":
            score += 1.0

        elif status == "Partial":
            score += 0.5

    if evaluable == 0:
        return 0

    return round(
        score
        / evaluable
        * 100
    )


# ============================================================
# MAIN PERSONAL FIT WORKFLOW
# ============================================================

def analyze_personal_fit(
    user_id: int,
    opportunity: dict,
) -> dict:
    """
    Evaluate explicit opportunity requirements against RAG
    evidence using a real Strands tool-using agent.
    """

    if not isinstance(
        opportunity,
        dict,
    ):
        raise TypeError(
            "opportunity must be a dictionary."
        )

    requirements = clean_string_list(
        opportunity.get(
            "requirements"
        )
    )

    # --------------------------------------------------------
    # No explicit requirements = nothing legitimate to assess.
    # --------------------------------------------------------

    if not requirements:
        return {
            "requirements":
                [],

            "matching_skills":
                [],

            "skill_gaps":
                [],

            "profile_evidence":
                [],

            "personal_fit_score":
                0,

            "_personal_meta": {
                "framework":
                    "Strands Agents SDK",

                "agent":
                    "Personal Intelligence Agent",

                "tool":
                    "search_profile_evidence",

                "requirements_evaluated":
                    0,
            },
        }

    agent = create_personal_agent()

    prompt = f"""
Evaluate this user's fit for the explicit requirements below.

USER ID:
{user_id}

OPPORTUNITY:

{json.dumps(
    {
        "title":
            opportunity.get(
                "title",
                "",
            ),

        "organization":
            opportunity.get(
                "organization",
                "",
            ),

        "category":
            opportunity.get(
                "category",
                "",
            ),
    },
    indent=2,
    ensure_ascii=False,
)}

EXPLICIT REQUIREMENTS:

{json.dumps(
    requirements,
    indent=2,
    ensure_ascii=False,
)}

INSTRUCTIONS

For every requirement:

1. Call search_profile_evidence.

2. Search specifically for evidence relevant to that requirement.

3. Assign exactly one status:

Match
Partial
No Match
Unknown

4. Use Unknown when evidence is insufficient.

5. Do not use absence of evidence as proof of No Match.

6. Do not evaluate anything that is not in EXPLICIT REQUIREMENTS.

7. Keep requirement wording faithful to the supplied text.

8. Return profile evidence only when it was actually used.

Return PersonalFitResult.
"""

    try:
        result = agent(
            prompt,
            structured_output_model=
                PersonalFitResult,
        )

    except Exception as exc:
        print(
            "[Personal] Strands agent failed: "
            f"{exc}"
        )

        return {
            "requirements": [
                {
                    "requirement":
                        requirement,

                    "status":
                        "Unknown",

                    "evidence":
                        "",
                }
                for requirement
                in requirements
            ],

            "matching_skills":
                [],

            "skill_gaps":
                [],

            "profile_evidence":
                [],

            "personal_fit_score":
                0,

            "_personal_meta": {
                "framework":
                    "Strands Agents SDK",

                "agent":
                    "Personal Intelligence Agent",

                "tool":
                    "search_profile_evidence",

                "fallback":
                    True,

                "error":
                    clean_text(exc),
            },
        }

    structured = getattr(
        result,
        "structured_output",
        None,
    )

    if not isinstance(
        structured,
        PersonalFitResult,
    ):
        raise ValueError(
            "Personal Agent returned no valid "
            "structured output."
        )

    raw = structured.model_dump()

    # ========================================================
    # DEFENSIVE FILTERING
    # ========================================================

    explicit_requirement_texts = {
        clean_text(
            requirement
        )
        for requirement
        in requirements
    }

    filtered_requirements = []

    seen = set()

    for item in raw.get(
        "requirements",
        [],
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        requirement_text = clean_text(
            item.get(
                "requirement"
            )
        )

        if (
            requirement_text
            not in explicit_requirement_texts
        ):
            continue

        if requirement_text in seen:
            continue

        seen.add(
            requirement_text
        )

        status = clean_text(
            item.get(
                "status"
            )
        )

        if status not in {
            "Match",
            "Partial",
            "No Match",
            "Unknown",
        }:
            status = "Unknown"

        evidence = clean_text(
            item.get(
                "evidence"
            )
        )

        filtered_requirements.append({
            "requirement":
                requirement_text,

            "status":
                status,

            "evidence":
                evidence,
        })

    # --------------------------------------------------------
    # Ensure every explicit requirement exists in output.
    # --------------------------------------------------------

    returned_requirements = {
        item[
            "requirement"
        ]
        for item
        in filtered_requirements
    }

    for requirement in requirements:

        if (
            requirement
            not in returned_requirements
        ):

            filtered_requirements.append({
                "requirement":
                    requirement,

                "status":
                    "Unknown",

                "evidence":
                    "",
            })

    # ========================================================
    # GAP FILTERING
    # ========================================================

    allowed_gap_requirements = {
        item[
            "requirement"
        ]
        for item
        in filtered_requirements
        if item[
            "status"
        ]
        in {
            "Partial",
            "No Match",
        }
    }

    skill_gaps = []

    for gap in raw.get(
        "skill_gaps",
        [],
    ):

        gap_text = clean_text(
            gap
        )

        if (
            gap_text
            in allowed_gap_requirements
            and gap_text
            not in skill_gaps
        ):
            skill_gaps.append(
                gap_text
            )

    # ========================================================
    # MATCHING SKILLS
    # ========================================================

    matching_skills = clean_string_list(
        raw.get(
            "matching_skills"
        )
    )

    profile_evidence = clean_string_list(
        raw.get(
            "profile_evidence"
        )
    )

    # ========================================================
    # DETERMINISTIC SCORE
    # ========================================================

    personal_fit_score = (
        calculate_personal_fit_score(
            filtered_requirements
        )
    )

    # ========================================================
    # FINAL PIPELINE CONTRACT
    # ========================================================

    return {
        "requirements":
            filtered_requirements,

        "matching_skills":
            matching_skills,

        "skill_gaps":
            skill_gaps,

        "profile_evidence":
            profile_evidence,

        "personal_fit_score":
            personal_fit_score,

        "_personal_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Personal Intelligence Agent",

            "tool":
                "search_profile_evidence",

            "requirements_evaluated":
                len(
                    filtered_requirements
                ),

            "fallback":
                False,
        },
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    sample = {
        "title":
            "AI Engineer",

        "organization":
            "Example Company",

        "category":
            "JOB",

        "requirements": [
            "Python",
            "AWS",
            "Production RAG experience",
        ],
    }

    result = analyze_personal_fit(
        user_id=1,
        opportunity=sample,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )



    
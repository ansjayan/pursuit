




# agents/effort_agent.py

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from config.models import create_pursuit_agent


# ============================================================
# HELPERS
# ============================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


# ============================================================
# STRUCTURED OUTPUT
# ============================================================

class RiskItem(BaseModel):
    description: str = ""
    severity: str = "Low"


class EffortRiskResult(BaseModel):
    estimated_effort: str = "Unknown"
    time_pressure: str = "Unknown"

    risks: list[RiskItem] = Field(
        default_factory=list
    )

    opportunity_cost: str = ""

    effort_reasoning: str = ""
    risk_reasoning: str = ""


# ============================================================
# NORMALIZATION
# ============================================================

VALID_EFFORT_LEVELS = {
    "Low",
    "Medium",
    "High",
    "Unknown",
}


VALID_RISK_LEVELS = {
    "Low",
    "Medium",
    "High",
    "Critical",
}


def normalize_effort(
    value,
) -> str:
    text = clean_text(
        value
    ).title()

    if text not in VALID_EFFORT_LEVELS:
        return "Unknown"

    return text


def normalize_risk_severity(
    value,
) -> str:
    text = clean_text(
        value
    ).title()

    if text not in VALID_RISK_LEVELS:
        return "Low"

    return text


# ============================================================
# DETERMINISTIC SCORES
# ============================================================
from app.scoring import (
    calculate_effort_score,
    calculate_risk_score,
)

# ============================================================
# STRANDS EFFORT & RISK AGENT
# ============================================================

EFFORT_AGENT_INSTRUCTIONS = """
You are PURSUIT's Effort & Risk Agent.

Assess the practical effort and evidence-supported risk of
pursuing one professional opportunity.

Use ONLY:

1. researched opportunity facts
2. Personal Fit results

Do not use general knowledge about the company or industry.

ESTIMATED EFFORT

Return exactly one:

Low
Medium
High
Unknown

Consider only evidence-supported factors such as:

- application/submission complexity
- explicit deliverables
- explicit preparation burden
- explicit skill gaps
- participation workload
- project scope
- required artifacts

Do not invent hours.

Do not estimate effort from job title alone.

TIME PRESSURE

If the opportunity includes an explicit deadline or application
period, assess the pressure concisely.

If no deadline/time constraint is supplied:

Unknown

RISKS

Only include risks supported by supplied evidence.

Examples of valid risks:

- an explicit Partial requirement
- an explicit No Match requirement
- an explicit near deadline
- required travel or location constraint explicitly stated
- explicit funding/submission condition
- explicit project workload
- explicit participation eligibility concern

DO NOT create risks from:

- Unknown requirements
- missing profile evidence
- generic competition assumptions
- assumed visa issues
- assumed relocation
- assumed salary problems
- assumed company culture
- general market conditions

Unknown is uncertainty, not confirmed risk.

Each risk severity must be exactly:

Low
Medium
High
Critical

OPPORTUNITY COST

Describe only evidence-supported tradeoffs in pursuing this
specific opportunity.

If there is insufficient evidence, return an empty string.

Keep reasoning concise and grounded.
"""


def create_effort_agent():
    return create_pursuit_agent(
        name=
            "Effort & Risk Agent",

        instructions=
            EFFORT_AGENT_INSTRUCTIONS,

        tier=
            "reasoning",
    )


# ============================================================
# MAIN WORKFLOW
# ============================================================

def assess_effort_and_risk(
    opportunity: dict,
    personal_fit: dict,
) -> dict:
    """
    Assess effort and risk using a real Strands Agent.

    Pipeline contract:
        dict + dict -> dict
    """

    if not isinstance(
        opportunity,
        dict,
    ):
        raise TypeError(
            "opportunity must be a dictionary."
        )

    if not isinstance(
        personal_fit,
        dict,
    ):
        raise TypeError(
            "personal_fit must be a dictionary."
        )

    agent = create_effort_agent()

    prompt = f"""
Assess the effort and risk of pursuing this opportunity.

RESEARCHED OPPORTUNITY:

{json.dumps(
    opportunity,
    indent=2,
    ensure_ascii=False,
)}

PERSONAL FIT:

{json.dumps(
    personal_fit,
    indent=2,
    ensure_ascii=False,
)}

Return EffortRiskResult.

Rules:

- Use only supplied evidence.
- Missing profile evidence is not a confirmed deficiency.
- Unknown requirement statuses must not create risks.
- Qualification risks may only come from explicit Partial or
  No Match requirements.
- Do not invent deadlines.
- Do not invent relocation, visa, salary, competition, or
  company-specific risks.
- estimated_effort must be exactly:
  Low, Medium, High, or Unknown.
- every risk severity must be exactly:
  Low, Medium, High, or Critical.
"""

    try:
        result = agent(
            prompt,
            structured_output_model=
                EffortRiskResult,
        )

    except Exception as exc:

        print(
            "[Effort] Strands agent failed: "
            f"{exc}"
        )

        return {
            "estimated_effort":
                "Unknown",

            "time_pressure":
                "Unknown",

            "risks":
                [],

            "opportunity_cost":
                "",

            "effort_reasoning":
                "",

            "risk_reasoning":
                "",

            "effort_score":
                50,

            "risk_score":
                90,

            "_effort_meta": {
                "framework":
                    "Strands Agents SDK",

                "agent":
                    "Effort & Risk Agent",

                "fallback":
                    True,

                "error":
                    clean_text(
                        exc
                    ),
            },
        }

    structured = getattr(
        result,
        "structured_output",
        None,
    )

    if not isinstance(
        structured,
        EffortRiskResult,
    ):
        raise ValueError(
            "Effort & Risk Agent returned "
            "no valid structured output."
        )

    raw = (
        structured.model_dump()
    )

    # ========================================================
    # NORMALIZE EFFORT
    # ========================================================

    estimated_effort = (
        normalize_effort(
            raw.get(
                "estimated_effort"
            )
        )
    )

    # ========================================================
    # NORMALIZE RISKS
    # ========================================================

    normalized_risks = []

    for risk in raw.get(
        "risks",
        [],
    ):
        if not isinstance(
            risk,
            dict,
        ):
            continue

        description = clean_text(
            risk.get(
                "description"
            )
        )

        if not description:
            continue

        severity = (
            normalize_risk_severity(
                risk.get(
                    "severity"
                )
            )
        )

        normalized_risks.append({
            "description":
                description,

            "severity":
                severity,
        })

    # ========================================================
    # REMOVE INVALID QUALIFICATION RISKS
    # ========================================================

    valid_gap_requirements = {
        clean_text(
            item.get(
                "requirement"
            )
        )
        for item
        in personal_fit.get(
            "requirements",
            [],
        )
        if isinstance(
            item,
            dict,
        )
        and clean_text(
            item.get(
                "status"
            )
        )
        in {
            "Partial",
            "No Match",
        }
    }

    unknown_requirements = {
        clean_text(
            item.get(
                "requirement"
            )
        )
        for item
        in personal_fit.get(
            "requirements",
            [],
        )
        if isinstance(
            item,
            dict,
        )
        and clean_text(
            item.get(
                "status"
            )
        )
        == "Unknown"
    }

    # We cannot reliably parse every free-text risk into
    # a requirement, so only remove risks that explicitly
    # reference a known Unknown requirement.

    filtered_risks = []

    for risk in normalized_risks:
        description_lower = (
            risk[
                "description"
            ].lower()
        )

        references_unknown = any(
            requirement
            and requirement.lower()
            in description_lower
            for requirement
            in unknown_requirements
        )

        if references_unknown:
            continue

        filtered_risks.append(
            risk
        )

    normalized_risks = (
        filtered_risks
    )

    # ========================================================
    # DETERMINISTIC SCORES
    # ========================================================

    effort_score = (
        calculate_effort_score(
            estimated_effort
        )
    )

    risk_score = (
        calculate_risk_score(
            normalized_risks
        )
    )

    # ========================================================
    # FINAL CONTRACT
    # ========================================================

    return {
        "estimated_effort":
            estimated_effort,

        "time_pressure":
            clean_text(
                raw.get(
                    "time_pressure"
                )
            )
            or "Unknown",

        "risks":
            normalized_risks,

        "opportunity_cost":
            clean_text(
                raw.get(
                    "opportunity_cost"
                )
            ),

        "effort_reasoning":
            clean_text(
                raw.get(
                    "effort_reasoning"
                )
            ),

        "risk_reasoning":
            clean_text(
                raw.get(
                    "risk_reasoning"
                )
            ),

        "effort_score":
            effort_score,

        "risk_score":
            risk_score,

        "_effort_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Effort & Risk Agent",

            "fallback":
                False,

            "supported_gap_requirements":
                list(
                    valid_gap_requirements
                ),
        },
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    sample_opportunity = {
        "title":
            "AI Engineer",

        "organization":
            "Example Company",

        "category":
            "JOB",

        "deadline":
            "September 30, 2026",

        "requirements": [
            "Python",
            "Production RAG experience",
        ],

        "details": {
            "responsibilities": [
                "Build production RAG systems",
            ],
        },
    }

    sample_personal_fit = {
        "requirements": [
            {
                "requirement":
                    "Python",

                "status":
                    "Match",

                "evidence":
                    "Python project experience.",
            },

            {
                "requirement":
                    "Production RAG experience",

                "status":
                    "Partial",

                "evidence":
                    "User has built a prototype RAG system.",
            },
        ],

        "matching_skills": [
            "Python",
        ],

        "skill_gaps": [
            "Production RAG experience",
        ],

        "personal_fit_score":
            75,
    }

    result = (
        assess_effort_and_risk(
            opportunity=
                sample_opportunity,

            personal_fit=
                sample_personal_fit,
        )
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


    
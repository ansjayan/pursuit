




# agents/value_agent.py

from __future__ import annotations

import json

from pydantic import BaseModel

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

class ValueAssessment(BaseModel):
    learning_value: str = "Unknown"
    portfolio_value: str = "Unknown"

    learning_reasoning: str = ""
    portfolio_reasoning: str = ""


# ============================================================
# VALID VALUES
# ============================================================

VALID_VALUE_LEVELS = {
    "Low",
    "Medium",
    "High",
    "Unknown",
}


def normalize_value_level(
    value,
) -> str:
    text = clean_text(
        value
    ).title()

    if text not in VALID_VALUE_LEVELS:
        return "Unknown"

    return text


# ============================================================
# STRANDS VALUE AGENT
# ============================================================

VALUE_AGENT_INSTRUCTIONS = """
You are PURSUIT's Value Agent.

Your job is to assess two things for the specific user:

1. Learning Value
2. Portfolio Value

Use ONLY the supplied researched opportunity and Personal Fit
evidence.

Do not invent opportunity facts.
Do not use general company reputation.
Do not assume prestigious brands automatically have high value.
Do not assume every technical opportunity is high learning value.

LEARNING VALUE

Assess how much useful career-relevant learning the opportunity
could provide based on explicit opportunity content and the user's
current profile evidence.

High:
- strong opportunity to build meaningful new skills
- meaningful exposure to tools, systems, methods, or domains not
  already fully supported by profile evidence

Medium:
- some useful learning
- partial overlap with current profile plus some new exposure

Low:
- little meaningful new learning beyond what profile evidence
  already supports

Unknown:
- insufficient evidence

PORTFOLIO VALUE

Assess how much the opportunity could strengthen the user's
professional portfolio based only on explicit opportunity facts.

High:
- likely to produce substantial demonstrable work, output,
  project evidence, public artifact, competition result, funded
  work, meaningful responsibility, or similarly strong evidence

Medium:
- some demonstrable professional value, but limited or unclear
  scope

Low:
- little explicit evidence of portfolio-building output

Unknown:
- insufficient evidence

IMPORTANT

Do not infer:
- prestige
- hiring probability
- salary
- brand value
- competition level
- networking value
- resume impact from organization name alone

Return concise reasoning.
"""


def create_value_agent():
    return create_pursuit_agent(
        name=
            "Value Agent",

        instructions=
            VALUE_AGENT_INSTRUCTIONS,

        tier=
            "reasoning",
    )


# ============================================================
# MAIN VALUE WORKFLOW
# ============================================================

def assess_learning_and_portfolio_value(
    user_id: int,
    opportunity: dict,
    personal_fit: dict,
) -> dict:
    """
    Assess opportunity value for a specific PURSUIT user.

    The function signature matches the resumable pipeline.
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

    agent = create_value_agent()

    prompt = f"""
Assess the learning and portfolio value of this opportunity for
this specific user.

USER ID:
{user_id}

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

Return ValueAssessment.

Rules:

- Use only the supplied data.
- Do not invent skills, responsibilities, deliverables, or
  benefits.
- Unknown profile evidence must not be treated as a deficiency.
- If evidence is insufficient for either value dimension, use
  "Unknown".
- learning_value must be exactly:
  Low, Medium, High, or Unknown.
- portfolio_value must be exactly:
  Low, Medium, High, or Unknown.
"""

    try:
        result = agent(
            prompt,
            structured_output_model=
                ValueAssessment,
        )

    except Exception as exc:

        print(
            "[Value] Strands agent failed: "
            f"{exc}"
        )

        return {
            "learning_value":
                "Unknown",

            "portfolio_value":
                "Unknown",

            "learning_reasoning":
                "",

            "portfolio_reasoning":
                "",

            "_value_meta": {
                "framework":
                    "Strands Agents SDK",

                "agent":
                    "Value Agent",

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
        ValueAssessment,
    ):
        raise ValueError(
            "Value Agent returned no valid "
            "structured output."
        )

    raw = structured.model_dump()

    learning_value = (
        normalize_value_level(
            raw.get(
                "learning_value"
            )
        )
    )

    portfolio_value = (
        normalize_value_level(
            raw.get(
                "portfolio_value"
            )
        )
    )

    return {
        "learning_value":
            learning_value,

        "portfolio_value":
            portfolio_value,

        "learning_reasoning":
            clean_text(
                raw.get(
                    "learning_reasoning"
                )
            ),

        "portfolio_reasoning":
            clean_text(
                raw.get(
                    "portfolio_reasoning"
                )
            ),

        "_value_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Value Agent",

            "fallback":
                False,
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

        "description":
            "Build production RAG systems.",

        "requirements": [
            "Python",
            "RAG",
        ],

        "details": {
            "responsibilities": [
                "Build production AI systems",
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
                    "RAG",

                "status":
                    "Partial",

                "evidence":
                    "User has a prototype RAG project.",
            },
        ],

        "matching_skills": [
            "Python",
        ],

        "skill_gaps": [
            "RAG",
        ],

        "profile_evidence": [
            "Python project experience.",
            "Prototype RAG project.",
        ],

        "personal_fit_score":
            75,
    }

    result = (
        assess_learning_and_portfolio_value(
            user_id=
                1,

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



    
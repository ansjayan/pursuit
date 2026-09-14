




# agents/decision_agent.py

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from config.models import create_pursuit_agent


from app.scoring import (
    calculate_score,
    calculate_personal_fit_from_requirements,
    calculate_learning_value,
    calculate_portfolio_value,
    calculate_effort_score,
    calculate_risk_score,
    recommendation_from_score,
)

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


# ============================================================
# STRANDS STRUCTURED OUTPUT
# ============================================================

class DecisionExplanation(BaseModel):
    reasoning: str = ""

    why_recommendation: str = ""

    why_not: str = ""

    what_could_change_decision: str = ""

    next_actions: list[str] = Field(
        default_factory=list
    )


# ============================================================
# RECOMMENDATION
# ============================================================


# ============================================================
# STRANDS DECISION AGENT
# ============================================================

DECISION_AGENT_INSTRUCTIONS = """
You are PURSUIT's Decision Agent.

You are the final explanation stage of a professional opportunity
evaluation pipeline.

The numerical score and recommendation are already calculated by
deterministic application logic.

You MUST NOT:
- change the score
- change the recommendation
- invent opportunity facts
- invent user qualifications
- introduce general company knowledge
- claim an Unknown requirement is a failure
- manufacture reasons merely to justify the recommendation

Your job is to explain WHY the fixed recommendation follows from
the supplied evidence.

Use only:

1. researched opportunity evidence
2. Personal Fit analysis
3. Learning Value analysis
4. Portfolio Value analysis
5. Effort & Risk analysis
6. the fixed deterministic score
7. the fixed deterministic recommendation

NEXT ACTIONS

Every next action must be grounded in one of:

- an explicit opportunity requirement
- a Partial requirement
- a No Match requirement
- an Unknown requirement that the user could verify
- explicit application/submission information
- explicit deadline/time pressure
- explicit effort/risk evidence

Do not suggest:
- networking
- contacting employees
- researching company culture
- asking for referrals
- salary negotiation
- visa actions
- relocation planning

unless supplied evidence explicitly makes such an action relevant.

why_not:
Describe what prevents a stronger recommendation.
If nothing meaningful prevents a stronger recommendation, return
an empty string.

what_could_change_decision:
Describe only evidence-grounded information or improvement that
could materially change the recommendation.
If nothing supported is available, return an empty string.

Keep the explanation concise, professional, and evidence-grounded.
"""


def create_decision_agent():
    return create_pursuit_agent(
        name=
            "Decision Agent",

        instructions=
            DECISION_AGENT_INSTRUCTIONS,

        tier=
            "reasoning",
    )


# ============================================================
# COMPONENT SCORE EXTRACTION
# ============================================================

def calculate_component_scores(
    personal_fit: dict,
    value_assessment: dict,
    risk_assessment: dict,
) -> dict:
    """
    Calculate all deterministic component scores through
    app.scoring.

    This keeps scoring logic centralized outside the LLM.
    """

    requirements = (
        personal_fit.get(
            "requirements",
            [],
        )
    )

    personal_fit_score = (
        personal_fit.get(
            "personal_fit_score"
        )
    )

    # Prefer the already-computed Personal Agent score.
    # Fall back to app.scoring for compatibility.
    if personal_fit_score is None:

        personal_fit_score = (
            calculate_personal_fit_from_requirements(
                requirements
            )
        )

    learning_value = (
        value_assessment.get(
            "learning_value",
            "Unknown",
        )
    )

    portfolio_value = (
        value_assessment.get(
            "portfolio_value",
            "Unknown",
        )
    )

    estimated_effort = (
        risk_assessment.get(
            "estimated_effort",
            "Unknown",
        )
    )

    risks = (
        risk_assessment.get(
            "risks",
            [],
        )
    )

    # --------------------------------------------------------
    # Keep app.scoring authoritative.
    # --------------------------------------------------------

    learning_value_score = (
        calculate_learning_value(
            learning_value
        )
    )

    portfolio_value_score = (
        calculate_portfolio_value(
            portfolio_value
        )
    )

    effort_score = (
        risk_assessment.get(
            "effort_score"
        )
    )

    if effort_score is None:

        effort_score = (
            calculate_effort_score(
                estimated_effort
            )
        )

    risk_score = (
        risk_assessment.get(
            "risk_score"
        )
    )

    if risk_score is None:

        risk_score = (
            calculate_risk_score(
                risks
            )
        )

    return {
        "personal_fit_score":
            personal_fit_score,

        "learning_value_score":
            learning_value_score,

        "portfolio_value_score":
            portfolio_value_score,

        "effort_score":
            effort_score,

        "risk_score":
            risk_score,
    }


# ============================================================
# DETERMINISTIC FINAL SCORE
# ============================================================

def calculate_final_decision(
    personal_fit: dict,
    value_assessment: dict,
    risk_assessment: dict,
) -> dict:
    """
    Calculate final score and recommendation without an LLM.
    """

    component_scores = (
        calculate_component_scores(
            personal_fit=
                personal_fit,

            value_assessment=
                value_assessment,

            risk_assessment=
                risk_assessment,
        )
    )

    final_score = calculate_score(
        component_scores[
            "personal_fit_score"
        ],

        component_scores[
            "learning_value_score"
        ],

        component_scores[
            "portfolio_value_score"
        ],

        component_scores[
            "effort_score"
        ],

        component_scores[
            "risk_score"
        ],
    )

    # Defensive range normalization.
    try:
        final_score = round(
            float(
                final_score
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        final_score = 0

    final_score = max(
        0,
        min(
            100,
            final_score,
        ),
    )

    recommendation = (
        recommendation_from_score(
            final_score
        )
    )

    return {
        "score":
            final_score,

        "recommendation":
            recommendation,

        **component_scores,
    }


# ============================================================
# MAIN DECISION WORKFLOW
# ============================================================

def make_decision(
    opportunity: dict,
    personal_fit: dict,
    risk_assessment: dict,
    value_assessment: dict,
    user_id: int | None = None,
) -> dict:
    """
    Produce PURSUIT's final decision.

    The score and recommendation are deterministic.
    Strands only explains the immutable decision.
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

    if not isinstance(
        risk_assessment,
        dict,
    ):
        raise TypeError(
            "risk_assessment must be a dictionary."
        )

    if not isinstance(
        value_assessment,
        dict,
    ):
        raise TypeError(
            "value_assessment must be a dictionary."
        )

    # ========================================================
    # DETERMINISTIC DECISION FIRST
    # ========================================================

    deterministic = (
        calculate_final_decision(
            personal_fit=
                personal_fit,

            value_assessment=
                value_assessment,

            risk_assessment=
                risk_assessment,
        )
    )

    final_score = (
        deterministic[
            "score"
        ]
    )

    recommendation = (
        deterministic[
            "recommendation"
        ]
    )

    # ========================================================
    # STRANDS EXPLANATION
    # ========================================================

    agent = create_decision_agent()

    prompt = f"""
Explain this already-calculated PURSUIT decision.

USER ID:
{user_id if user_id is not None else "Not supplied"}

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

VALUE ASSESSMENT:

{json.dumps(
    value_assessment,
    indent=2,
    ensure_ascii=False,
)}

EFFORT & RISK ASSESSMENT:

{json.dumps(
    risk_assessment,
    indent=2,
    ensure_ascii=False,
)}

DETERMINISTIC COMPONENT SCORES:

{json.dumps(
    {
        "personal_fit_score":
            deterministic[
                "personal_fit_score"
            ],

        "learning_value_score":
            deterministic[
                "learning_value_score"
            ],

        "portfolio_value_score":
            deterministic[
                "portfolio_value_score"
            ],

        "effort_score":
            deterministic[
                "effort_score"
            ],

        "risk_score":
            deterministic[
                "risk_score"
            ],
    },
    indent=2,
)}

FINAL SCORE:

{final_score}

FIXED RECOMMENDATION:

{recommendation}

IMPORTANT:

The score and recommendation above are immutable.

You are not deciding again.

You are explaining the deterministic decision.

Return DecisionExplanation.
"""

    try:

        result = agent(
            prompt,

            structured_output_model=
                DecisionExplanation,
        )

    except Exception as exc:

        print(
            "[Decision] Strands agent failed: "
            f"{exc}"
        )

        return {
            "score":
                final_score,

            "recommendation":
                recommendation,

            "personal_fit_score":
                deterministic[
                    "personal_fit_score"
                ],

            "learning_value_score":
                deterministic[
                    "learning_value_score"
                ],

            "portfolio_value_score":
                deterministic[
                    "portfolio_value_score"
                ],

            "effort_score":
                deterministic[
                    "effort_score"
                ],

            "risk_score":
                deterministic[
                    "risk_score"
                ],

            "reasoning":
                "",

            "why_recommendation":
                "",

            "why_not":
                "",

            "what_could_change_decision":
                "",

            "next_actions":
                [],

            "_decision_meta": {
                "framework":
                    "Strands Agents SDK",

                "agent":
                    "Decision Agent",

                "scoring":
                    "deterministic",

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
        DecisionExplanation,
    ):

        raise ValueError(
            "Decision Agent returned no valid "
            "structured output."
        )

    explanation = (
        structured.model_dump()
    )

    # ========================================================
    # FINAL IMMUTABLE CONTRACT
    # ========================================================

    return {
        # ----------------------------------------------------
        # Deterministic values
        # ----------------------------------------------------

        "score":
            final_score,

        "recommendation":
            recommendation,

        "personal_fit_score":
            deterministic[
                "personal_fit_score"
            ],

        "learning_value_score":
            deterministic[
                "learning_value_score"
            ],

        "portfolio_value_score":
            deterministic[
                "portfolio_value_score"
            ],

        "effort_score":
            deterministic[
                "effort_score"
            ],

        "risk_score":
            deterministic[
                "risk_score"
            ],

        # ----------------------------------------------------
        # Strands explanation
        # ----------------------------------------------------

        "reasoning":
            clean_text(
                explanation.get(
                    "reasoning"
                )
            ),

        "why_recommendation":
            clean_text(
                explanation.get(
                    "why_recommendation"
                )
            ),

        "why_not":
            clean_text(
                explanation.get(
                    "why_not"
                )
            ),

        "what_could_change_decision":
            clean_text(
                explanation.get(
                    "what_could_change_decision"
                )
            ),

        "next_actions":
            clean_string_list(
                explanation.get(
                    "next_actions"
                )
            ),

        "_decision_meta": {
            "framework":
                "Strands Agents SDK",

            "agent":
                "Decision Agent",

            "scoring":
                "deterministic",

            "recommendation_thresholds": {
                "PURSUE":
                    "score >= 70",

                "REVIEW":
                    "50 <= score < 70",

                "REJECT":
                    "score < 50",
            },

            "fallback":
                False,
        },
    }


# ============================================================
# PIPELINE-COMPATIBLE ALIAS
# ============================================================

def decide_opportunity(
    opportunity: dict,
    personal_fit: dict,
    risk_assessment: dict,
    value_assessment: dict,
    user_id: int | None = None,
) -> dict:
    """
    Friendly alias for pipeline integrations.
    """

    return make_decision(
        opportunity=
            opportunity,

        personal_fit=
            personal_fit,

        risk_assessment=
            risk_assessment,

        value_assessment=
            value_assessment,

        user_id=
            user_id,
    )


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

        "requirements": [
            "Python",
            "Production RAG experience",
        ],
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
                    "Prototype RAG project.",
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

    sample_value = {
        "learning_value":
            "High",

        "portfolio_value":
            "High",

        "learning_reasoning":
            "Opportunity exposes the user to production RAG.",

        "portfolio_reasoning":
            "Work could produce substantial production AI evidence.",
    }

    sample_risk = {
        "estimated_effort":
            "Medium",

        "time_pressure":
            "Unknown",

        "risks": [
            {
                "description":
                    "Production RAG experience is only partially supported.",

                "severity":
                    "Medium",
            },
        ],

        "opportunity_cost":
            "",

        "effort_score":
            60,

        "risk_score":
            75,
    }

    result = make_decision(
        opportunity=
            sample_opportunity,

        personal_fit=
            sample_personal_fit,

        risk_assessment=
            sample_risk,

        value_assessment=
            sample_value,

        user_id=
            1,
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )



    





# app/scoring.py

from __future__ import annotations


# ============================================================
# SCORE WEIGHTS
# ============================================================

PERSONAL_FIT_WEIGHT = 0.35
LEARNING_VALUE_WEIGHT = 0.20
PORTFOLIO_VALUE_WEIGHT = 0.20
EFFORT_WEIGHT = 0.10
RISK_WEIGHT = 0.15


# ============================================================
# HELPERS
# ============================================================

def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    ).strip()


def clamp_score(
    value,
) -> int:
    try:
        value = round(
            float(value)
        )
    except (
        TypeError,
        ValueError,
    ):
        value = 0

    return max(
        0,
        min(
            100,
            value,
        ),
    )


# ============================================================
# PERSONAL FIT
# ============================================================

def calculate_personal_fit_from_requirements(
    requirements: list,
) -> int:
    """
    Calculate Personal Fit using only requirements that can
    actually be evaluated.

    Match      = 100%
    Partial    = 50%
    No Match   = 0%
    Unknown    = excluded from denominator

    This is intentional:
    missing profile evidence is uncertainty, not failure.
    """

    if not isinstance(
        requirements,
        list,
    ):
        return 0

    points = 0.0
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

        if status == "Match":
            points += 1.0
            evaluable += 1

        elif status == "Partial":
            points += 0.5
            evaluable += 1

        elif status == "No Match":
            evaluable += 1

    if evaluable == 0:
        return 0

    return clamp_score(
        (
            points
            / evaluable
        )
        * 100
    )


# ============================================================
# VALUE SCORES
# ============================================================

def calculate_learning_value(
    learning_value: str,
) -> int:
    """
    Convert qualitative learning value into score.
    """

    mapping = {
        "High":
            90,

        "Medium":
            65,

        "Low":
            35,

        "Unknown":
            50,
    }

    normalized = clean_text(
        learning_value
    ).title()

    return mapping.get(
        normalized,
        50,
    )


def calculate_portfolio_value(
    portfolio_value: str,
) -> int:
    """
    Convert qualitative portfolio value into score.
    """

    mapping = {
        "High":
            90,

        "Medium":
            65,

        "Low":
            35,

        "Unknown":
            50,
    }

    normalized = clean_text(
        portfolio_value
    ).title()

    return mapping.get(
        normalized,
        50,
    )


# ============================================================
# EFFORT SCORE
# ============================================================

def calculate_effort_score(
    estimated_effort: str,
) -> int:
    """
    Higher score means easier / less costly to pursue.
    """

    mapping = {
        "Low":
            90,

        "Medium":
            60,

        "High":
            30,

        "Unknown":
            50,
    }

    normalized = clean_text(
        estimated_effort
    ).title()

    return mapping.get(
        normalized,
        50,
    )


# ============================================================
# RISK SCORE
# ============================================================

def calculate_risk_score(
    risks: list,
) -> int:
    """
    Higher score means safer / lower risk.

    The most severe supported risk dominates, while additional
    risks add a smaller cumulative penalty.
    """

    if not isinstance(
        risks,
        list,
    ):
        return 90

    if not risks:
        return 90

    severity_penalty = {
        "Low":
            10,

        "Medium":
            25,

        "High":
            45,

        "Critical":
            70,
    }

    penalties = []

    for risk in risks:

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

        severity = clean_text(
            risk.get(
                "severity"
            )
        ).title()

        penalty = (
            severity_penalty.get(
                severity,
                10,
            )
        )

        penalties.append(
            penalty
        )

    if not penalties:
        return 90

    # Most serious supported risk is primary.
    total_penalty = max(
        penalties
    )

    # Extra risks add limited cumulative pressure.
    if len(
        penalties
    ) > 1:

        extra_penalty = min(
            20,
            (
                len(penalties)
                - 1
            )
            * 5,
        )

        total_penalty += (
            extra_penalty
        )

    return clamp_score(
        100
        - total_penalty
    )


# ============================================================
# FINAL SCORE
# ============================================================

def calculate_score(
    personal_fit_score,
    learning_value_score,
    portfolio_value_score,
    effort_score,
    risk_score,
) -> int:
    """
    Calculate PURSUIT's final opportunity score.

    Weighting:

    Personal Fit       35%
    Learning Value     20%
    Portfolio Value    20%
    Effort             10%
    Risk               15%
    """

    personal_fit_score = clamp_score(
        personal_fit_score
    )

    learning_value_score = clamp_score(
        learning_value_score
    )

    portfolio_value_score = clamp_score(
        portfolio_value_score
    )

    effort_score = clamp_score(
        effort_score
    )

    risk_score = clamp_score(
        risk_score
    )

    final_score = (
        personal_fit_score
        * PERSONAL_FIT_WEIGHT

        + learning_value_score
        * LEARNING_VALUE_WEIGHT

        + portfolio_value_score
        * PORTFOLIO_VALUE_WEIGHT

        + effort_score
        * EFFORT_WEIGHT

        + risk_score
        * RISK_WEIGHT
    )

    return clamp_score(
        final_score
    )


# ============================================================
# RECOMMENDATION
# ============================================================

def recommendation_from_score(
    score,
) -> str:
    """
    Final recommendation is deterministic.

    >= 70       PURSUE
    50 - 69     REVIEW
    < 50        REJECT
    """

    score = clamp_score(
        score
    )

    if score >= 70:
        return "PURSUE"

    if score >= 50:
        return "REVIEW"

    return "REJECT"


# ============================================================
# COMPLETE SCORING SNAPSHOT
# ============================================================

def calculate_scoring_snapshot(
    *,
    requirements: list,
    learning_value: str,
    portfolio_value: str,
    estimated_effort: str,
    risks: list,
) -> dict:
    """
    Convenience helper used by Decision Agent or tests.
    """

    personal_fit_score = (
        calculate_personal_fit_from_requirements(
            requirements
        )
    )

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
        calculate_effort_score(
            estimated_effort
        )
    )

    risk_score = (
        calculate_risk_score(
            risks
        )
    )

    final_score = (
        calculate_score(
            personal_fit_score,
            learning_value_score,
            portfolio_value_score,
            effort_score,
            risk_score,
        )
    )

    recommendation = (
        recommendation_from_score(
            final_score
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

        "score":
            final_score,

        "recommendation":
            recommendation,
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    sample_requirements = [
        {
            "requirement":
                "Python",

            "status":
                "Match",

            "evidence":
                "Python projects.",
        },

        {
            "requirement":
                "AWS",

            "status":
                "Partial",

            "evidence":
                "Some AWS experience.",
        },

        {
            "requirement":
                "Kubernetes",

            "status":
                "Unknown",

            "evidence":
                "",
        },
    ]

    snapshot = (
        calculate_scoring_snapshot(
            requirements=
                sample_requirements,

            learning_value=
                "High",

            portfolio_value=
                "High",

            estimated_effort=
                "Medium",

            risks=[
                {
                    "description":
                        "AWS requirement is partially met.",

                    "severity":
                        "Medium",
                }
            ],
        )
    )

    print(
        snapshot
    )



    
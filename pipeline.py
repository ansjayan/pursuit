




# pipeline.py

from __future__ import annotations

from typing import Any, Optional

from agents.discovery_agent import discover_opportunities
from agents.research_agent import research_opportunity
from agents.personal_agent import analyze_personal_fit
from agents.value_agent import assess_learning_and_portfolio_value
from agents.effort_agent import assess_effort_and_risk
from agents.decision_agent import make_decision

from app.database import (
    add_opportunity_source,
    create_evaluation,
    create_or_update_opportunity,
    ensure_pipeline_state,
    find_opportunity_by_source_url,
    from_json,
    get_pipeline_state,
    get_primary_source,
    get_resumable_pipeline_opportunities,
    get_user_opportunity,
    mark_opportunity_verified,
    mark_pipeline_completed,
    mark_pipeline_stage_completed,
    mark_pipeline_stage_failed,
    mark_pipeline_stage_started,
    reset_pipeline_state,
    update_opportunity_evaluation,
)


# ============================================================
# FINAL PIPELINE CONFIGURATION
# ============================================================

PIPELINE_VERSION = "4.0"
EVALUATION_VERSION = "4.0"

STAGE_RESEARCH = "RESEARCH"
STAGE_PERSONAL_FIT = "PERSONAL_FIT"
STAGE_VALUE = "VALUE"
STAGE_EFFORT_RISK = "EFFORT_RISK"
STAGE_DECISION = "DECISION"

COMPLETED = "COMPLETED"


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def decode_json_object(value: Any) -> dict:
    """Decode a DB JSON column defensively."""
    if isinstance(value, dict):
        return value
    parsed = from_json(value, {})
    return parsed if isinstance(parsed, dict) else {}


def decode_json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    parsed = from_json(value, [])
    return parsed if isinstance(parsed, list) else []


def get_source_url(opportunity: dict) -> str:
    """Canonical field is source_url; url is legacy compatibility."""
    return clean_text(
        opportunity.get("source_url")
        or opportunity.get("url")
    )


def get_source_type(opportunity: dict) -> str:
    return clean_text(
        opportunity.get("source_type")
        or "OTHER"
    )


def normalize_recommendation_for_app(value: Any) -> str:
    """PURSUIT's final UI vocabulary is PURSUE / REVIEW / REJECT."""
    text = clean_text(value).upper()
    if text == "INVESTIGATE":
        return "REVIEW"
    if text in {"PURSUE", "REVIEW", "REJECT"}:
        return text
    return text



# ============================================================
# DATABASE ROW -> CANONICAL OPPORTUNITY
# ============================================================

def opportunity_from_database(user_id: int, opportunity_id: int) -> dict:
    """Reconstruct an opportunity dict when resuming after a failure."""
    row = get_user_opportunity(user_id, opportunity_id)
    if not row:
        raise ValueError("Opportunity not found for this user.")

    primary_source = get_primary_source(opportunity_id)

    source_url = ""
    source_type = "OTHER"
    source_external_id = ""

    if primary_source:
        source_url = clean_text(primary_source["source_url"])
        source_type = clean_text(primary_source["source_type"] or "OTHER")
        try:
            source_external_id = clean_text(primary_source["external_id"])
        except (KeyError, IndexError):
            source_external_id = ""

    return {
        "title": clean_text(row["title"]),
        "organization": clean_text(row["organization"]),
        "category": clean_text(row["category"] or "OTHER"),
        "external_id": clean_text(row["external_id"] or source_external_id),
        "source_url": source_url,
        "source_type": source_type,
        "location": clean_text(row["location"]),
        "work_arrangement": clean_text(row["work_arrangement"] or "UNKNOWN"),
        "deadline": clean_text(row["deadline"]),
        "reward": clean_text(row["reward"]),
        "description": clean_text(row["description"]),
        "requirements": decode_json_list(row["requirements"]),
        "eligibility": decode_json_list(row["eligibility"]),
        "submission": clean_text(row["submission"]),
        "details": decode_json_object(row["details"]),
        "evidence": decode_json_list(row["evidence"]),
        "activity_status": clean_text(row["activity_status"] or "UNKNOWN"),
    }


# ============================================================
# OPPORTUNITY PERSISTENCE
# ============================================================

def save_opportunity(
    user_id: int,
    opportunity: dict,
    *,
    fallback: Optional[dict] = None,
) -> int:
    """Create/update the canonical opportunity row and primary source."""
    fallback = fallback if isinstance(fallback, dict) else {}

    source_url = get_source_url(opportunity) or get_source_url(fallback)
    if not source_url:
        raise ValueError("Cannot persist an opportunity without source_url.")

    title = clean_text(opportunity.get("title")) or clean_text(fallback.get("title"))
    organization = (
        clean_text(opportunity.get("organization"))
        or clean_text(fallback.get("organization"))
    )
    category = (
        clean_text(opportunity.get("category"))
        or clean_text(fallback.get("category"))
        or "OTHER"
    )
    source_type = (
        clean_text(opportunity.get("source_type"))
        or clean_text(fallback.get("source_type"))
        or "OTHER"
    )
    external_id = (
        clean_text(opportunity.get("external_id"))
        or clean_text(fallback.get("external_id"))
        or None
    )

    opportunity_id = create_or_update_opportunity(
        user_id=user_id,
        title=title,
        organization=organization,
        category=category,
        source_url=source_url,
        source_type=source_type,
        source_name=organization or None,
        external_id=external_id,
        location=clean_text(
            opportunity.get("location") or fallback.get("location")
        ),
        work_arrangement=clean_text(
            opportunity.get("work_arrangement")
            or fallback.get("work_arrangement")
            or "UNKNOWN"
        ),
        deadline=(
            opportunity.get("deadline")
            if opportunity.get("deadline") is not None
            else fallback.get("deadline")
        ),
        reward=(
            opportunity.get("reward")
            if opportunity.get("reward") is not None
            else fallback.get("reward")
        ),
        description=(
            opportunity.get("description")
            if opportunity.get("description") is not None
            else fallback.get("description")
        ),
        requirements=safe_list(
            opportunity.get("requirements")
            if opportunity.get("requirements") is not None
            else fallback.get("requirements")
        ),
        eligibility=safe_list(
            opportunity.get("eligibility")
            if opportunity.get("eligibility") is not None
            else fallback.get("eligibility")
        ),
        submission=(
            opportunity.get("submission")
            if opportunity.get("submission") is not None
            else fallback.get("submission")
        ),
        details=safe_dict(
            opportunity.get("details")
            if opportunity.get("details") is not None
            else fallback.get("details")
        ),
        evidence=safe_list(
            opportunity.get("evidence")
            if opportunity.get("evidence") is not None
            else fallback.get("evidence")
        ),
        activity_status=clean_text(
            opportunity.get("activity_status")
            or fallback.get("activity_status")
            or "UNKNOWN"
        ),
        is_primary_source=True,
    )

    ensure_pipeline_state(opportunity_id)
    return opportunity_id


def save_alternate_sources(opportunity_id: int, discovered: dict) -> None:
    """Persist duplicate URLs discovered for the same real-world opportunity."""
    discovery_meta = safe_dict(discovered.get("_discovery_meta"))
    alternate_sources = safe_list(discovery_meta.get("alternate_sources"))

    for source in alternate_sources:
        if not isinstance(source, dict):
            continue

        source_url = clean_text(source.get("url"))
        if not source_url:
            continue

        try:
            add_opportunity_source(
                opportunity_id=opportunity_id,
                source_url=source_url,
                source_type=clean_text(source.get("source_type") or "OTHER"),
                source_name=clean_text(source.get("domain")) or None,
                is_primary=False,
                external_id=clean_text(source.get("external_id")) or None,
            )
        except Exception as exc:
            # An alternate source must never invalidate the canonical opportunity.
            print(
                "[Pipeline] Alternate source save failed: "
                f"{source_url} | {exc}"
            )


# ============================================================
# RESEARCH INPUT COMPATIBILITY
# ============================================================

def prepare_research_input(opportunity: dict) -> dict:
    """Prepare canonical input for the Strands Research Agent."""
    result = dict(opportunity)
    result["source_url"] = get_source_url(opportunity)
    return result


# ============================================================
# PIPELINE STATE HELPERS
# ============================================================

def _stage_is_complete(state, status_column: str) -> bool:
    return bool(state and clean_text(state[status_column]).upper() == COMPLETED)


def _load_stage_output(state, output_column: str) -> dict:
    if not state:
        return {}
    return decode_json_object(state[output_column])


def _run_stage(
    opportunity_id: int,
    stage: str,
    callable_,
) -> dict:
    """Run one stage and atomically persist success/failure state."""
    mark_pipeline_stage_started(opportunity_id, stage)

    try:
        output = callable_()
        if not isinstance(output, dict):
            raise ValueError(f"{stage} returned a non-object result.")
        mark_pipeline_stage_completed(opportunity_id, stage, output)
        return output
    except Exception as exc:
        mark_pipeline_stage_failed(opportunity_id, stage, exc)
        raise


# ============================================================
# STRANDS DECISION CALL
# ============================================================

def call_decision_agent(
    *,
    user_id: int,
    opportunity: dict,
    personal_fit: dict,
    risk_assessment: dict,
    value_assessment: dict,
) -> dict:
    """
    Call the final Strands Decision Agent using its canonical contract.

    The Decision Agent receives complete evidence from all upstream
    stages. Numeric scoring and PURSUE / REVIEW / REJECT remain
    deterministic inside app.scoring / decision_agent.py.
    """
    decision = make_decision(
        opportunity=opportunity,
        personal_fit=personal_fit,
        risk_assessment=risk_assessment,
        value_assessment=value_assessment,
        user_id=user_id,
    )

    if not isinstance(decision, dict):
        raise ValueError(
            "Decision Agent returned invalid data."
        )

    decision = dict(decision)
    decision["recommendation"] = normalize_recommendation_for_app(
        decision.get("recommendation")
    )

    return decision


# ============================================================
# RESUMABLE EVALUATION CORE
# ============================================================

def evaluate_saved_opportunity(
    *,
    user_id: int,
    opportunity_id: int,
    discovered_fallback: Optional[dict] = None,
) -> dict:
    """
    Resume or run all remaining evaluation stages for one saved opportunity.

    Completed stage outputs are loaded from SQLite and are NOT recomputed.
    """
    discovered_fallback = (
        discovered_fallback if isinstance(discovered_fallback, dict) else {}
    )

    ensure_pipeline_state(opportunity_id)
    base_opportunity = opportunity_from_database(user_id, opportunity_id)
    state = get_pipeline_state(opportunity_id)

    # ========================================================
    # 1. RESEARCH
    # ========================================================

    if _stage_is_complete(state, "research_status"):
        researched = _load_stage_output(state, "research_output")
        print("[Pipeline] RESEARCH already complete — reused cached output.")
    else:
        print("[Pipeline] Stage: RESEARCH")

        def run_research():
            result = research_opportunity(
                prepare_research_input(base_opportunity)
            )
            if not isinstance(result, dict):
                raise ValueError("Research Agent returned invalid data.")

            result = dict(result)
            result["source_url"] = get_source_url(base_opportunity)
            result["source_type"] = (
                result.get("source_type")
                or base_opportunity.get("source_type")
                or "OTHER"
            )
            result.setdefault("category", base_opportunity.get("category", "OTHER"))
            return result

        researched = _run_stage(
            opportunity_id,
            STAGE_RESEARCH,
            run_research,
        )

        # Enrich the canonical opportunity immediately after successful Research.
        opportunity_id = save_opportunity(
            user_id,
            researched,
            fallback=discovered_fallback or base_opportunity,
        )
        mark_opportunity_verified(
            opportunity_id,
            researched.get("activity_status"),
        )

    # Re-read state because the stage may just have completed.
    state = get_pipeline_state(opportunity_id)

    # ========================================================
    # 2. PERSONAL FIT
    # ========================================================

    if _stage_is_complete(state, "personal_fit_status"):
        personal_fit = _load_stage_output(state, "personal_fit_output")
        print("[Pipeline] PERSONAL_FIT already complete — reused cached output.")
    else:
        print("[Pipeline] Stage: PERSONAL_FIT")
        personal_fit = _run_stage(
            opportunity_id,
            STAGE_PERSONAL_FIT,
            lambda: analyze_personal_fit(
                user_id=user_id,
                opportunity=researched,
            ),
        )

    state = get_pipeline_state(opportunity_id)

    # ========================================================
    # 3. VALUE
    # ========================================================

    if _stage_is_complete(state, "value_status"):
        value_assessment = _load_stage_output(state, "value_output")
        print("[Pipeline] VALUE already complete — reused cached output.")
    else:
        print("[Pipeline] Stage: VALUE")
        value_assessment = _run_stage(
            opportunity_id,
            STAGE_VALUE,
            lambda: assess_learning_and_portfolio_value(
                user_id=user_id,
                opportunity=researched,
                personal_fit=personal_fit,
            ),
        )

    state = get_pipeline_state(opportunity_id)

    # ========================================================
    # 4. EFFORT / RISK
    # ========================================================

    if _stage_is_complete(state, "effort_risk_status"):
        risk_assessment = _load_stage_output(state, "risk_output")
        print("[Pipeline] EFFORT_RISK already complete — reused cached output.")
    else:
        print("[Pipeline] Stage: EFFORT_RISK")
        risk_assessment = _run_stage(
            opportunity_id,
            STAGE_EFFORT_RISK,
            lambda: assess_effort_and_risk(
                opportunity=researched,
                personal_fit=personal_fit,
            ),
        )

    state = get_pipeline_state(opportunity_id)

    # ========================================================
    # 5. DECISION
    # ========================================================

    if _stage_is_complete(state, "decision_status"):
        decision = _load_stage_output(state, "decision_output")
        decision["recommendation"] = normalize_recommendation_for_app(
            decision.get("recommendation")
        )
        print("[Pipeline] DECISION already complete — reused cached output.")
    else:
        print("[Pipeline] Stage: DECISION")
        decision = _run_stage(
            opportunity_id,
            STAGE_DECISION,
            lambda: call_decision_agent(
                user_id=user_id,
                opportunity=researched,
                personal_fit=personal_fit,
                risk_assessment=risk_assessment,
                value_assessment=value_assessment,
            ),
        )

    return {
        "opportunity_id": opportunity_id,
        "opportunity": researched,
        "personal_fit": personal_fit,
        "value_assessment": value_assessment,
        "risk_assessment": risk_assessment,
        "decision": decision,
    }


# ============================================================
# FINAL EVALUATION SNAPSHOT
# ============================================================

def save_final_evaluation(evaluation: dict) -> int:
    opportunity_id = int(evaluation["opportunity_id"])
    researched = evaluation["opportunity"]
    personal_fit = evaluation["personal_fit"]
    value_assessment = evaluation["value_assessment"]
    risk_assessment = evaluation["risk_assessment"]
    decision = evaluation["decision"]

    score = decision.get("score")
    recommendation = normalize_recommendation_for_app(
        decision.get("recommendation")
    )
    matching_skills = safe_list(personal_fit.get("matching_skills"))
    skill_gaps = safe_list(personal_fit.get("skill_gaps"))

    update_opportunity_evaluation(
        opportunity_id=opportunity_id,
        score=score,
        recommendation=recommendation,
        matching_skills=matching_skills,
        skill_gaps=skill_gaps,
    )

    evaluation_id = create_evaluation(
        opportunity_id=opportunity_id,
        personal_fit_score=personal_fit.get("personal_fit_score"),
        learning_value=value_assessment.get("learning_value"),
        portfolio_value=value_assessment.get("portfolio_value"),
        effort_score=risk_assessment.get("effort_score"),
        risk_score=risk_assessment.get("risk_score"),
        overall_score=score,
        recommendation=recommendation,
        reasoning=clean_text(decision.get("reasoning")),
        why_recommendation=clean_text(decision.get("why_recommendation")),
        requirements_analysis=safe_list(personal_fit.get("requirements")),
        personal_fit_analysis={
            "personal_fit_score": personal_fit.get("personal_fit_score"),
            "requirements": safe_list(personal_fit.get("requirements")),
            "matching_skills": matching_skills,
            "skill_gaps": skill_gaps,
            "profile_evidence": safe_list(personal_fit.get("profile_evidence")),
        },
        effort_risk_analysis={
            "effort_score": risk_assessment.get("effort_score"),
            "risk_score": risk_assessment.get("risk_score"),
            "estimated_effort": risk_assessment.get("estimated_effort"),
            "time_pressure": risk_assessment.get("time_pressure"),
            "risks": safe_list(risk_assessment.get("risks")),
            "opportunity_cost": risk_assessment.get("opportunity_cost"),
        },
        why_not_analysis=clean_text(decision.get("why_not")),
        what_could_change_decision=clean_text(
            decision.get("what_could_change_decision")
        ),
        estimated_effort=risk_assessment.get("estimated_effort"),
        time_pressure=risk_assessment.get("time_pressure"),
        risks=safe_list(risk_assessment.get("risks")),
        opportunity_cost=risk_assessment.get("opportunity_cost"),
        next_actions=safe_list(decision.get("next_actions")),
        research_output=researched,
        personal_fit_output=personal_fit,
        value_output=value_assessment,
        risk_output=risk_assessment,
        decision_output=decision,
        agent_output={
            "research": researched,
            "personal_fit": personal_fit,
            "value": value_assessment,
            "effort_risk": risk_assessment,
            "decision": decision,
        },
        model_info={
            "pipeline": "PURSUIT",
            "framework": "Strands Agents SDK",
            "pipeline_version": PIPELINE_VERSION,
            "stages": [
                "DISCOVERY",
                "RESEARCH",
                "PERSONAL_FIT",
                "VALUE",
                "EFFORT_RISK",
                "DECISION",
            ],
        },
        evaluation_version=EVALUATION_VERSION,
    )

    mark_pipeline_completed(opportunity_id)
    return evaluation_id


# ============================================================
# PROCESS ONE NEWLY DISCOVERED OPPORTUNITY
# ============================================================

def process_discovered_opportunity(
    *,
    user_id: int,
    discovered: dict,
) -> dict:
    source_url = get_source_url(discovered)
    if not source_url:
        raise ValueError("Discovered opportunity has no source_url.")

    title = clean_text(discovered.get("title")) or "Pending research"

    existing = find_opportunity_by_source_url(user_id, source_url)

    if existing:
        opportunity_id = int(existing["id"])
        state = get_pipeline_state(opportunity_id)

        if state and clean_text(state["pipeline_status"]).upper() == COMPLETED:
            return {
                "opportunity_id": opportunity_id,
                "title": existing["title"],
                "organization": existing["organization"],
                "category": existing["category"],
                "source_url": source_url,
                "score": existing["score"],
                "recommendation": normalize_recommendation_for_app(
                    existing["recommendation"]
                ),
                "evaluated": True,
                "existing": True,
            }

        print(
            "[Pipeline] Existing incomplete opportunity found; resuming: "
            f"{title}"
        )
    else:
        opportunity_id = save_opportunity(
            user_id,
            discovered,
        )
        save_alternate_sources(opportunity_id, discovered)
        print(
            "[Pipeline] Saved DISCOVERED candidate "
            f"id={opportunity_id}: {title}"
        )

    try:
        evaluation = evaluate_saved_opportunity(
            user_id=user_id,
            opportunity_id=opportunity_id,
            discovered_fallback=discovered,
        )
        save_final_evaluation(evaluation)
    except Exception as exc:
        # The failing stage has already been recorded by _run_stage().
        state = get_pipeline_state(opportunity_id)
        return {
            "opportunity_id": opportunity_id,
            "title": title,
            "organization": clean_text(discovered.get("organization")),
            "category": clean_text(discovered.get("category") or "OTHER"),
            "source_url": source_url,
            "evaluated": False,
            "pipeline_status": clean_text(state["pipeline_status"]) if state else "FAILED",
            "current_stage": clean_text(state["current_stage"]) if state else "",
            "error": str(exc),
        }

    researched = evaluation["opportunity"]
    decision = evaluation["decision"]

    return {
        "opportunity_id": opportunity_id,
        "title": clean_text(researched.get("title")) or title,
        "organization": clean_text(
            researched.get("organization") or discovered.get("organization")
        ),
        "category": clean_text(
            researched.get("category") or discovered.get("category") or "OTHER"
        ),
        "source_url": source_url,
        "score": decision.get("score"),
        "recommendation": normalize_recommendation_for_app(
            decision.get("recommendation")
        ),
        "evaluated": True,
        "existing": bool(existing),
    }


# ============================================================
# AUTOMATIC DISCOVERY -> EVALUATION
# ============================================================

def discover_and_evaluate(
    user_id: int,
    requested_types=None,
    max_opportunities: int = 10,
    search_preferences: str = "",
) -> list:
    """Complete automatic PURSUIT workflow."""
    discovered = discover_opportunities(
        user_id=user_id,
        requested_types=requested_types,
        max_opportunities=max_opportunities,
        search_preferences=search_preferences,
    )

    if not discovered:
        print("[Pipeline] No opportunities discovered.")
        return []

    results = []

    print(
        "[Pipeline] Starting/resuming evaluation for "
        f"{len(discovered)} opportunity/opportunities."
    )

    for index, opportunity in enumerate(discovered, start=1):
        print("=" * 72)
        print(
            f"[Pipeline] Opportunity {index}/{len(discovered)}: "
            f"{opportunity.get('title', 'Untitled')}"
        )

        try:
            result = process_discovered_opportunity(
                user_id=user_id,
                discovered=opportunity,
            )
        except Exception as exc:
            # Failure before an opportunity row/stage could be established.
            result = {
                "opportunity_id": None,
                "title": clean_text(opportunity.get("title")) or "Untitled",
                "source_url": get_source_url(opportunity),
                "evaluated": False,
                "error": str(exc),
            }

        results.append(result)

    successful = sum(1 for item in results if item.get("evaluated"))
    incomplete = len(results) - successful

    print("=" * 72)
    print(f"[Pipeline] Finished. Complete={successful}, incomplete={incomplete}")

    return results


# ============================================================
# RESUME PREVIOUSLY INTERRUPTED PIPELINES
# ============================================================

def resume_incomplete_evaluations(
    user_id: int,
    limit: int = 20,
) -> list:
    """
    Resume opportunities that previously stopped because of rate limits,
    provider errors, timeouts, app restarts, etc.
    """
    rows = get_resumable_pipeline_opportunities(
        user_id=user_id,
        limit=limit,
    )

    results = []

    for row in rows:
        opportunity_id = int(row["id"])
        title = clean_text(row["title"]) or "Pending research"

        print("=" * 72)
        print(
            f"[Pipeline] Resuming opportunity {opportunity_id}: {title} "
            f"from {row['current_stage']}"
        )

        try:
            evaluation = evaluate_saved_opportunity(
                user_id=user_id,
                opportunity_id=opportunity_id,
            )
            save_final_evaluation(evaluation)

            decision = evaluation["decision"]
            opportunity = evaluation["opportunity"]

            results.append({
                "opportunity_id": opportunity_id,
                "title": clean_text(opportunity.get("title")) or title,
                "organization": clean_text(opportunity.get("organization")),
                "category": clean_text(opportunity.get("category") or "OTHER"),
                "source_url": get_source_url(opportunity),
                "score": decision.get("score"),
                "recommendation": normalize_recommendation_for_app(
                    decision.get("recommendation")
                ),
                "evaluated": True,
                "resumed": True,
            })

        except Exception as exc:
            state = get_pipeline_state(opportunity_id)
            results.append({
                "opportunity_id": opportunity_id,
                "title": title,
                "evaluated": False,
                "resumed": True,
                "pipeline_status": clean_text(state["pipeline_status"]) if state else "FAILED",
                "current_stage": clean_text(state["current_stage"]) if state else "",
                "error": str(exc),
            })

    return results


# ============================================================
# MANUAL "EVALUATE URL" WORKFLOW FOR STREAMLIT
# ============================================================

def evaluate_url(
    user_id: int,
    url: str,
    category: str = "OTHER",
    *,
    force_restart: bool = False,
) -> dict:
    """
    Evaluate a URL supplied by the user.

    If the URL is already known but incomplete, resume it.
    If already complete, return the saved summary unless force_restart=True.
    """
    url = clean_text(url)
    if not url:
        raise ValueError("URL is required.")

    existing = find_opportunity_by_source_url(user_id, url)

    if existing:
        opportunity_id = int(existing["id"])
        state = get_pipeline_state(opportunity_id)

        if force_restart:
            reset_pipeline_state(opportunity_id)
        elif state and clean_text(state["pipeline_status"]).upper() == COMPLETED:
            return {
                "opportunity_id": opportunity_id,
                "existing": True,
                "evaluated": True,
                "title": existing["title"],
                "organization": existing["organization"],
                "category": existing["category"],
                "source_url": url,
                "score": existing["score"],
                "recommendation": normalize_recommendation_for_app(
                    existing["recommendation"]
                ),
            }

        evaluation = evaluate_saved_opportunity(
            user_id=user_id,
            opportunity_id=opportunity_id,
        )
        save_final_evaluation(evaluation)

        decision = evaluation["decision"]
        researched = evaluation["opportunity"]

        return {
            "opportunity_id": opportunity_id,
            "existing": True,
            "evaluated": True,
            "title": researched.get("title", existing["title"]),
            "organization": researched.get("organization", existing["organization"]),
            "category": researched.get("category", existing["category"]),
            "source_url": url,
            "score": decision.get("score"),
            "recommendation": normalize_recommendation_for_app(
                decision.get("recommendation")
            ),
        }

    candidate = {
        "title": "Pending research",
        "organization": "",
        "category": category or "OTHER",
        "external_id": "",
        "source_url": url,
        "source_type": "OTHER",
        "location": "",
        "work_arrangement": "UNKNOWN",
        "deadline": "",
        "reward": "",
        "description": "",
        "requirements": [],
        "eligibility": [],
        "submission": "",
        "details": {},
        "evidence": [],
        "activity_status": "UNKNOWN",
    }

    result = process_discovered_opportunity(
        user_id=user_id,
        discovered=candidate,
    )
    result["existing"] = False
    return result


# ============================================================
# EXPLICIT RETRY / RESTART HELPERS FOR UI
# ============================================================

def retry_opportunity_evaluation(
    user_id: int,
    opportunity_id: int,
) -> dict:
    """Retry from the first incomplete/failed stage, preserving completed work."""
    evaluation = evaluate_saved_opportunity(
        user_id=user_id,
        opportunity_id=opportunity_id,
    )
    save_final_evaluation(evaluation)

    decision = evaluation["decision"]
    opportunity = evaluation["opportunity"]

    return {
        "opportunity_id": opportunity_id,
        "title": opportunity.get("title", ""),
        "organization": opportunity.get("organization", ""),
        "category": opportunity.get("category", "OTHER"),
        "source_url": get_source_url(opportunity),
        "score": decision.get("score"),
        "recommendation": normalize_recommendation_for_app(
            decision.get("recommendation")
        ),
        "evaluated": True,
        "resumed": True,
    }


def restart_opportunity_evaluation(
    user_id: int,
    opportunity_id: int,
) -> dict:
    """Explicitly discard cached agent-stage outputs and evaluate from Research."""
    if not get_user_opportunity(user_id, opportunity_id):
        raise ValueError("Opportunity not found for this user.")

    reset_pipeline_state(opportunity_id)
    return retry_opportunity_evaluation(
        user_id=user_id,
        opportunity_id=opportunity_id,
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    user_id = 1
    if len(sys.argv) > 1:
        user_id = int(sys.argv[1])

    print(f"Starting PURSUIT pipeline for user {user_id}...")

    # Keep this deliberately small during provider/free-tier testing.
    results = discover_and_evaluate(
        user_id=user_id,
        requested_types=["JOB"],
        max_opportunities=2,
    )

    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))




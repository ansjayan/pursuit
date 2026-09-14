




# main.py

from __future__ import annotations

import importlib
import inspect
import io
import json
import math
from datetime import date

import streamlit as st

from app.database import (
    init_db,
    authenticate_user,
    create_user,
    get_or_create_external_user,
    create_document,
    get_user_documents,
    delete_document,
    get_user,
    get_user_opportunity,
    get_profile,
    create_or_update_profile,
    delete_user,
    get_dashboard_metrics,
    get_dashboard_opportunities,
    get_interested_opportunities,
    get_watchlist,
    get_history,
    get_latest_evaluation,
    get_pipeline_state,
    mark_opportunity_seen,
    mark_interested,
    remove_interested,
    add_to_watchlist,
    remove_from_watchlist,
    mark_not_interested,
    mark_applied,
    restore_opportunity,
    STATUS_INTERESTED,
    DASHBOARD_FILTER_INTERESTED,
)

from pipeline import (
    discover_and_evaluate,
    evaluate_url,
    resume_incomplete_evaluations,
    retry_opportunity_evaluation,
)


# ============================================================
# APP CONFIG
# ============================================================

st.set_page_config(
    page_title="PURSUIT",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

PAGE_SIZE = 5

CATEGORY_OPTIONS = [
    "JOB",
    "FREELANCE",
    "HACKATHON",
    "GRANT",
    "PROGRAM",
    "OTHER",
]

SORT_OPTIONS = [
    "Newest",
    "Oldest",
    "Highest score",
    "Lowest score",
]

DASHBOARD_FILTERS = [
    "All",
    "New",
    "Pursue",
    "Review",
    "Rejected",
    DASHBOARD_FILTER_INTERESTED,
    "Watch",
    "Applied",
]

HISTORY_FILTERS = [
    "All",
    "Interested",
    "Uninterested",
    "Watch",
    "Unwatch",
    "Not Interested",
    "Applied",
    "Archived",
    "Restored",
]


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; padding-bottom: 3rem;}
    [data-testid="stSidebar"] {min-width: 250px;}
    .pursuit-title {font-size: 1.9rem; font-weight: 750; margin-bottom: 0;}
    .pursuit-tagline {font-size: .88rem; opacity: .68; margin-top: -.2rem;}
    .pursuit-auth {max-width: 560px; margin: 3.5rem auto 1.5rem auto; text-align:center;}
    .pursuit-logo {width:72px;height:72px;border-radius:22px;border:2px solid currentColor;display:inline-flex;align-items:center;justify-content:center;font-size:34px;font-weight:800;margin-bottom:.8rem;}
    .pursuit-auth-title {font-size:2.55rem;font-weight:800;letter-spacing:.04em;margin:0;}
    .pursuit-auth-tagline {font-size:1.02rem;opacity:.72;margin-top:.25rem;margin-bottom:1.3rem;}
    .document-row {border:1px solid rgba(128,128,128,.22);border-radius:12px;padding:.7rem .9rem;margin-bottom:.55rem;}
    .muted {opacity: .72;}
    .opp-meta {font-size: .9rem; opacity: .76;}
    .opp-card {border: 1px solid rgba(128,128,128,.25); border-radius: 14px; padding: 1rem 1rem .6rem 1rem; margin-bottom: .9rem;}
    .analysis-shell {border:1px solid rgba(128,128,128,.30);border-radius:20px;padding:1.25rem 1.35rem;margin:.35rem 0 1.2rem 0;background:rgba(128,128,128,.045);}
    .analysis-kicker {font-size:.78rem;font-weight:750;letter-spacing:.14em;opacity:.65;text-transform:uppercase;margin-bottom:.25rem;}
    .analysis-title {font-size:2rem;font-weight:780;line-height:1.18;margin:.15rem 0 .25rem 0;}
    .analysis-org {font-size:1.03rem;font-weight:650;opacity:.88;}
    .analysis-meta {font-size:.9rem;opacity:.68;margin-top:.25rem;}
    .analysis-section {margin-top:1.15rem;padding-top:.25rem;}
    .analysis-note {border-left:4px solid currentColor;padding:.65rem .9rem;margin:.55rem 0;opacity:.92;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION
# ============================================================

def initialize_session():
    defaults = {
        "user_id": None,
        "page": "Dashboard",
        "dashboard_page": 1,
        "interested_page": 1,
        "watchlist_page": 1,
        "history_page": 1,
        "dashboard_filter_signature": None,
        "interested_filter_signature": None,
        "history_filter_signature": None,
        "analysis_opportunity_id": None,
        "analysis_return_page": "Dashboard",
        "evaluate_result": None,
        "discover_result_ids": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session()


# ============================================================
# HELPERS
# ============================================================

def row_value(row, key, default=None):
    try:
        value = row[key]
    except Exception:
        if isinstance(row, dict):
            value = row.get(key, default)
        else:
            return default
    return default if value is None else value


def json_value(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def opportunity_url(row):
    return (
        row_value(row, "primary_url", "")
        or row_value(row, "source_url", "")
        or row_value(row, "original_url", "")
        or ""
    )


def set_page(name: str):
    st.session_state.page = name
    st.rerun()


def refresh_page():
    st.rerun()


def reset_page_if_filters_changed(page_key: str, signature_key: str, signature):
    if st.session_state.get(signature_key) != signature:
        st.session_state[signature_key] = signature
        st.session_state[page_key] = 1


def paginate(items, page_key: str):
    items = list(items)
    total = len(items)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(1, int(st.session_state.get(page_key, 1))), total_pages)
    st.session_state[page_key] = page
    start = (page - 1) * PAGE_SIZE
    return items[start:start + PAGE_SIZE], page, total_pages, total


def pagination_controls(page_key: str, page: int, total_pages: int, total: int, where: str):
    left, middle, right = st.columns([1, 2, 1])

    with left:
        if st.button(
            "← Previous",
            key=f"{page_key}_{where}_prev",
            disabled=page <= 1,
            use_container_width=True,
        ):
            st.session_state[page_key] = page - 1
            st.rerun()

    with middle:
        st.markdown(
            f"<div style='text-align:center;padding:.45rem 0;'>Page <b>{page}</b> of <b>{total_pages}</b> · {total} item(s)</div>",
            unsafe_allow_html=True,
        )

    with right:
        if st.button(
            "Next →",
            key=f"{page_key}_{where}_next",
            disabled=page >= total_pages,
            use_container_width=True,
        ):
            st.session_state[page_key] = page + 1
            st.rerun()


def section_header(title: str, refresh_key: str, subtitle: str = ""):
    left, right = st.columns([8, 1.25])
    with left:
        st.subheader(title)
        if subtitle:
            st.caption(subtitle)
    with right:
        st.write("")
        if st.button("↻ Refresh", key=refresh_key, use_container_width=True):
            refresh_page()


def _display_score(value):
    if value in (None, ""):
        return "—"
    try:
        return str(int(round(float(value))))
    except Exception:
        return str(value)


def _render_requirement_analysis(personal_fit):
    requirements = []
    if isinstance(personal_fit, dict):
        requirements = personal_fit.get("requirements", []) or []

    if not requirements:
        st.info("No explicit requirements were available for requirement-by-requirement comparison.")
        return

    st.markdown("#### Requirement fit")
    for index, item in enumerate(requirements, start=1):
        if not isinstance(item, dict):
            continue
        requirement = row_value(item, "requirement", "Requirement")
        status = row_value(item, "status", "Unknown") or "Unknown"
        evidence = row_value(item, "evidence", "")
        icon = {
            "Match": "✅",
            "Partial": "🟡",
            "No Match": "❌",
            "Unknown": "❔",
        }.get(status, "❔")
        st.markdown(f"**{icon} {index}. {requirement}**")
        st.caption(f"Status: {status}")
        if evidence:
            st.write(evidence)
        else:
            st.caption("No supporting profile evidence was available.")
        st.divider()


def _render_risks(risk_output):
    risks = []
    if isinstance(risk_output, dict):
        risks = risk_output.get("risks", []) or []

    if not risks:
        st.success("No explicit pursuit risks were identified from the available evidence.")
        return

    for item in risks:
        if not isinstance(item, dict):
            continue
        severity = row_value(item, "severity", "UNKNOWN")
        description = row_value(item, "description", "")
        if severity in {"CRITICAL", "HIGH"}:
            st.error(f"**{severity}** — {description}")
        elif severity == "MEDIUM":
            st.warning(f"**{severity}** — {description}")
        else:
            st.info(f"**{severity}** — {description}")


def render_analysis_page(user_id: int):
    opportunity_id = st.session_state.get("analysis_opportunity_id")
    return_page = st.session_state.get("analysis_return_page", "Dashboard")

    top_left, top_right = st.columns([7, 1.6])
    with top_left:
        st.markdown("## Analysis Workspace")
    with top_right:
        st.write("")
        if st.button("← Back", key="analysis_back", use_container_width=True):
            st.session_state.page = return_page
            st.session_state.analysis_opportunity_id = None
            st.rerun()

    if not opportunity_id:
        st.warning("No opportunity was selected.")
        return

    opportunity = get_user_opportunity(user_id, int(opportunity_id))
    if not opportunity:
        st.error("This opportunity could not be found for your account.")
        return

    evaluation = get_latest_evaluation(int(opportunity_id))
    pipeline_state = get_pipeline_state(int(opportunity_id))

    title = row_value(opportunity, "title", "Untitled opportunity")
    organization = row_value(opportunity, "organization", "") or "Unknown organization"
    category = row_value(opportunity, "category", "OTHER")
    location = row_value(opportunity, "location", "")
    work_arrangement = row_value(opportunity, "work_arrangement", "UNKNOWN")
    deadline = row_value(opportunity, "deadline", "")
    reward = row_value(opportunity, "reward", "")
    recommendation = row_value(opportunity, "recommendation", "") or "—"
    score = row_value(opportunity, "score", None)
    url = opportunity_url(opportunity)

    meta = " · ".join(
        x for x in [category, location, work_arrangement]
        if x
    )

    st.markdown(
        f"""
        <div class="analysis-shell">
            <div class="analysis-kicker">PURSUIT · AI Opportunity Analysis</div>
            <div class="analysis-title">{title}</div>
            <div class="analysis-org">{organization}</div>
            <div class="analysis-meta">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    h1, h2, h3 = st.columns([1.2, 1.4, 4])
    h1.metric("Overall score", _display_score(score))
    h2.metric("Recommendation", recommendation)
    with h3:
        if deadline:
            st.write(f"**Deadline:** {deadline}")
        if reward:
            st.write(f"**Reward / compensation:** {reward}")
        if url:
            st.link_button("Open original opportunity ↗", url)

    if not evaluation:
        st.divider()
        if pipeline_state:
            current_stage = row_value(pipeline_state, "current_stage", "UNKNOWN")
            pipeline_status = row_value(pipeline_state, "pipeline_status", "PENDING")
            st.info(f"Evaluation is not complete. Current stage: **{current_stage}** · Status: **{pipeline_status}**")
            error = row_value(pipeline_state, "last_error", "")
            if error:
                st.error(error)
            if st.button("Resume evaluation", key="analysis_resume", use_container_width=False):
                with st.spinner("Resuming from the first incomplete stage..."):
                    try:
                        retry_opportunity_evaluation(user_id, int(opportunity_id))
                        st.success("Evaluation resumed.")
                    except Exception as exc:
                        st.error(str(exc))
                st.rerun()
        else:
            st.info("No completed analysis is available yet.")
        return

    personal_fit = json_value(row_value(evaluation, "personal_fit_output", ""), {})
    value_output = json_value(row_value(evaluation, "value_output", ""), {})
    risk_output = json_value(row_value(evaluation, "risk_output", ""), {})
    decision_output = json_value(row_value(evaluation, "decision_output", ""), {})
    research_output = json_value(row_value(evaluation, "research_output", ""), {})

    st.divider()
    st.subheader("Score breakdown")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Personal fit", _display_score(row_value(evaluation, "personal_fit_score", None)))
    c2.metric("Learning", _display_score(row_value(evaluation, "learning_value", None)))
    c3.metric("Portfolio", _display_score(row_value(evaluation, "portfolio_value", None)))
    c4.metric("Effort", _display_score(row_value(evaluation, "effort_score", None)))
    c5.metric("Risk", _display_score(row_value(evaluation, "risk_score", None)))
    st.caption("Higher Personal Fit, Learning and Portfolio scores are positive. Higher Effort and Risk mean more cost or difficulty.")

    st.divider()
    st.subheader("Why this recommendation")
    reasoning = (
        row_value(evaluation, "reasoning", "")
        or row_value(evaluation, "why_recommendation", "")
        or row_value(decision_output, "reasoning", "")
    )
    if reasoning:
        st.write(reasoning)
    else:
        st.caption("No narrative explanation was generated for this evaluation.")

    why_not = row_value(evaluation, "why_not_analysis", "") or row_value(decision_output, "why_not_analysis", "")
    if why_not:
        st.markdown("#### What prevents a stronger recommendation")
        st.write(why_not)

    change = row_value(evaluation, "what_could_change_decision", "") or row_value(decision_output, "what_could_change_decision", "")
    if change:
        st.markdown("#### What could change the decision")
        st.write(change)

    st.divider()
    st.subheader("Personal fit")
    matching_skills = personal_fit.get("matching_skills", []) if isinstance(personal_fit, dict) else []
    skill_gaps = personal_fit.get("skill_gaps", []) if isinstance(personal_fit, dict) else []
    unknowns = personal_fit.get("unknown_requirements", []) if isinstance(personal_fit, dict) else []

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown("**Matching skills**")
        if matching_skills:
            for item in matching_skills:
                st.write(f"✅ {item}")
        else:
            st.caption("None explicitly confirmed.")
    with p2:
        st.markdown("**Skill gaps**")
        if skill_gaps:
            for item in skill_gaps:
                st.write(f"🟡 {item}")
        else:
            st.caption("No explicit skill gaps identified.")
    with p3:
        st.markdown("**Unknown requirements**")
        if unknowns:
            for item in unknowns:
                st.write(f"❔ {item}")
        else:
            st.caption("None.")

    _render_requirement_analysis(personal_fit)

    st.subheader("Learning & portfolio value")
    v1, v2 = st.columns(2)
    with v1:
        st.markdown("#### Learning value")
        learning_analysis = row_value(value_output, "learning_analysis", "")
        if learning_analysis:
            st.write(learning_analysis)
        else:
            st.caption("No learning-value explanation available.")
    with v2:
        st.markdown("#### Portfolio value")
        portfolio_analysis = row_value(value_output, "portfolio_analysis", "")
        if portfolio_analysis:
            st.write(portfolio_analysis)
        else:
            st.caption("No portfolio-value explanation available.")

    uncertainties = value_output.get("uncertainties", []) if isinstance(value_output, dict) else []
    if uncertainties:
        st.markdown("**Value assessment uncertainties**")
        for item in uncertainties:
            st.write(f"• {item}")

    st.divider()
    st.subheader("Effort & risk")
    e1, e2, e3 = st.columns(3)
    e1.metric("Estimated effort", row_value(risk_output, "estimated_effort", row_value(evaluation, "estimated_effort", "UNKNOWN")))
    e2.metric("Time pressure", row_value(risk_output, "time_pressure", row_value(evaluation, "time_pressure", "UNKNOWN")))
    e3.metric("Risk score", _display_score(row_value(evaluation, "risk_score", None)))

    opportunity_cost = row_value(risk_output, "opportunity_cost", "") or row_value(evaluation, "opportunity_cost", "")
    if opportunity_cost:
        st.markdown("**Opportunity cost**")
        st.write(opportunity_cost)

    _render_risks(risk_output)

    st.divider()
    st.subheader("Next actions")
    actions = json_value(row_value(evaluation, "next_actions", ""), [])
    if not actions and isinstance(decision_output, dict):
        actions = decision_output.get("next_actions", []) or []
    if actions:
        for index, action in enumerate(actions, start=1):
            st.write(f"**{index}.** {action}")
    else:
        st.caption("No evidence-supported next actions were generated.")

    st.divider()
    st.subheader("Opportunity details")
    description = row_value(opportunity, "description", "") or row_value(research_output, "description", "")
    if description:
        st.write(description)

    requirements = json_value(row_value(opportunity, "requirements", ""), [])
    if not requirements and isinstance(research_output, dict):
        requirements = research_output.get("requirements", []) or []
    if requirements:
        st.markdown("**Explicit requirements**")
        for requirement in requirements:
            st.write(f"• {requirement}")

    eligibility = json_value(row_value(opportunity, "eligibility", ""), [])
    if not eligibility and isinstance(research_output, dict):
        eligibility = research_output.get("eligibility", []) or []
    if eligibility:
        st.markdown("**Eligibility**")
        for item in eligibility:
            st.write(f"• {item}")

    submission = row_value(opportunity, "submission", "") or row_value(research_output, "submission", "")
    if submission:
        st.markdown("**Submission / application**")
        st.write(submission)

    evidence = json_value(row_value(opportunity, "evidence", ""), [])
    if not evidence and isinstance(research_output, dict):
        evidence = research_output.get("evidence", []) or []
    if evidence:
        with st.expander("Research evidence", expanded=False):
            for item in evidence:
                if isinstance(item, dict):
                    text = row_value(item, "evidence", "") or row_value(item, "text", "")
                    if text:
                        st.write(f"• {text}")
                else:
                    st.write(f"• {item}")


def render_opportunity_card(row, user_id: int, key_prefix: str, show_restore=False):
    opportunity_id = int(row_value(row, "id", row_value(row, "opportunity_id", 0)))
    title = row_value(row, "title", "Untitled opportunity")
    organization = row_value(row, "organization", "") or "Unknown organization"
    category = row_value(row, "category", "OTHER")
    location = row_value(row, "location", "")
    work_arrangement = row_value(row, "work_arrangement", "UNKNOWN")
    deadline = row_value(row, "deadline", "")
    score = row_value(row, "score", None)
    recommendation = row_value(row, "recommendation", "") or "—"
    status = row_value(row, "status", row_value(row, "new_status", ""))
    url = opportunity_url(row)

    st.markdown('<div class="opp-card">', unsafe_allow_html=True)
    top_left, top_right = st.columns([7, 2])
    with top_left:
        st.markdown(f"### {title}")
        st.markdown(f"**{organization}**")
        meta = " · ".join(x for x in [category, location, work_arrangement] if x)
        if meta:
            st.caption(meta)
    with top_right:
        st.metric("Score", "—" if score is None else score)
        st.caption(f"{recommendation} · {status}")

    if deadline:
        st.caption(f"Deadline: {deadline}")

    description = row_value(row, "description", "")
    if description:
        st.write(description[:650] + ("…" if len(description) > 650 else ""))

    cols = st.columns(6)

    if show_restore:
        if cols[0].button("Restore", key=f"{key_prefix}_restore_{opportunity_id}", use_container_width=True):
            restore_opportunity(user_id, opportunity_id)
            st.rerun()
    else:
        if status == STATUS_INTERESTED:
            if cols[0].button("Remove interested", key=f"{key_prefix}_uninterest_{opportunity_id}", use_container_width=True):
                remove_interested(user_id, opportunity_id)
                st.rerun()
        else:
            if cols[0].button("Interested", key=f"{key_prefix}_interest_{opportunity_id}", use_container_width=True):
                mark_interested(user_id, opportunity_id)
                st.rerun()

        if status == "WATCHING":
            if cols[1].button("Unwatch", key=f"{key_prefix}_unwatch_{opportunity_id}", use_container_width=True):
                remove_from_watchlist(user_id, opportunity_id)
                st.rerun()
        else:
            if cols[1].button("Watch", key=f"{key_prefix}_watch_{opportunity_id}", use_container_width=True):
                add_to_watchlist(user_id, opportunity_id)
                st.rerun()

        if cols[2].button("Applied", key=f"{key_prefix}_applied_{opportunity_id}", use_container_width=True):
            mark_applied(user_id, opportunity_id)
            st.rerun()

        if cols[3].button("Not interested", key=f"{key_prefix}_no_{opportunity_id}", use_container_width=True):
            mark_not_interested(user_id, opportunity_id)
            st.rerun()

    if cols[4].button("View analysis", key=f"{key_prefix}_analysis_{opportunity_id}", use_container_width=True):
        st.session_state.analysis_opportunity_id = opportunity_id
        st.session_state.analysis_return_page = st.session_state.get("page", "Dashboard")
        st.session_state.page = "Analysis"
        st.rerun()

    if url:
        cols[5].link_button("Open original ↗", url, use_container_width=True)
    else:
        cols[5].button("No URL", key=f"{key_prefix}_nourl_{opportunity_id}", disabled=True, use_container_width=True)

    # If rate-limited / incomplete, allow a direct retry from card.
    pipeline_state = get_pipeline_state(opportunity_id)
    if pipeline_state and row_value(pipeline_state, "pipeline_status", "") != "COMPLETED":
        c1, c2 = st.columns([2, 6])
        with c1:
            if st.button("Resume evaluation", key=f"{key_prefix}_resume_{opportunity_id}", use_container_width=True):
                with st.spinner("Resuming from the first incomplete stage..."):
                    try:
                        retry_opportunity_evaluation(user_id, opportunity_id)
                        st.success("Evaluation resumed.")
                    except Exception as exc:
                        st.error(str(exc))
                st.rerun()
        with c2:
            error = row_value(pipeline_state, "last_error", "")
            stage = row_value(pipeline_state, "current_stage", "")
            if error:
                st.caption(f"Incomplete at {stage}: {error}")

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# GOOGLE / OIDC AUTH
# ============================================================

def _google_identity():
    """Return Google/OIDC identity when Streamlit has an active login."""
    try:
        user = st.user
        if not getattr(user, "is_logged_in", False):
            return None
        email = getattr(user, "email", "") or ""
        name = getattr(user, "name", "") or email.split("@")[0]
        subject = getattr(user, "sub", "") or getattr(user, "subject", "") or email
        if not email:
            return None
        return {"email": email, "name": name, "subject": subject}
    except Exception:
        return None


def _sync_google_session():
    identity = _google_identity()
    if not identity:
        return False
    if st.session_state.get("user_id"):
        return True
    user_id = get_or_create_external_user(
        provider="GOOGLE",
        provider_subject=identity["subject"],
        email=identity["email"],
        name=identity["name"],
    )
    st.session_state.user_id = int(user_id)
    st.session_state.page = "Dashboard"
    return True


# ============================================================
# DOCUMENT / RAG ADAPTER
# ============================================================

def _extract_uploaded_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith((".txt", ".md", ".csv", ".json", ".py", ".sql", ".yml", ".yaml")):
        return data.decode("utf-8", errors="replace").strip()

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF upload requires: pip install pypdf") from exc
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()

    if name.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("DOCX upload requires: pip install python-docx") from exc
        document = Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip()).strip()

    raise ValueError("Supported files: PDF, DOCX, TXT, MD, CSV, JSON, PY, SQL, YAML.")


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def _invoke_by_signature(fn, values: dict):
    sig = inspect.signature(fn)
    kwargs = {}
    aliases = {
        "text": "text", "content": "text", "extracted_text": "text",
        "chunks": "chunks", "documents": "chunks", "texts": "chunks",
        "user_id": "user_id", "document_id": "document_id", "doc_id": "document_id",
        "filename": "filename", "file_name": "filename", "file_type": "file_type",
        "metadata": "metadata", "chroma_document_id": "chroma_document_id",
    }
    for name, param in sig.parameters.items():
        source = aliases.get(name)
        if source and source in values:
            kwargs[name] = values[source]
        elif param.default is inspect._empty and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            raise TypeError(f"Unsupported required parameter: {name}")
    return fn(**kwargs)


def _index_document_in_chroma(*, user_id: int, document_id: int, filename: str, file_type: str, text: str):
    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError("No usable text was extracted from this document.")

    module = importlib.import_module("rag.vector_store")
    values = {
        "user_id": user_id,
        "document_id": document_id,
        "filename": filename,
        "file_type": file_type,
        "text": text,
        "chunks": chunks,
        "metadata": {"user_id": user_id, "document_id": document_id, "filename": filename, "file_type": file_type},
        "chroma_document_id": str(document_id),
    }

    for name in ("add_document_chunks", "index_document", "upsert_document", "add_chunks", "store_chunks"):
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                _invoke_by_signature(fn, values)
                return len(chunks)
            except TypeError:
                continue

    raise RuntimeError(
        "rag.vector_store has search_chunks() but no recognized indexing helper. "
        "Expose one of: add_document_chunks, index_document, upsert_document, add_chunks, store_chunks."
    )


def _delete_document_from_chroma(*, user_id: int, document_id: int) -> None:
    module = importlib.import_module("rag.vector_store")
    values = {"user_id": user_id, "document_id": document_id, "chroma_document_id": str(document_id)}
    for name in ("delete_document_chunks", "delete_document_vectors", "delete_document", "remove_document"):
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                _invoke_by_signature(fn, values)
                return
            except TypeError:
                continue
    raise RuntimeError("No document-deletion helper was found in rag.vector_store.")


def _ingest_uploaded_document(user_id: int, uploaded_file):
    text = _extract_uploaded_text(uploaded_file)
    if not text:
        raise ValueError("No text could be extracted from the uploaded document.")

    file_type = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else "text"
    record = create_document(
        user_id=user_id,
        filename=uploaded_file.name,
        file_type=file_type,
        extracted_text=text,
        chroma_document_id=None,
    )
    document_id = int(record["document_id"])

    if not record.get("created", False):
        return {"document_id": document_id, "created": False, "chunks": None}

    try:
        chunk_count = _index_document_in_chroma(
            user_id=user_id,
            document_id=document_id,
            filename=uploaded_file.name,
            file_type=file_type,
            text=text,
        )
    except Exception:
        delete_document(user_id=user_id, document_id=document_id)
        raise

    return {"document_id": document_id, "created": True, "chunks": chunk_count}


# ============================================================
# AUTH
# ============================================================

def render_auth():
    st.markdown(
        """
        <div class="pursuit-auth">
            <div class="pursuit-logo">P</div>
            <div class="pursuit-auth-title">PURSUIT</div>
            <div class="pursuit-auth-tagline">
                AI-powered opportunity discovery, evaluation, and decision intelligence
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    center_left, center, center_right = st.columns([1.1, 2, 1.1])

    with center:
        login_tab, register_tab = st.tabs(["Login", "Create account"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Login",
                    use_container_width=True,
                    type="primary",
                )

            if submitted:
                user = authenticate_user(email, password)

                if user:
                    st.session_state.user_id = int(user["id"])
                    st.session_state.page = "Dashboard"
                    st.rerun()

                st.error("Invalid email or password.")

        with register_tab:
            with st.form("register_form"):
                name = st.text_input("Name")
                email = st.text_input("Email", key="register_email")
                password = st.text_input(
                    "Password",
                    type="password",
                    key="register_password",
                )
                submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                )

            if submitted:
                try:
                    user_id = create_user(name, email, password)
                    create_or_update_profile(user_id=user_id)
                    st.success("Account created. You can log in now.")
                except Exception as exc:
                    st.error(str(exc))


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar(user):
    with st.sidebar:
        st.markdown('<div class="pursuit-title">PURSUIT</div>', unsafe_allow_html=True)
        st.markdown('<div class="pursuit-tagline">AI-powered opportunity intelligence</div>', unsafe_allow_html=True)
        st.divider()

        st.markdown(f"**{row_value(user, 'name', 'User')}**")
        st.caption(row_value(user, "email", ""))

        if st.button("Profile", use_container_width=True, key="nav_profile"):
            set_page("Profile")

        st.divider()

        nav_items = [
            "Dashboard",
            "Discover",
            "Evaluate URL",
            "Interested",
            "Watchlist",
            "History",
        ]

        for item in nav_items:
            button_type = "primary" if st.session_state.page == item else "secondary"
            if st.button(item, use_container_width=True, key=f"nav_{item}", type=button_type):
                set_page(item)

        st.divider()
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()


# ============================================================
# DASHBOARD
# ============================================================

def render_dashboard(user_id: int, user):
    top_left, top_right = st.columns([6, 3])
    with top_left:
        st.title(row_value(user, "name", "Dashboard"))
    with top_right:
        st.markdown(f"<div style='text-align:right;padding-top:.9rem'>{row_value(user, 'email', '')}</div>", unsafe_allow_html=True)

    hour = __import__("datetime").datetime.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    st.subheader(greeting)

    action1, action2, action3 = st.columns([2, 2, 5])
    if action1.button("Find opportunities", use_container_width=True):
        set_page("Discover")
    if action2.button("Evaluate URL", use_container_width=True):
        set_page("Evaluate URL")
    if action3.button("Resume incomplete evaluations", use_container_width=True):
        with st.spinner("Resuming incomplete evaluations..."):
            try:
                results = resume_incomplete_evaluations(user_id=user_id, limit=20)
                st.success(f"Processed {len(results)} incomplete evaluation(s).")
            except Exception as exc:
                st.error(str(exc))

    metrics = get_dashboard_metrics(user_id)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Opportunities", metrics.get("opportunities", 0))
    m2.metric("Pursue", metrics.get("pursue", 0))
    m3.metric("Interested", metrics.get("interested", 0))
    m4.metric("Watching", metrics.get("watching", 0))
    m5.metric("Review", metrics.get("review", 0))

    st.divider()
    section_header("All opportunities", "dashboard_refresh")

    f1, f2, f3, f4 = st.columns([2, 2, 2, 3])
    filter_name = f1.selectbox("Filter", DASHBOARD_FILTERS, key="dashboard_filter")
    category_display = f2.selectbox("Category", ["All"] + CATEGORY_OPTIONS, key="dashboard_category")
    sort_by = f3.selectbox("Sort", SORT_OPTIONS, key="dashboard_sort")
    search_text = f4.text_input("Search", key="dashboard_search")

    d1, d2 = st.columns(2)
    date_from = d1.date_input("From date", value=None, key="dashboard_from")
    date_to = d2.date_input("To date", value=None, key="dashboard_to")

    signature = (filter_name, category_display, sort_by, search_text, str(date_from), str(date_to))
    reset_page_if_filters_changed("dashboard_page", "dashboard_filter_signature", signature)

    rows = get_dashboard_opportunities(
        user_id=user_id,
        filter_name=filter_name,
        category=None if category_display == "All" else category_display,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        search_text=search_text or None,
    )

    page_rows, page, total_pages, total = paginate(rows, "dashboard_page")
    pagination_controls("dashboard_page", page, total_pages, total, "top")

    if not page_rows:
        st.info("No opportunities match these filters.")
    else:
        for row in page_rows:
            render_opportunity_card(row, user_id, "dash")

    pagination_controls("dashboard_page", page, total_pages, total, "bottom")


# ============================================================
# DISCOVER
# ============================================================

def render_discover(user_id: int):
    section_header(
        "Discover",
        "discover_refresh",
        "Search multiple opportunity types and evaluate the strongest candidates.",
    )

    with st.form("discover_form"):
        requested_types = st.multiselect(
            "Opportunity types",
            CATEGORY_OPTIONS,
            default=[
                "JOB",
                "FREELANCE",
                "HACKATHON",
                "GRANT",
                "PROGRAM",
            ],
        )

        max_opportunities = st.slider(
            "Maximum opportunities",
            1,
            20,
            10,
        )

        preferences = st.text_input(
            "Search preferences",
            placeholder="Examples: India, remote worldwide, Bengaluru",
        )

        submitted = st.form_submit_button(
            "Discover & evaluate",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not requested_types:
            st.warning(
                "Select at least one opportunity type."
            )
        else:
            with st.spinner(
                "Discovering and evaluating opportunities..."
            ):
                try:
                    results = discover_and_evaluate(
                        user_id=user_id,
                        # Explicit UI selection must be passed exactly.
                        requested_types=requested_types,
                        max_opportunities=max_opportunities,
                        search_preferences=preferences,
                    )

                    result_ids = []

                    for result in results:
                        opportunity_id = row_value(
                            result,
                            "opportunity_id",
                            row_value(
                                result,
                                "id",
                                None,
                            ),
                        )

                        if opportunity_id is None:
                            continue

                        try:
                            opportunity_id = int(
                                opportunity_id
                            )
                        except (TypeError, ValueError):
                            continue

                        if opportunity_id not in result_ids:
                            result_ids.append(
                                opportunity_id
                            )

                    st.session_state.discover_result_ids = (
                        result_ids
                    )

                    st.success(
                        f"Processed {len(result_ids)} "
                        "opportunity/opportunities."
                    )

                except Exception as exc:
                    st.error(str(exc))

    # --------------------------------------------------------
    # RENDER NEWLY PROCESSED RESULTS AS NORMAL OPPORTUNITY CARDS
    # --------------------------------------------------------

    result_ids = st.session_state.get(
        "discover_result_ids",
        [],
    )

    if not result_ids:
        st.caption(
            "Newly processed opportunities will appear here "
            "after Discovery finishes."
        )
        return

    st.divider()

    header_left, header_right = st.columns(
        [8, 1.5]
    )

    with header_left:
        st.subheader("Discovery results")
        st.caption(
            "These opportunities are already saved in PURSUIT. "
            "Use the same actions available on the Dashboard."
        )

    with header_right:
        st.write("")
        if st.button(
            "Clear results",
            key="clear_discovery_results",
            use_container_width=True,
        ):
            st.session_state.discover_result_ids = []
            st.rerun()

    rendered = 0

    for opportunity_id in result_ids:
        row = get_user_opportunity(
            user_id=user_id,
            opportunity_id=opportunity_id,
        )

        if not row:
            continue

        render_opportunity_card(
            row,
            user_id,
            f"discover_{opportunity_id}",
        )

        rendered += 1

    if rendered == 0:
        st.info(
            "The processed opportunities are no longer available."
        )


# ============================================================
# EVALUATE URL
# ============================================================

def render_evaluate_url(user_id: int):
    section_header(
        "Evaluate URL",
        "evaluate_refresh",
        "Paste a professional opportunity URL you found online and let PURSUIT run the full AI evaluation pipeline.",
    )

    with st.form("evaluate_url_form"):
        url = st.text_input(
            "Opportunity URL",
            placeholder="https://...",
        )
        category = st.selectbox(
            "Category",
            CATEGORY_OPTIONS,
        )
        restart = st.checkbox(
            "Restart evaluation if this URL already exists"
        )
        submitted = st.form_submit_button(
            "Evaluate",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        with st.spinner("Researching and evaluating URL..."):
            try:
                result = evaluate_url(
                    user_id=user_id,
                    url=url,
                    category=category,
                    force_restart=restart,
                )
                st.session_state.evaluate_result = result
                st.success("Evaluation completed.")
            except Exception as exc:
                st.session_state.evaluate_result = None
                st.error(str(exc))

    result = st.session_state.get("evaluate_result")

    if not result:
        return

    opportunity_id = row_value(
        result,
        "opportunity_id",
        row_value(result, "id", None),
    )

    title = row_value(
        result,
        "title",
        "Evaluated opportunity",
    ) or "Evaluated opportunity"

    organization = row_value(
        result,
        "organization",
        "",
    ) or "Unknown organization"

    category = row_value(
        result,
        "category",
        "OTHER",
    )

    score = row_value(
        result,
        "score",
        None,
    )

    recommendation = row_value(
        result,
        "recommendation",
        "",
    ) or "—"

    source_url = (
        row_value(result, "source_url", "")
        or row_value(result, "url", "")
    )

    st.markdown("### Evaluation result")

    st.markdown(
        f"""
        <div class="analysis-shell">
            <div class="analysis-kicker">AI evaluation complete</div>
            <div class="analysis-title">{title}</div>
            <div class="analysis-org">{organization}</div>
            <div class="analysis-meta">{category}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1, r2, r3 = st.columns([1.2, 1.4, 3.4])

    r1.metric(
        "Overall score",
        _display_score(score),
    )

    r2.metric(
        "Recommendation",
        recommendation,
    )

    with r3:
        if source_url:
            st.link_button(
                "Open original opportunity ↗",
                source_url,
                use_container_width=True,
            )

    a1, a2 = st.columns([1.4, 4])

    with a1:
        if opportunity_id:
            if st.button(
                "View full analysis",
                key=f"evaluate_view_analysis_{opportunity_id}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.analysis_opportunity_id = int(
                    opportunity_id
                )
                st.session_state.analysis_return_page = "Evaluate URL"
                st.session_state.page = "Analysis"
                st.rerun()

    with a2:
        st.caption(
            "The full analysis contains Personal Fit, Learning & Portfolio Value, "
            "Effort & Risk, requirement-by-requirement evidence, and next actions."
        )


# ============================================================
# INTERESTED
# ============================================================

def render_interested(user_id: int):
    section_header("Interested", "interested_refresh", "Opportunities you explicitly want to consider or apply to.")

    f1, f2 = st.columns([2, 3])
    sort_by = f1.selectbox("Sort", SORT_OPTIONS, key="interested_sort")
    search_text = f2.text_input("Search", key="interested_search")
    d1, d2 = st.columns(2)
    date_from = d1.date_input("From date", value=None, key="interested_from")
    date_to = d2.date_input("To date", value=None, key="interested_to")

    signature = (sort_by, search_text, str(date_from), str(date_to))
    reset_page_if_filters_changed("interested_page", "interested_filter_signature", signature)

    rows = get_interested_opportunities(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        search_text=search_text or None,
    )

    page_rows, page, total_pages, total = paginate(rows, "interested_page")
    pagination_controls("interested_page", page, total_pages, total, "top")

    if not page_rows:
        st.info("No interested opportunities yet.")
    else:
        for row in page_rows:
            render_opportunity_card(row, user_id, "interest")

    pagination_controls("interested_page", page, total_pages, total, "bottom")


# ============================================================
# WATCHLIST
# ============================================================

def render_watchlist(user_id: int):
    section_header("Watchlist", "watchlist_refresh", "Opportunities you are monitoring while deciding or preparing to apply.")

    rows = list(get_watchlist(user_id))
    page_rows, page, total_pages, total = paginate(rows, "watchlist_page")
    pagination_controls("watchlist_page", page, total_pages, total, "top")

    if not page_rows:
        st.info("Your watchlist is empty.")
    else:
        for row in page_rows:
            render_opportunity_card(row, user_id, "watchlist")

    pagination_controls("watchlist_page", page, total_pages, total, "bottom")


# ============================================================
# HISTORY
# ============================================================

def render_history(user_id: int):
    section_header("History", "history_refresh", "All workflow actions remain visible here, including Not Interested items.")

    f1, f2, f3 = st.columns([2, 2, 3])
    action_filter = f1.selectbox("Action", HISTORY_FILTERS, key="history_action")
    sort_by = f2.selectbox("Sort", ["Newest", "Oldest"], key="history_sort")
    search_text = f3.text_input("Search", key="history_search")

    d1, d2 = st.columns(2)
    date_from = d1.date_input("From date", value=None, key="history_from")
    date_to = d2.date_input("To date", value=None, key="history_to")

    signature = (action_filter, sort_by, search_text, str(date_from), str(date_to))
    reset_page_if_filters_changed("history_page", "history_filter_signature", signature)

    rows = get_history(
        user_id=user_id,
        action_filter=action_filter,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        search_text=search_text or None,
    )

    page_rows, page, total_pages, total = paginate(rows, "history_page")
    pagination_controls("history_page", page, total_pages, total, "top")

    if not page_rows:
        st.info("No history records match these filters.")
    else:
        for row in page_rows:
            title = row_value(row, "title", "Untitled")
            org = row_value(row, "organization", "")
            action = row_value(row, "action", "")
            action_date = row_value(row, "action_date", "")
            old_status = row_value(row, "old_status", "")
            new_status = row_value(row, "new_status", "")
            st.markdown('<div class="opp-card">', unsafe_allow_html=True)
            st.markdown(f"### {title}")
            st.write(f"**{org}**")
            st.caption(f"{action} · {old_status} → {new_status} · {action_date}")
            note = row_value(row, "note", "")
            if note:
                st.write(note)
            render_opportunity_card(row, user_id, f"history_{row_value(row, 'history_id', 0)}", show_restore=new_status in {"NOT_INTERESTED", "ARCHIVED"})
            st.markdown('</div>', unsafe_allow_html=True)

    pagination_controls("history_page", page, total_pages, total, "bottom")


# ============================================================
# PROFILE
# ============================================================

def _delete_chroma_user_best_effort(user_id: int) -> tuple[bool, str]:
    """Try known vector-store cleanup function names without creating a hard import dependency."""
    try:
        module = importlib.import_module("rag.vector_store")
    except Exception as exc:
        return False, f"Could not load vector store: {exc}"

    for name in ("delete_user_data", "delete_user_collection", "delete_user_chunks", "delete_user_vectors"):
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                fn(user_id=user_id)
            except TypeError:
                fn(user_id)
            return True, ""

    return False, "No user-deletion helper was found in rag.vector_store."


def render_profile(user_id: int, user):
    st.title("Profile")
    profile = get_profile(user_id)

    current_types = []
    raw_types = row_value(profile, "opportunity_types", "") if profile else ""
    if raw_types:
        current_types = [x.strip() for x in raw_types.split(",") if x.strip()]

    with st.form("profile_form"):
        career_goal = st.text_input("Career goal", value=row_value(profile, "career_goal", "") if profile else "")
        skills = st.text_area("Skills", value=row_value(profile, "skills", "") if profile else "")
        currently_learning = st.text_area("Currently learning", value=row_value(profile, "currently_learning", "") if profile else "")
        opportunity_types = st.multiselect("Opportunity types", CATEGORY_OPTIONS, default=[x for x in current_types if x in CATEGORY_OPTIONS])
        work_preferences = st.text_area("Work/search preferences", value=row_value(profile, "work_preferences", "") if profile else "")

        c1, c2 = st.columns(2)
        learning_value = c1.slider("Learning priority", 0, 100, int(row_value(profile, "learning_value", 50) if profile else 50))
        portfolio_value = c2.slider("Portfolio priority", 0, 100, int(row_value(profile, "portfolio_value", 50) if profile else 50))

        saved = st.form_submit_button("Save profile", use_container_width=True)

    if saved:
        create_or_update_profile(
            user_id=user_id,
            career_goal=career_goal,
            skills=skills,
            currently_learning=currently_learning,
            opportunity_types=opportunity_types,
            work_preferences=work_preferences,
            learning_value=learning_value,
            portfolio_value=portfolio_value,
        )
        st.success("Profile saved.")
        st.rerun()

    st.divider()
    st.subheader("Documents & profile intelligence")
    st.caption(
        "Upload resumes, certifications, project notes, portfolios, or other career evidence. "
        "PURSUIT stores document metadata in SQLite and indexes extracted text in ChromaDB for Personal Fit."
    )

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt", "md", "csv", "json", "py", "sql", "yml", "yaml"],
        accept_multiple_files=True,
        key="profile_documents",
    )

    if uploaded_files and st.button("Add documents to profile intelligence", use_container_width=True):
        successes = 0
        duplicates = 0
        for uploaded in uploaded_files:
            try:
                with st.spinner(f"Indexing {uploaded.name}..."):
                    result = _ingest_uploaded_document(user_id, uploaded)
                if result.get("created"):
                    successes += 1
                else:
                    duplicates += 1
            except Exception as exc:
                st.error(f"{uploaded.name}: {exc}")
        if successes:
            st.success(f"Indexed {successes} new document(s) in ChromaDB.")
        if duplicates:
            st.info(f"Skipped {duplicates} duplicate document(s).")
        if successes or duplicates:
            st.rerun()

    documents = get_user_documents(user_id)
    if documents:
        st.markdown("#### Existing documents")
        for doc in documents:
            c1, c2, c3 = st.columns([6, 2, 1])
            with c1:
                st.markdown(f"**{row_value(doc, 'filename', 'Document')}**")
                st.caption(
                    f"{row_value(doc, 'file_type', '')} · added {row_value(doc, 'created_at', '')}"
                )
            with c2:
                text = row_value(doc, "extracted_text", "") or ""
                st.caption(f"{len(text):,} characters")
            with c3:
                doc_id = int(row_value(doc, "id", 0))
                if st.button("Delete", key=f"delete_doc_{doc_id}", use_container_width=True):
                    try:
                        _delete_document_from_chroma(user_id=user_id, document_id=doc_id)
                        delete_document(user_id=user_id, document_id=doc_id)
                        st.success("Document removed.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not remove document safely: {exc}")
    else:
        st.info("No documents uploaded yet.")

    st.divider()
    st.subheader("Delete account")
    st.warning("This permanently deletes your SQLite profile, opportunities, evaluations, watchlist, and history. ChromaDB user vectors are removed first when the vector-store cleanup helper is available.")
    confirm = st.checkbox("I understand this cannot be undone.", key="delete_confirm")
    if st.button("Delete my account", type="primary", disabled=not confirm):
        cleaned, message = _delete_chroma_user_best_effort(user_id)
        if not cleaned:
            st.error(f"Account was not deleted because ChromaDB cleanup could not be confirmed. {message}")
        else:
            delete_user(user_id)
            st.session_state.clear()
            st.success("Account deleted.")
            st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():
    if not st.session_state.user_id:
        render_auth()
        return

    user = get_user(st.session_state.user_id)
    if not user:
        st.session_state.clear()
        st.rerun()

    user_id = int(user["id"])
    render_sidebar(user)

    page = st.session_state.page

    if page == "Dashboard":
        render_dashboard(user_id, user)
    elif page == "Discover":
        render_discover(user_id)
    elif page == "Evaluate URL":
        render_evaluate_url(user_id)
    elif page == "Interested":
        render_interested(user_id)
    elif page == "Watchlist":
        render_watchlist(user_id)
    elif page == "History":
        render_history(user_id)
    elif page == "Profile":
        render_profile(user_id, user)
    elif page == "Analysis":
        render_analysis_page(user_id)
    else:
        st.session_state.page = "Dashboard"
        st.rerun()


if __name__ == "__main__":
    main()






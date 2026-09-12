import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from pipeline import analyze_candidates


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="EviRank — Explainable Resume Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at 15% 10%, rgba(113, 63, 255, 0.14), transparent 30%),
                radial-gradient(circle at 85% 20%, rgba(0, 220, 255, 0.08), transparent 25%),
                #070A12;
            color: #F5F7FB;
        }

        [data-testid="stSidebar"] {
            background: #0B0F1A;
            border-right: 1px solid rgba(255,255,255,0.06);
        }

        h1, h2, h3, h4 {
            font-family: Inter, Arial, sans-serif;
            letter-spacing: -0.02em;
        }

        .nexora-title {
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 0;
            background: linear-gradient(90deg, #FFFFFF, #A88CFF, #66E3FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .subtitle {
            color: #8F9BB3;
            font-size: 1rem;
            margin-top: -8px;
            margin-bottom: 22px;
        }

        .hero {
            padding: 28px 32px;
            border-radius: 22px;
            background: linear-gradient(
                135deg,
                rgba(121, 80, 255, 0.12),
                rgba(255,255,255,0.03)
            );
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 18px 60px rgba(0,0,0,0.28);
            margin-bottom: 20px;
        }

        .metric-card {
            padding: 18px 20px;
            border-radius: 18px;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.07);
            min-height: 118px;
        }

        .metric-label {
            color: #8A95AA;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .metric-value {
            color: white;
            font-size: 2rem;
            font-weight: 800;
            margin-top: 6px;
        }

        .candidate-card {
            padding: 22px;
            border-radius: 20px;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.075);
            min-height: 210px;
        }

        .rank-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 100px;
            background: rgba(126, 90, 255, 0.18);
            color: #B9A6FF;
            font-weight: 700;
            font-size: 0.78rem;
        }

        .score-big {
            font-size: 2.6rem;
            font-weight: 850;
            color: #FFFFFF;
            line-height: 1;
        }

        .score-label {
            color: #7F8BA1;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .badge-exact {
            color: #7FFFC4;
            background: rgba(38, 203, 124, 0.13);
            border: 1px solid rgba(38,203,124,0.22);
            padding: 4px 8px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.72rem;
        }

        .badge-normalized {
            color: #8FD8FF;
            background: rgba(49, 161, 255, 0.13);
            border: 1px solid rgba(49,161,255,0.22);
            padding: 4px 8px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.72rem;
        }

        .badge-semantic {
            color: #C3A8FF;
            background: rgba(143, 88, 255, 0.13);
            border: 1px solid rgba(143,88,255,0.25);
            padding: 4px 8px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.72rem;
        }

        .badge-missing {
            color: #FF9B9B;
            background: rgba(255, 81, 81, 0.10);
            border: 1px solid rgba(255,81,81,0.20);
            padding: 4px 8px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.72rem;
        }

        .evidence-box {
            padding: 14px 16px;
            border-radius: 12px;
            background: rgba(255,255,255,0.025);
            border-left: 3px solid #805DFF;
            color: #C8D0DE;
            margin-top: 8px;
            margin-bottom: 10px;
        }

        .section-header {
            font-size: 1.35rem;
            font-weight: 800;
            margin-top: 16px;
            margin-bottom: 12px;
        }

        .muted {
            color: #8995AA;
        }

        div.stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.08);
            background: linear-gradient(90deg, #7251FF, #8C67FF);
            color: white;
            font-weight: 700;
        }

        div.stButton > button:hover {
            border-color: #A58CFF;
            color: white;
        }

        [data-testid="stFileUploader"] {
            background: rgba(255,255,255,0.025);
            border-radius: 16px;
        }

        .footer {
            text-align: center;
            color: #5F6B80;
            padding-top: 40px;
            padding-bottom: 16px;
            font-size: 0.8rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HELPERS
# =========================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def candidate_name(candidate):
    return (
        candidate.get("candidate_name")
        or candidate.get("name")
        or candidate.get("candidate_id")
        or "Unknown Candidate"
    )


def get_ranked_candidates(bundle):
    if not isinstance(bundle, dict):
        return []

    for key in [
        "ranked_candidates",
        "candidates",
        "rankings",
        "results",
    ]:
        value = bundle.get(key)
        if isinstance(value, list):
            return value

    return []


def get_score_breakdown(candidate):
    breakdown = candidate.get("score_breakdown", {})
    return breakdown if isinstance(breakdown, dict) else {}


def get_requirements(candidate):
    requirements = candidate.get("requirements", [])
    return requirements if isinstance(requirements, list) else []


def badge_html(match_type):
    match_type = str(match_type or "NOT_EVIDENCED").upper()

    if match_type == "EXACT":
        cls = "badge-exact"
    elif match_type == "NORMALIZED":
        cls = "badge-normalized"
    elif match_type == "SEMANTIC":
        cls = "badge-semantic"
    else:
        cls = "badge-missing"

    readable = match_type.replace("_", " ")

    return f'<span class="{cls}">{readable}</span>'


def get_top3_explanation(bundle, candidate, index):
    # Candidate-level explanation first
    for key in [
        "explanation",
        "top3_explanation",
        "summary",
    ]:
        if candidate.get(key):
            return str(candidate[key])

    # Bundle-level variants
    for key in [
        "top_three_explanations",
        "top3_explanations",
        "explanations",
    ]:
        data = bundle.get(key)

        if isinstance(data, list) and index < len(data):
            item = data[index]

            if isinstance(item, str):
                return item

            if isinstance(item, dict):
                return (
                    item.get("explanation")
                    or item.get("text")
                    or item.get("summary")
                    or str(item)
                )

        if isinstance(data, dict):
            cid = candidate.get("candidate_id")
            name = candidate_name(candidate)

            if cid in data:
                return str(data[cid])

            if name in data:
                return str(data[name])

    return None


def find_jd_quality(bundle):
    if not isinstance(bundle, dict):
        return []

    for key in [
        "jd_quality",
        "jd_quality_report",
        "bias_flags",
        "jd_flags",
    ]:
        value = bundle.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            for subkey in ["flags", "issues", "findings"]:
                subvalue = value.get(subkey)
                if isinstance(subvalue, list):
                    return subvalue

    return []


def save_uploaded_file(uploaded_file, directory):
    path = os.path.join(directory, uploaded_file.name)

    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return path


def create_evidence_matrix(candidates):
    requirement_names = []

    for candidate in candidates:
        for req in get_requirements(candidate):
            text = req.get("text") or req.get("requirement") or req.get("id")
            if text and text not in requirement_names:
                requirement_names.append(text)

    rows = []

    for requirement_name in requirement_names:
        row = {"Requirement": requirement_name}

        for candidate in candidates:
            found = None

            for req in get_requirements(candidate):
                text = req.get("text") or req.get("requirement") or req.get("id")

                if text == requirement_name:
                    found = req
                    break

            if found:
                match_type = str(
                    found.get("match_type", "NOT_EVIDENCED")
                ).replace("_", " ")

                sem = safe_float(found.get("semantic_score"))
                key = safe_float(found.get("keyword_score"))

                row[candidate_name(candidate)] = (
                    f"{match_type} | K:{key:.0f} S:{sem:.0f}"
                )
            else:
                row[candidate_name(candidate)] = "—"

        rows.append(row)

    return pd.DataFrame(rows)


# =========================================================
# SESSION STATE
# =========================================================

if "bundle" not in st.session_state:
    st.session_state.bundle = None


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown(
        '<div class="nexora-title">EviRank</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="subtitle">Explainable Resume Intelligence</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Input Files")

    jd_file = st.file_uploader(
        "Job Description",
        type=["pdf", "docx", "txt", "xml"],
        accept_multiple_files=False,
    )

    resume_files = st.file_uploader(
        "Candidate Resumes",
        type=["pdf", "docx", "txt", "xml"],
        accept_multiple_files=True,
    )

    analyze_clicked = st.button(
        "Analyze Candidates",
        use_container_width=True,
    )

    st.divider()

    if st.session_state.bundle:
        st.success("Analysis loaded")

        if st.button(
            "Clear Results",
            use_container_width=True,
        ):
            st.session_state.bundle = None
            st.rerun()


# =========================================================
# RUN PIPELINE
# =========================================================

if analyze_clicked:
    if jd_file is None:
        st.error("Please upload a Job Description.")
    elif not resume_files:
        st.error("Please upload at least one resume.")
    else:
        try:
            progress = st.progress(0)
            status = st.empty()

            with tempfile.TemporaryDirectory() as temp_dir:
                status.info("Saving uploaded files...")
                progress.progress(10)

                jd_path = save_uploaded_file(jd_file, temp_dir)

                resume_paths = [
                    save_uploaded_file(file, temp_dir)
                    for file in resume_files
                ]

                status.info("Parsing documents...")
                progress.progress(25)

                status.info("Running explicit and semantic matching...")
                progress.progress(45)

                # REAL BACKEND CALL
                bundle = analyze_candidates(
                    jd_path,
                    resume_paths,
                )

                progress.progress(80)
                status.info("Building Evidence Ledger and ranking candidates...")

                st.session_state.bundle = bundle

                progress.progress(100)
                status.success("Analysis complete.")

            st.rerun()

        except Exception as exc:
            st.exception(exc)


# =========================================================
# HOME STATE
# =========================================================

bundle = st.session_state.bundle

if not bundle:
    st.markdown(
        """
        <div class="hero"><div class="nexora-title" style="font-size:3.5rem;">EviRank</div><div style="font-size:1.55rem;font-weight:650;margin-top:6px;color:#F5F7FB;">Hiring decisions. Backed by evidence.</div><div style="color:#8F9BB3;margin-top:12px;font-size:1.05rem;max-width:780px;">EviRank combines explicit skill matching, semantic understanding and traceable resume evidence to produce transparent candidate rankings.</div></div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            """
            <div class="metric-card">
                <div class="metric-label">Explicit Matching</div>
                <div class="metric-value">Keyword</div>
                <div class="muted">Tracks literal and normalized skill evidence.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            """
            <div class="metric-card">
                <div class="metric-label">Contextual Matching</div>
                <div class="metric-value">Semantic</div>
                <div class="muted">Finds relevant experience even when wording differs.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            """
            <div class="metric-card">
                <div class="metric-label">Explainability</div>
                <div class="metric-value">Evidence</div>
                <div class="muted">Every important match links back to resume evidence.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.info(
        "Upload the Job Description and candidate resumes from the sidebar to begin."
    )

    st.stop()


# =========================================================
# DATA
# =========================================================

candidates = get_ranked_candidates(bundle)

if not candidates:
    st.error(
        "The backend returned no ranked candidates. "
        "Inspect the pipeline output before continuing."
    )
    st.json(bundle)
    st.stop()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    '<div class="nexora-title">EviRank</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Explainable Resume Intelligence · Analysis Complete</div>',
    unsafe_allow_html=True,
)


# =========================================================
# NAVIGATION
# =========================================================

tabs = st.tabs(
    [
        "Overview",
        "Rankings",
        "Evidence Ledger",
        "Compare",
        "JD Quality",
        "Methodology",
    ]
)


# =========================================================
# OVERVIEW
# =========================================================

with tabs[0]:

    total_requirements = len(
        {
            (
                req.get("id")
                or req.get("text")
                or req.get("requirement")
            )
            for candidate in candidates
            for req in get_requirements(candidate)
        }
    )

    average_score = (
        sum(
            safe_float(c.get("final_score"))
            for c in candidates
        )
        / len(candidates)
    )

    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Candidates</div>
                <div class="metric-value">{len(candidates)}</div>
                <div class="muted">Ranked against the selected JD</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">JD Requirements</div>
                <div class="metric-value">{total_requirements}</div>
                <div class="muted">Requirement-level evidence tracked</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Average Score</div>
                <div class="metric-value">{average_score:.1f}</div>
                <div class="muted">Across all analyzed candidates</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="section-header">Top Matches</div>',
        unsafe_allow_html=True,
    )

    top3 = candidates[:3]

    cols = st.columns(len(top3))

    for index, candidate in enumerate(top3):
        breakdown = get_score_breakdown(candidate)

        with cols[index]:

            semantic = safe_float(
                breakdown.get("semantic")
                or breakdown.get("semantic_score")
            )

            keyword = safe_float(
                breakdown.get("keyword")
                or breakdown.get("keyword_score")
            )

            st.markdown(
                f'<div class="candidate-card"><span class="rank-pill">#{index + 1}</span><h3 style="margin-bottom:8px;">{candidate_name(candidate)}</h3><div class="score-big">{safe_float(candidate.get("final_score")):.1f}</div><div class="score-label">Match Score</div><br><div style="color:#ADB7C9;">Semantic&nbsp;&nbsp; <b>{semantic:.1f}</b><br>Explicit&nbsp;&nbsp;&nbsp;&nbsp; <b>{keyword:.1f}</b></div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-header">Top-3 Explanations</div>',
        unsafe_allow_html=True,
    )

    for index, candidate in enumerate(top3):
        explanation = get_top3_explanation(
            bundle,
            candidate,
            index,
        )

        with st.expander(
            f"#{index + 1} — {candidate_name(candidate)}"
        ):
            if explanation:
                st.write(explanation)
            else:
                st.caption(
                    "No explanation field was returned by the backend."
                )


# =========================================================
# RANKINGS
# =========================================================

with tabs[1]:

    st.markdown(
        '<div class="section-header">Candidate Rankings</div>',
        unsafe_allow_html=True,
    )

    ranking_rows = []

    for rank, candidate in enumerate(candidates, start=1):
        breakdown = get_score_breakdown(candidate)

        ranking_rows.append(
            {
                "Rank": rank,
                "Candidate": candidate_name(candidate),
                "Final Score": round(
                    safe_float(candidate.get("final_score")),
                    2,
                ),
                "Keyword": round(
                    safe_float(
                        breakdown.get("keyword")
                        or breakdown.get("keyword_score")
                    ),
                    2,
                ),
                "Semantic": round(
                    safe_float(
                        breakdown.get("semantic")
                        or breakdown.get("semantic_score")
                    ),
                    2,
                ),
                "Experience": round(
                    safe_float(
                        breakdown.get("experience")
                        or breakdown.get("experience_score")
                    ),
                    2,
                ),
            }
        )

    ranking_df = pd.DataFrame(ranking_rows)

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
    )

    selected_name = st.selectbox(
        "Inspect candidate",
        [candidate_name(c) for c in candidates],
    )

    selected_candidate = next(
        c
        for c in candidates
        if candidate_name(c) == selected_name
    )

    st.markdown(
        f"## {candidate_name(selected_candidate)}"
    )

    st.metric(
        "Final Match Score",
        f"{safe_float(selected_candidate.get('final_score')):.1f}",
    )

    breakdown = get_score_breakdown(selected_candidate)

    if breakdown:
        cols = st.columns(len(breakdown))

        for col, (key, value) in zip(
            cols,
            breakdown.items(),
        ):
            with col:
                st.metric(
                    key.replace("_", " ").title(),
                    f"{safe_float(value):.1f}",
                )

    st.markdown("### Requirement Evidence")

    for req in get_requirements(selected_candidate):

        req_text = (
            req.get("text")
            or req.get("requirement")
            or req.get("id")
            or "Requirement"
        )

        match_type = req.get(
            "match_type",
            "NOT_EVIDENCED",
        )

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin:8px 0 6px 0;"><strong>{req_text}</strong>{badge_html(match_type)}</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            st.caption(
                f"Keyword score: "
                f"{safe_float(req.get('keyword_score')):.1f}"
            )

        with c2:
            st.caption(
                f"Semantic score: "
                f"{safe_float(req.get('semantic_score')):.1f}"
            )

        evidence = req.get("evidence")

        if evidence:
            st.markdown(
                f'<div class="evidence-box"><b>Resume evidence</b><br>{evidence}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption(
                "No clear evidence was identified in the submitted resume."
            )

        st.divider()


# =========================================================
# EVIDENCE LEDGER
# =========================================================

with tabs[2]:

    st.markdown(
        '<div class="section-header">Evidence Ledger</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Requirement-level view of explicit and semantic evidence "
        "used by the ranking engine."
    )

    evidence_df = create_evidence_matrix(candidates)

    if evidence_df.empty:
        st.warning("No Evidence Ledger data was returned.")
    else:
        st.dataframe(
            evidence_df,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Inspect a match")

    candidate_choice = st.selectbox(
        "Candidate",
        [candidate_name(c) for c in candidates],
        key="evidence_candidate",
    )

    evidence_candidate = next(
        c
        for c in candidates
        if candidate_name(c) == candidate_choice
    )

    requirements = get_requirements(evidence_candidate)

    if requirements:

        labels = [
            (
                req.get("text")
                or req.get("requirement")
                or req.get("id")
            )
            for req in requirements
        ]

        chosen_requirement = st.selectbox(
            "Requirement",
            labels,
        )

        req = requirements[labels.index(chosen_requirement)]

        st.markdown(
            badge_html(
                req.get(
                    "match_type",
                    "NOT_EVIDENCED",
                )
            ),
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:
            st.metric(
                "Keyword Score",
                f"{safe_float(req.get('keyword_score')):.1f}",
            )

        with c2:
            st.metric(
                "Semantic Score",
                f"{safe_float(req.get('semantic_score')):.1f}",
            )

        evidence = req.get("evidence")

        if evidence:
            st.markdown(
                f'<div class="evidence-box">{evidence}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info(
                "No clear evidence was identified in the submitted resume."
            )


# =========================================================
# COMPARE
# =========================================================

with tabs[3]:

    st.markdown(
        '<div class="section-header">Compare Candidates</div>',
        unsafe_allow_html=True,
    )

    names = [candidate_name(c) for c in candidates]

    left_name = st.selectbox(
        "Candidate A",
        names,
        index=0,
        key="candidate_a",
    )

    default_b = 1 if len(names) > 1 else 0

    right_name = st.selectbox(
        "Candidate B",
        names,
        index=default_b,
        key="candidate_b",
    )

    left_candidate = next(
        c for c in candidates
        if candidate_name(c) == left_name
    )

    right_candidate = next(
        c for c in candidates
        if candidate_name(c) == right_name
    )

    left_score = safe_float(
        left_candidate.get("final_score")
    )

    right_score = safe_float(
        right_candidate.get("final_score")
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"### {left_name}")
        st.metric(
            "Final Score",
            f"{left_score:.1f}",
        )

    with c2:
        st.markdown(f"### {right_name}")
        st.metric(
            "Final Score",
            f"{right_score:.1f}",
        )

    difference = left_score - right_score

    if difference > 0:
        st.success(
            f"{left_name} leads by {difference:.1f} points."
        )
    elif difference < 0:
        st.success(
            f"{right_name} leads by {abs(difference):.1f} points."
        )
    else:
        st.info("The candidates have the same final score.")

    left_breakdown = get_score_breakdown(left_candidate)
    right_breakdown = get_score_breakdown(right_candidate)

    component_names = sorted(
        set(left_breakdown.keys())
        | set(right_breakdown.keys())
    )

    comparison_rows = []

    for component in component_names:

        left_value = safe_float(
            left_breakdown.get(component)
        )

        right_value = safe_float(
            right_breakdown.get(component)
        )

        comparison_rows.append(
            {
                "Component":
                    component.replace("_", " ").title(),
                left_name: round(left_value, 2),
                right_name: round(right_value, 2),
                "Difference":
                    round(left_value - right_value, 2),
            }
        )

    if comparison_rows:
        st.dataframe(
            pd.DataFrame(comparison_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Why does one rank above the other?")

    if component_names:

        advantages = []

        for component in component_names:

            delta = (
                safe_float(left_breakdown.get(component))
                - safe_float(right_breakdown.get(component))
            )

            if abs(delta) >= 1:
                leader = (
                    left_name
                    if delta > 0
                    else right_name
                )

                advantages.append(
                    (
                        abs(delta),
                        leader,
                        component.replace("_", " "),
                    )
                )

        advantages.sort(reverse=True)

        for delta, leader, component in advantages[:4]:
            st.write(
                f"• **{leader}** leads by "
                f"**{delta:.1f}** on {component}."
            )
    else:
        st.caption(
            "No score breakdown was returned by the backend."
        )


# =========================================================
# JD QUALITY
# =========================================================

with tabs[4]:

    st.markdown(
        '<div class="section-header">JD Quality Lens</div>',
        unsafe_allow_html=True,
    )

    flags = find_jd_quality(bundle)

    if not flags:
        st.success(
            "No JD-quality flags were returned by the backend."
        )
    else:
        st.warning(
            f"{len(flags)} potential JD wording issue(s) identified."
        )

        for flag in flags:

            if isinstance(flag, str):
                st.write(flag)
                st.divider()
                continue

            phrase = (
                flag.get("phrase")
                or flag.get("text")
                or "Flagged wording"
            )

            category = (
                flag.get("category")
                or flag.get("issue")
                or flag.get("type")
                or "Review"
            )

            reason = (
                flag.get("reason")
                or flag.get("explanation")
                or ""
            )

            rewrite = (
                flag.get("suggested_rewrite")
                or flag.get("rewrite")
                or flag.get("suggestion")
            )

            with st.expander(
                f"{category}: {phrase}"
            ):
                if reason:
                    st.write(reason)

                if rewrite:
                    st.markdown(
                        "**Suggested neutral rewrite**"
                    )
                    st.write(rewrite)


# =========================================================
# METHODOLOGY
# =========================================================

with tabs[5]:

    st.markdown(
        '<div class="section-header">How EviRank Works</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        ### 1. Job Description
        The JD is parsed locally.

        ↓

        ### 2. Atomic Requirements
        The system identifies individual role requirements.

        ↓

        ### 3. Explicit Matching
        Exact and normalized keyword evidence is measured.

        ↓

        ### 4. Semantic Matching
        Local embeddings identify relevant experience even where
        wording differs.

        ↓

        ### 5. Evidence Retrieval
        The strongest resume passage supporting each requirement
        is stored.

        ↓

        ### 6. Evidence Ledger
        Every candidate × requirement match records:

        - keyword score
        - semantic score
        - match type
        - supporting evidence

        ↓

        ### 7. Ranking
        Component scores are combined deterministically.

        ↓

        ### 8. Explainability
        Rankings and candidate comparisons are generated from the
        same evidence used by the scoring system.

        ---

        **The ranking is never decided by an external LLM/API.**
        """
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown(
    """
    <div class="footer">
        EviRank · Explainable Resume Intelligence
        <br>
        Transparent ranking through explicit + semantic evidence
    </div>
    """,
    unsafe_allow_html=True,
)



"""
Meeting Intelligence & Project Automation
──────────────────────────────────────────
A 5-stage AI pipeline that converts client meeting transcripts into
structured project scopes, actionable tasks, sprint plans, and syncs
everything to Jira — with human approval gates at every step.

Run:  streamlit run app.py
"""

import streamlit as st
from pathlib import Path
from services import project_store
from stages import (
    stage1_extraction,
    stage2_clarification,
    stage3_sow,
    stage4_sprint,
    stage5_jira,
)

# ── Page config ───────────────────────────────────────────────

st.set_page_config(
    page_title="Meeting Intelligence Pipeline",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────

st.markdown("""
<style>
    /* Stage progress bar */
    .stage-bar {
        display: flex;
        gap: 4px;
        margin-bottom: 1rem;
    }
    .stage-item {
        flex: 1;
        text-align: center;
        padding: 8px 4px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .stage-complete {
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        color: white;
    }
    .stage-active {
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        box-shadow: 0 0 12px rgba(52, 152, 219, 0.4);
    }
    .stage-locked {
        background: #2c3e50;
        color: #7f8c8d;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e8e8e8;
    }

    /* Hide the default Streamlit menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Card-like containers */
    .stExpander {
        border: 1px solid #334155;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ──────────────────────────────

if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = None


# ══════════════════════════════════════════════════════════════
# SIDEBAR — Project Switcher
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("##  Meeting Intelligence")
    st.caption("AI-powered transcript → Jira pipeline")
    st.divider()

    # ── Create new project ────────────────────────────────────
    st.markdown("###  New Project")
    new_name = st.text_input(
        "Project name:",
        placeholder="e.g. MY CHASE Discovery",
        key="new_project_name",
        label_visibility="collapsed",
    )
    if st.button("Create Project", use_container_width=True, type="primary"):
        if new_name.strip():
            p = project_store.create_project(new_name.strip())
            st.session_state.current_project_id = p["id"]
            st.rerun()
        else:
            st.warning("Enter a project name.")

    st.divider()

    # ── Project list ──────────────────────────────────────────
    projects = project_store.list_projects()
    if projects:
        st.markdown("###  Projects")
        for p in projects:
            is_active = p["id"] == st.session_state.current_project_id
            stage_num = p.get("current_stage", 1)
            label = f"{'▶ ' if is_active else ''}{p['name']}  •  Stage {stage_num}"
            if st.button(
                label,
                key=f"proj_{p['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.current_project_id = p["id"]
                st.rerun()
    else:
        st.info("No projects yet. Create one above.")


# ══════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════

# ── No project selected ──────────────────────────────────────

if not st.session_state.current_project_id:
    st.markdown("#  Meeting Intelligence Pipeline")
    st.markdown("""
    Transform client meeting transcripts into structured project scopes,
    actionable tasks, sprint plans, and Jira tickets — with human approval
    at every step.

    ### Pipeline Stages
    | Stage | Description |
    |-------|-------------|
    |  **Stage 1** | Upload transcript → AI extracts structured info |
    |  **Stage 2** | AI asks clarification questions → you answer |
    |  **Stage 3** | AI generates Scope of Work → you refine |
    | ️ **Stage 4** | AI creates sprint plan → you adjust |
    |  **Stage 5** | Push everything to Jira |

    ** Create a project in the sidebar to get started.**
    """)
    st.stop()


# ── Load project ──────────────────────────────────────────────

project = project_store.load_project(st.session_state.current_project_id)
if not project:
    st.error("Project not found. It may have been deleted.")
    st.session_state.current_project_id = None
    st.stop()


# ── Stage progress indicator ─────────────────────────────────

STAGE_LABELS = {
    "1": " Extraction",
    "2": " Clarification",
    "3": " Scope of Work",
    "4": "️ Sprint Plan",
    "5": " Jira Sync",
}

stages_data = project.get("stages", {})

# Build the HTML progress bar
bar_html = '<div class="stage-bar">'
for s_key in ["1", "2", "3", "4", "5"]:
    s_data = stages_data.get(s_key, {})
    status = s_data.get("status", "locked")
    css_class = f"stage-{status}"
    icon = "" if status == "complete" else ("" if status == "active" else "")
    bar_html += f'<div class="stage-item {css_class}">{icon} {STAGE_LABELS[s_key]}</div>'
bar_html += '</div>'

st.markdown(bar_html, unsafe_allow_html=True)
st.markdown(f"### {project['name']}")
st.divider()


# ── Stage tabs ────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    " Stage 1 — Extraction",
    " Stage 2 — Clarification",
    " Stage 3 — Scope of Work",
    "️ Stage 4 — Sprint Plan",
    " Stage 5 — Jira Sync",
])

with tab1:
    stage1_extraction.render(project)

with tab2:
    stage2_clarification.render(project)

with tab3:
    stage3_sow.render(project)

with tab4:
    stage4_sprint.render(project)

with tab5:
    stage5_jira.render(project)

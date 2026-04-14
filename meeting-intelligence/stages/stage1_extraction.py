"""
Stage 1 — Transcript Upload & AI Extraction

The user uploads or pastes a transcript. The AI extracts structured
project information and presents it with confidence indicators.
The user can type corrections in plain language before approving.
"""

import streamlit as st
from services import ai_service, project_store


_CONF_COLORS = {
    "high":   "",
    "medium": "",
    "low":    "",
}


def _badge(confidence: str) -> str:
    return f"{_CONF_COLORS.get(confidence, '')} {confidence}"


# ── Render helpers ────────────────────────────────────────────

def _render_field(label: str, field: dict):
    """Render a single {value, confidence} field."""
    col1, col2 = st.columns([5, 1])
    col1.markdown(f"**{label}:** {field.get('value', 'N/A')}")
    col2.markdown(_badge(field.get("confidence", "low")))


def _render_table(title: str, items: list, columns: list[str]):
    """Render a list of dicts as a styled table with confidence badges."""
    st.markdown(f"### {title}")
    if not items:
        st.info("None extracted.")
        return

    # Build header
    header_cols = st.columns([3] * len(columns) + [1])
    for i, col_name in enumerate(columns):
        header_cols[i].markdown(f"**{col_name}**")
    header_cols[-1].markdown("**Conf.**")

    st.divider()
    for item in items:
        row_cols = st.columns([3] * len(columns) + [1])
        for i, col_name in enumerate(columns):
            key = col_name.lower().replace(" ", "_")
            row_cols[i].markdown(str(item.get(key, "")))
        row_cols[-1].markdown(_badge(item.get("confidence", "low")))



def render(project: dict):
    """Draw the entire Stage 1 UI."""
    stage = project["stages"]["1"]

    st.header(" Stage 1 — Transcript Upload & Extraction")

    if stage.get("approved"):
        st.success(" Stage 1 approved. Extraction is locked.")
        
        with st.expander("View Original Transcript"):
            st.text_area("Transcript Content", stage.get("transcript", "No transcript found."), height=200, disabled=True)
            
        _show_extraction(stage["extraction"])
        return

    st.subheader("Upload Transcript")
    upload_tab, paste_tab = st.tabs([" Upload File", " Paste Text"])

    with upload_tab:
        uploaded = st.file_uploader(
            "Upload a .txt transcript file",
            type=["txt"],
            key=f"upload_{project['id']}",
        )
        if uploaded:
            text = uploaded.read().decode("utf-8", errors="replace")
            stage["transcript"] = text
            project_store.update_stage_data(project, 1, transcript=text)
            st.success(f"Loaded {len(text):,} characters from **{uploaded.name}**")

    with paste_tab:
        pasted = st.text_area(
            "Paste transcript here",
            value=stage.get("transcript", ""),
            height=200,
            key=f"paste_{project['id']}",
        )
        if pasted and pasted != stage.get("transcript", ""):
            stage["transcript"] = pasted
            project_store.update_stage_data(project, 1, transcript=pasted)

    transcript = stage.get("transcript", "")
    if not transcript:
        st.info(" Upload or paste a meeting transcript to begin.")
        return

    st.divider()

    
    if stage.get("extraction") is None:
        if st.button(" Extract Information", type="primary", use_container_width=True):
            with st.spinner("AI is analyzing the transcript… This may take 15-30 seconds."):
                try:
                    extraction = ai_service.extract_from_transcript(transcript)
                    stage["extraction"] = extraction
                    project_store.update_stage_data(project, 1, extraction=extraction)
                    st.rerun()
                except Exception as e:
                    st.error(f"Extraction failed: {e}")
        return

    _show_extraction(stage["extraction"])

    st.divider()

    st.subheader("️ Corrections")
    st.caption("Type corrections in plain language and the AI will update the extraction.")

    if stage.get("corrections"):
        with st.expander(f"Previous corrections ({len(stage['corrections'])})"):
            for i, c in enumerate(stage["corrections"], 1):
                st.markdown(f"**{i}.** {c}")

    correction = st.text_area(
        "Enter your correction",
        placeholder='e.g. "The vendor name should be Software Co, not SoftwareCo" or "Add a Payments module with High priority"',
        key=f"correction_{project['id']}",
    )

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        if st.button(" Apply Correction", disabled=not correction, use_container_width=True):
            with st.spinner("Applying correction…"):
                try:
                    updated = ai_service.refine_extraction(
                        stage["extraction"], correction
                    )
                    corrections = stage.get("corrections", []) + [correction]
                    stage["extraction"] = updated
                    stage["corrections"] = corrections
                    project_store.update_stage_data(
                        project, 1,
                        extraction=updated,
                        corrections=corrections,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Correction failed: {e}")

    with col2:
        if st.button(" Re-extract from scratch", use_container_width=True):
            stage["extraction"] = None
            stage["corrections"] = []
            project_store.update_stage_data(
                project, 1, extraction=None, corrections=[]
            )
            st.rerun()

    with col3:
        if st.button(" Approve Extraction", type="primary", use_container_width=True):
            project_store.advance_stage(project, 1)
            st.rerun()




def _show_extraction(extraction: dict):
    """Render the full extraction in a readable, structured format."""
    if not extraction:
        return

    st.subheader(" Extracted Information")

    # Top-level fields
    col1, col2, col3 = st.columns(3)
    with col1:
        _render_field("Project Name", extraction.get("project_name", {}))
    with col2:
        _render_field("Client Name", extraction.get("client_name", {}))
    with col3:
        _render_field("Vendor Name", extraction.get("vendor_name", {}))

    st.markdown("---")

    # Modules
    _render_table(
        " Modules",
        extraction.get("modules", []),
        ["Name", "Description", "Priority", "Deadline"],
    )

    # Requirements
    _render_table(
        " Requirements",
        extraction.get("requirements", []),
        ["Description", "Module", "Type"],
    )

    # Integrations
    _render_table(
        " Integrations",
        extraction.get("integrations", []),
        ["Name", "Description"],
    )

    # Constraints
    st.markdown("### ️ Constraints")
    for c in extraction.get("constraints", []):
        st.markdown(f"- {_badge(c.get('confidence','low'))} {c.get('description','')}")

    # Assumptions
    st.markdown("###  Assumptions")
    for a in extraction.get("assumptions", []):
        st.markdown(f"- {_badge(a.get('confidence','low'))} {a.get('description','')}")

    # Unknowns
    st.markdown("###  Unknowns")
    for u in extraction.get("unknowns", []):
        st.markdown(f"- {_badge(u.get('confidence','low'))} {u.get('description','')}")

    # Legend
    with st.expander("ℹ️ Confidence Legend"):
        st.markdown("""
        -  **High** — Explicitly stated in the transcript
        -  **Medium** — Reasonably inferred from context
        -  **Low** — Guessed or ambiguous
        """)

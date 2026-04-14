"""
Stage 3 — Scope of Work (SoW) Generation

The AI writes a full SoW from Stage 1 extraction + Stage 2 clarifications.
The user gives free-text feedback, the AI revises/shows a changelog.
Approval is only available after at least one feedback round.
Final SoW is downloadable as .md or .txt.
"""

import streamlit as st
from services import ai_service, project_store


def render(project: dict):
    """Draw the Stage 3 UI."""
    stage = project["stages"]["3"]
    s1 = project["stages"]["1"]
    s2 = project["stages"]["2"]

    st.header(" Stage 3 — Scope of Work")

    if stage["approved"]:
        st.success(" Stage 3 approved. SoW is locked.")
        _show_sow(stage)
        _download_button(stage)
        return

    if s2.get("status") != "complete":
        st.warning(" Complete and approve Stage 2 first.")
        return

    extraction = s1.get("extraction", {})
    qa_history = _build_qa_history(s2)

    if not stage.get("sow"):
        if st.button(" Generate Scope of Work", type="primary", use_container_width=True):
            with st.spinner("AI is drafting the Scope of Work… This may take 30-60 seconds."):
                try:
                    sow = ai_service.generate_sow(extraction, qa_history)
                    stage["sow"] = sow
                    stage["feedback_rounds"] = 0
                    stage["changelog"] = []
                    project_store.update_stage_data(
                        project, 3, sow=sow, feedback_rounds=0, changelog=[]
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"SoW generation failed: {e}")
        return

    _show_sow(stage)

    st.divider()

    if stage.get("changelog"):
        with st.expander(f" Changelog ({len(stage['changelog'])} revision(s))"):
            for i, entry in enumerate(stage["changelog"], 1):
                st.markdown(f"**Revision {i}:**")
                if isinstance(entry, list):
                    for change in entry:
                        st.markdown(f"- {change}")
                else:
                    st.markdown(f"- {entry}")
                st.markdown("---")

    st.subheader(" Feedback")
    st.caption(
        "Provide feedback in plain text. The AI will revise the SoW and show what changed."
    )

    feedback = st.text_area(
        "Your feedback:",
        key=f"sow_fb_{project['id']}",
        height=120,
        placeholder='e.g. "Add a section for user roles and permissions" or "The timeline should be 12 weeks, not 8"',
    )

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        if st.button(" Submit Feedback & Revise", disabled=not feedback,
                      type="primary", use_container_width=True):
            with st.spinner("AI is revising the SoW…"):
                try:
                    result = ai_service.revise_sow(stage["sow"], feedback, extraction)
                    new_sow = result.get("sow", stage["sow"])
                    new_changelog = result.get("changelog", [feedback])

                    stage["sow"] = new_sow
                    stage["feedback_rounds"] = stage.get("feedback_rounds", 0) + 1
                    stage.setdefault("changelog", []).append(new_changelog)

                    project_store.update_stage_data(
                        project, 3,
                        sow=new_sow,
                        feedback_rounds=stage["feedback_rounds"],
                        changelog=stage["changelog"],
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Revision failed: {e}")

    with col2:
        if st.button(" Regenerate from scratch", use_container_width=True):
            stage["sow"] = ""
            stage["changelog"] = []
            stage["feedback_rounds"] = 0
            project_store.update_stage_data(
                project, 3, sow="", changelog=[], feedback_rounds=0
            )
            st.rerun()

    with col3:
        can_approve = stage.get("feedback_rounds", 0) >= 1
        if not can_approve:
            st.button(
                " Approve SoW",
                disabled=True,
                use_container_width=True,
                help="Submit at least one round of feedback before approving.",
            )
            st.caption("️ At least one feedback round required.")
        else:
            if st.button(" Approve SoW", type="primary", use_container_width=True):
                project_store.advance_stage(project, 3)
                st.rerun()

    _download_button(stage)



def _show_sow(stage: dict):
    """Render the SoW as styled markdown."""
    sow = stage.get("sow", "")
    if sow:
        with st.container(border=True):
            st.markdown(sow)


def _download_button(stage: dict):
    """Offer .md and .txt downloads."""
    sow = stage.get("sow", "")
    if not sow:
        return
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Download as .md",
            data=sow,
            file_name="scope_of_work.md",
            mime="text/markdown",
        )
    with col2:
        st.download_button(
            "⬇️ Download as .txt",
            data=sow,
            file_name="scope_of_work.txt",
            mime="text/plain",
        )


def _build_qa_history(s2: dict) -> list:
    """Collect all Q&A from Stage 2 into a flat list."""
    history = []
    for q in s2.get("questions", []):
        entry = {"question": q["question"], "answer": q.get("answer", ""), "status": q.get("status", "open")}
        if q.get("follow_ups"):
            entry["follow_ups"] = q["follow_ups"]
        history.append(entry)
    for uq in s2.get("user_questions", []):
        history.append({"question": uq["question"], "answer": uq["answer"], "type": "user_question"})
    return history

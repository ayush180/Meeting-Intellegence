"""
Stage 2 — AI Clarification & Q&A

The AI generates targeted questions from gaps in Stage 1.
The user answers, AI follows up or marks resolved. The user can also
ask their own questions. A "Done" button lets the user move on.
"""

import streamlit as st
from services import ai_service, project_store


def render(project: dict):
    """Draw the Stage 2 UI."""
    stage = project["stages"]["2"]
    s1 = project["stages"]["1"]

    st.header(" Stage 2 — Clarification & Q&A")

    if stage["approved"]:
        st.success(" Stage 2 approved. All clarifications are locked.")
        _show_qa_summary(stage)
        return

    if s1.get("status") != "complete":
        st.warning(" Complete and approve Stage 1 first.")
        return

    extraction = s1.get("extraction", {})

   
    if not stage.get("questions"):
        if st.button(" Generate Clarification Questions", type="primary", use_container_width=True):
            with st.spinner("AI is analyzing gaps and generating questions…"):
                try:
                    questions = ai_service.generate_questions(
                        extraction, s1.get("transcript", "")
                    )
                    stage["questions"] = questions
                    project_store.update_stage_data(project, 2, questions=questions)
                    st.rerun()
                except Exception as e:
                    st.error(f"Question generation failed: {e}")
        return

    questions = stage["questions"]
    answered_count = sum(1 for q in questions if q.get("status") == "resolved")
    skipped_count = sum(1 for q in questions if q.get("status") == "skipped")
    total = len(questions)

    st.progress(
        (answered_count + skipped_count) / max(total, 1),
        text=f"Progress: {answered_count} answered, {skipped_count} skipped, "
             f"{total - answered_count - skipped_count} remaining"
    )

    for i, q in enumerate(questions):
        qid = q.get("id", f"q{i+1}")
        status = q.get("status", "open")
        icon = "" if status == "resolved" else ("️" if status == "skipped" else "")

        with st.expander(f"{icon} {qid}: {q['question']}", expanded=(status == "open")):
            st.caption(f"**Why this is being asked:** {q.get('reason', 'N/A')}")

            if status == "resolved":
                st.success(f"**Answer:** {q.get('answer', '')}")
                # Show follow-ups if any
                for fu in q.get("follow_ups", []):
                    st.markdown(f"↳ **Follow-up:** {fu.get('question', '')}")
                    if fu.get("answer"):
                        st.markdown(f"   **Answer:** {fu['answer']}")
            elif status == "skipped":
                st.info(f"Skipped — Reason: {q.get('skip_reason', 'No reason given')}")
            else:
                # Answer input
                answer = st.text_area(
                    "Your answer:",
                    key=f"ans_{project['id']}_{qid}",
                    placeholder="Type your answer here…",
                )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Submit Answer", key=f"submit_{project['id']}_{qid}",
                                 disabled=not answer, type="primary"):
                        with st.spinner("Evaluating answer…"):
                            try:
                                result = ai_service.process_answer(
                                    extraction, q["question"], answer
                                )
                                q["answer"] = answer
                                if result.get("resolved", True) or not result.get("follow_up"):
                                    q["status"] = "resolved"
                                else:
                                    # Add follow-up
                                    fu = {
                                        "question": result["follow_up"],
                                        "reason": result.get("follow_up_reason", ""),
                                        "answer": "",
                                    }
                                    q.setdefault("follow_ups", []).append(fu)
                                    q["status"] = "resolved"  # Mark parent resolved, follow-up shown inline

                                project_store.update_stage_data(project, 2, questions=questions)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                with col2:
                    skip_reason = st.text_input(
                        "Skip reason (optional):",
                        key=f"skip_{project['id']}_{qid}",
                    )
                    if st.button("️ Skip Question", key=f"skipbtn_{project['id']}_{qid}"):
                        q["status"] = "skipped"
                        q["skip_reason"] = skip_reason or "No reason given"
                        project_store.update_stage_data(project, 2, questions=questions)
                        st.rerun()

    st.divider()

    st.subheader(" Ask Your Own Question")
    st.caption("Ask anything about the project — the AI will answer in context.")

    user_questions = stage.get("user_questions", [])
    if user_questions:
        for uq in user_questions:
            st.markdown(f"**Q:** {uq['question']}")
            st.markdown(f"**A:** {uq['answer']}")
            st.markdown("---")

    user_q = st.text_input(
        "Your question:",
        key=f"userq_{project['id']}",
        placeholder="e.g. Can we fit the reporting module into Sprint 2?",
    )
    if st.button("Ask AI", disabled=not user_q, key=f"askbtn_{project['id']}"):
        with st.spinner("AI is thinking…"):
            try:
                ans = ai_service.answer_user_question(
                    extraction,
                    [{"q": q["question"], "a": q.get("answer", "")} for q in questions],
                    user_q,
                )
                user_questions.append({"question": user_q, "answer": ans})
                project_store.update_stage_data(project, 2, user_questions=user_questions)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    st.divider()

    st.subheader("Ready to proceed?")
    st.caption("You decide when enough has been clarified. Click Done to advance to Stage 3.")
    if st.button(" Done — Proceed to Stage 3", type="primary", use_container_width=True):
        project_store.advance_stage(project, 2)
        st.rerun()


def _show_qa_summary(stage: dict):
    """Show a read-only summary of all Q&A."""
    for q in stage.get("questions", []):
        status = q.get("status", "open")
        icon = "" if status == "resolved" else "️"
        st.markdown(f"{icon} **{q.get('id', '')}:** {q['question']}")
        if q.get("answer"):
            st.markdown(f"   → {q['answer']}")
        elif status == "skipped":
            st.markdown(f"   → *Skipped: {q.get('skip_reason', '')}*")

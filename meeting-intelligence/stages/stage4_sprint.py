"""
Stage 4 — Sprint Planning

From the approved SoW, the AI generates tasks and organises them into
sprints (2-week, max 40 points, Fibonacci story points).
The user can move tasks between sprints before approving.
"""

import streamlit as st
import json
from services import ai_service, project_store


def render(project: dict):
    """Draw the Stage 4 UI."""
    stage = project["stages"]["4"]
    s1 = project["stages"]["1"]
    s3 = project["stages"]["3"]

    st.header("️ Stage 4 — Sprint Planning")

    if stage["approved"]:
        st.success(" Stage 4 approved. Sprint plan is locked.")
        _show_sprint_plan(stage)
        return

    if s3.get("status") != "complete":
        st.warning(" Complete and approve Stage 3 first.")
        return

    extraction = s1.get("extraction", {})
    sow = s3.get("sow", "")

    if not stage.get("tasks"):
        if st.button(" Generate Sprint Plan", type="primary", use_container_width=True):
            with st.spinner("AI is generating tasks and sprint plan… This may take 30-60 seconds."):
                try:
                    result = ai_service.generate_sprint_plan(sow, extraction)
                    tasks = result.get("tasks", [])
                    sprints = result.get("sprints", [])
                    stage["tasks"] = tasks
                    stage["sprints"] = sprints
                    project_store.update_stage_data(
                        project, 4, tasks=tasks, sprints=sprints
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Sprint plan generation failed: {e}")
        return

    _show_sprint_plan(stage)

    st.divider()

    st.subheader(" Move Tasks Between Sprints")
    st.caption("Adjust the plan by moving tasks to different sprints.")

    tasks = stage["tasks"]
    sprints = stage["sprints"]
    task_map = {t["id"]: t for t in tasks}
    sprint_names = [s["name"] for s in sprints]

    # Flatten task-to-sprint mapping
    task_sprint = {}
    for sp in sprints:
        for tid in sp.get("task_ids", []):
            task_sprint[tid] = sp["name"]

    col1, col2, col3 = st.columns(3)
    with col1:
        task_options = [f"{t['id']}: {t['title']}" for t in tasks]
        selected_task = st.selectbox("Select task to move:", task_options, key=f"move_task_{project['id']}")
    with col2:
        current_sprint = task_sprint.get(selected_task.split(":")[0].strip(), "Unassigned") if selected_task else "N/A"
        st.text_input("Current sprint:", value=current_sprint, disabled=True)
    with col3:
        target_sprint = st.selectbox("Move to sprint:", sprint_names, key=f"move_to_{project['id']}")

    if st.button(" Move Task", use_container_width=True):
        if selected_task and target_sprint:
            tid = selected_task.split(":")[0].strip()
            # Remove from current sprint
            for sp in sprints:
                if tid in sp.get("task_ids", []):
                    sp["task_ids"].remove(tid)
                    # Recalculate points
                    sp["total_points"] = sum(
                        task_map[t].get("story_points", 0)
                        for t in sp["task_ids"] if t in task_map
                    )
            # Add to target sprint
            for sp in sprints:
                if sp["name"] == target_sprint:
                    sp.setdefault("task_ids", []).append(tid)
                    sp["total_points"] = sum(
                        task_map[t].get("story_points", 0)
                        for t in sp["task_ids"] if t in task_map
                    )
                    if sp["total_points"] > 40:
                        sp["warning"] = f"️ Sprint exceeds 40 points ({sp['total_points']} pts)"
                    else:
                        sp["warning"] = ""
                    break

            project_store.update_stage_data(project, 4, sprints=sprints)
            st.rerun()

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button(" Regenerate from scratch", use_container_width=True):
            stage["tasks"] = []
            stage["sprints"] = []
            project_store.update_stage_data(project, 4, tasks=[], sprints=[])
            st.rerun()

    with col2:
        # Check for over-capacity warnings
        warnings = [s for s in sprints if s.get("total_points", 0) > 40]
        if warnings:
            st.warning(f"️ {len(warnings)} sprint(s) exceed 40 story points. Consider rebalancing.")
        if st.button(" Approve Sprint Plan", type="primary", use_container_width=True):
            project_store.advance_stage(project, 4)
            st.rerun()


def _show_sprint_plan(stage: dict):
    """Render the full sprint plan with tasks."""
    tasks = stage.get("tasks", [])
    sprints = stage.get("sprints", [])
    task_map = {t["id"]: t for t in tasks}

    st.subheader(" Sprint Overview")

    for sp in sprints:
        total = sp.get("total_points", 0)
        warning = sp.get("warning", "")
        cap_color = "" if total > 40 else ("" if total > 30 else "")

        with st.expander(
            f"**{sp['name']}** — {cap_color} {total}/40 pts — {sp.get('goal', '')}",
            expanded=True
        ):
            if warning:
                st.warning(warning)

            sprint_tasks = [task_map[tid] for tid in sp.get("task_ids", []) if tid in task_map]
            if not sprint_tasks:
                st.info("No tasks assigned to this sprint.")
                continue

            for t in sprint_tasks:
                _render_task_card(t)


def _render_task_card(task: dict):
    """Render a single task as a card."""
    prio_colors = {"High": "", "Medium": "", "Low": ""}
    prio_icon = prio_colors.get(task.get("priority", "Medium"), "")

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            st.markdown(f"**{task['id']}:** {task.get('title', 'Untitled')}")
        with col2:
            st.caption(f" {task.get('module', 'N/A')}")
        with col3:
            st.caption(f"{prio_icon} {task.get('priority', 'Medium')}")
        with col4:
            st.caption(f" {task.get('story_points', '?')} pts")

        st.markdown(f"*{task.get('description', '')}*")

        if task.get("dependencies"):
            st.caption(f"️ Depends on: {', '.join(task['dependencies'])}")

        if task.get("acceptance_criteria"):
            with st.popover(" Acceptance Criteria"):
                for ac in task["acceptance_criteria"]:
                    st.markdown(f"- {ac}")

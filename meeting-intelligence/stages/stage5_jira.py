"""
Stage 5 — Jira Integration

Push the approved sprint plan to Jira Cloud. The user configures
credentials, tests the connection, previews each batch (Epics → Issues →
Sprints), and confirms before anything is created.
"""

import streamlit as st
from services import project_store
from services.jira_service import JiraService


def render(project: dict):
    """Draw the Stage 5 UI."""
    stage = project["stages"]["5"]
    s4 = project["stages"]["4"]

    st.header(" Stage 5 — Jira Sync")

    if s4.get("status") != "complete":
        st.warning(" Complete and approve Stage 4 first.")
        return

    st.subheader(" Jira Configuration")
    st.caption(
        "Enter your Jira Cloud credentials. "
        "[Create a free account](https://www.atlassian.com/software/jira/free) | "
        "[Generate API Token](https://id.atlassian.com/manage-api-tokens)"
    )

    jira_cfg = stage.get("jira_config", {})

    col1, col2 = st.columns(2)
    with col1:
        domain = st.text_input(
            "Jira Domain",
            value=jira_cfg.get("domain", ""),
            placeholder="your-org.atlassian.net",
            key=f"jira_domain_{project['id']}",
        )
        email = st.text_input(
            "Jira Email",
            value=jira_cfg.get("email", ""),
            placeholder="you@example.com",
            key=f"jira_email_{project['id']}",
        )
    with col2:
        api_token = st.text_input(
            "API Token",
            value=jira_cfg.get("api_token", ""),
            type="password",
            key=f"jira_token_{project['id']}",
        )
        project_key = st.text_input(
            "Project Key",
            value=jira_cfg.get("project_key", ""),
            placeholder="PROJ",
            key=f"jira_proj_{project['id']}",
        )

    # Save config changes
    new_cfg = {"domain": domain, "email": email, "api_token": api_token, "project_key": project_key}
    if new_cfg != jira_cfg:
        stage["jira_config"] = new_cfg
        project_store.update_stage_data(project, 5, jira_config=new_cfg)

    all_filled = all([domain, email, api_token, project_key])

    if all_filled:
        if st.button(" Test Connection", use_container_width=True):
            jira = JiraService(domain, email, api_token, project_key)
            with st.spinner("Testing connection…"):
                result = jira.test_connection()
            if result["ok"]:
                st.success(f" Connected to project **{result['project_name']}**")
                stage["connection_tested"] = True
                project_store.update_stage_data(project, 5, connection_tested=True)
            else:
                st.error(f" Connection failed: {result['error']}")
                stage["connection_tested"] = False
    else:
        st.info("Fill in all fields to test the connection.")

    if not stage.get("connection_tested"):
        return

    st.divider()

    tasks = s4.get("tasks", [])
    sprints = s4.get("sprints", [])
    task_map = {t["id"]: t for t in tasks}

    # Collect unique modules for Epics
    modules = _collect_modules(tasks, project["stages"]["1"].get("extraction", {}))

    sync_log = stage.get("sync_log", [])
    created = stage.get("created_items", {})
    if isinstance(created, list):
        created = {}

    st.subheader(" Phase 1 — Create Epics")
    if created.get("epics"):
        st.success(f" {len(created['epics'])} Epics created.")
        for e in created["epics"]:
            st.markdown(f"- **{e['key']}** — {e['name']}")
    else:
        st.markdown("The following Epics will be created (one per module):")
        for m in modules:
            st.markdown(f"-  **{m['name']}** — {m.get('description', '')}")

        if st.button(" Confirm & Create Epics", type="primary", key="create_epics"):
            jira = JiraService(domain, email, api_token, project_key)
            epic_results = []
            progress = st.progress(0, text="Creating Epics…")

            for i, m in enumerate(modules):
                try:
                    result = jira.create_epic(m["name"], m.get("description", ""))
                    epic_results.append(result)
                    progress.progress(
                        (i + 1) / len(modules),
                        text=f"Creating Epics… {i + 1} of {len(modules)}"
                    )
                except Exception as e:
                    st.error(f" Failed to create Epic '{m['name']}': {e}")
                    epic_results.append({"key": "FAILED", "name": m["name"], "error": str(e)})

            created["epics"] = epic_results
            project_store.update_stage_data(project, 5, created_items=created)
            st.rerun()
        return

    st.divider()

    st.subheader(" Phase 2 — Create Issues")

    epic_map = {e["name"]: e["key"] for e in created.get("epics", []) if e.get("key") != "FAILED"}

    if created.get("issues"):
        st.success(f" {len(created['issues'])} Issues created.")
        for iss in created["issues"]:
            st.markdown(f"- **{iss['key']}** — {iss['summary']}")
    else:
        st.markdown("The following Issues will be created:")
        for t in tasks:
            epic_key = epic_map.get(t.get("module", ""), "N/A")
            st.markdown(
                f"-  **{t['title']}** ({t.get('type', 'Story')}, "
                f"{t.get('story_points', '?')} pts) → Epic: {epic_key}"
            )

        if st.button(" Confirm & Create Issues", type="primary", key="create_issues"):
            jira = JiraService(domain, email, api_token, project_key)
            issue_results = []
            progress = st.progress(0, text="Creating Issues…")

            for i, t in enumerate(tasks):
                epic_key = epic_map.get(t.get("module", ""))
                try:
                    result = jira.create_issue(
                        summary=t["title"],
                        description=t.get("description", ""),
                        issue_type=t.get("type", "Story"),
                        priority=t.get("priority", "Medium"),
                        story_points=t.get("story_points"),
                        epic_key=epic_key,
                        acceptance_criteria=t.get("acceptance_criteria", []),
                    )
                    # Store mapping from task ID to Jira key
                    result["task_id"] = t["id"]
                    issue_results.append(result)
                    progress.progress(
                        (i + 1) / len(tasks),
                        text=f"Creating Issues… {i + 1} of {len(tasks)}"
                    )
                except Exception as e:
                    st.error(f" Failed to create '{t['title']}': {e}")
                    issue_results.append({
                        "key": "FAILED", "summary": t["title"],
                        "task_id": t["id"], "error": str(e)
                    })

            created["issues"] = issue_results
            project_store.update_stage_data(project, 5, created_items=created)
            st.rerun()
        return

    st.divider()

    st.subheader(" Phase 3 — Create Sprints")

    task_to_jira = {iss["task_id"]: iss["key"] for iss in created.get("issues", []) if iss.get("key") != "FAILED"}

    if created.get("sprints_done"):
        st.success(" All sprints created and issues assigned.")
        _show_summary(created, domain)
        
        if any("error" in sp for sp in created.get("sprint_results", [])):
            if st.button("Retry Failed Sprints", type="primary"):
                created.pop("sprints_done", None)
                project_store.update_stage_data(project, 5, created_items=created)
                st.rerun()
    else:
        st.markdown("The following Sprints will be created:")
        for sp in sprints:
            sprint_tasks = [task_map[tid] for tid in sp.get("task_ids", []) if tid in task_map]
            task_titles = ", ".join(t["title"][:40] for t in sprint_tasks[:5])
            st.markdown(
                f"-  **{sp['name']}** ({sp.get('total_points', 0)} pts) — {task_titles}…"
            )

        if st.button(" Confirm & Create Sprints", type="primary", key="create_sprints"):
            jira = JiraService(domain, email, api_token, project_key)
            board_id = jira.get_board_id()

            if not board_id:
                st.error(
                    " No Scrum board found for this project. "
                    "Please create a Scrum board in Jira first (Board → Create board → Scrum)."
                )
                return

            sprint_results = []
            progress = st.progress(0, text="Creating Sprints…")

            for i, sp in enumerate(sprints):
                try:
                    # Create sprint
                    sprint_name = sp["name"][:30]
                    sprint = jira.create_sprint(board_id, sprint_name, sp.get("goal", ""))
                    sprint_id = sprint["id"]

                    # Assign issues to sprint
                    issue_keys = [
                        task_to_jira[tid]
                        for tid in sp.get("task_ids", [])
                        if tid in task_to_jira
                    ]
                    if issue_keys:
                        jira.add_issues_to_sprint(sprint_id, issue_keys)

                    sprint_results.append({
                        "sprint_name": sp["name"],
                        "sprint_id": sprint_id,
                        "issues_assigned": issue_keys,
                    })
                    progress.progress(
                        (i + 1) / len(sprints),
                        text=f"Creating Sprints… {i + 1} of {len(sprints)}"
                    )
                except Exception as e:
                    st.error(f" Failed to create sprint '{sp['name']}': {e}")
                    sprint_results.append({
                        "sprint_name": sp["name"],
                        "error": str(e),
                    })

            created["sprint_results"] = sprint_results
            created["sprints_done"] = True
            project_store.update_stage_data(project, 5, created_items=created)
            st.rerun()
        return



def _collect_modules(tasks: list, extraction: dict) -> list:
    """Collect unique module names and descriptions from tasks + extraction."""
    modules_from_extraction = {
        m.get("name", ""): m.get("description", "")
        for m in extraction.get("modules", [])
    }
    module_names = set()
    modules = []
    for t in tasks:
        mname = t.get("module", "General")
        if mname not in module_names:
            module_names.add(mname)
            modules.append({
                "name": mname,
                "description": modules_from_extraction.get(mname, f"Module: {mname}"),
            })
    return modules


def _show_summary(created: dict, domain: str):
    """Show the final summary table with links."""
    st.subheader(" Sync Summary")

    base_url = f"https://{domain}/browse"

    # Epics
    st.markdown("**Epics:**")
    for e in created.get("epics", []):
        if e.get("key") != "FAILED":
            st.markdown(f"- [{e['key']}]({base_url}/{e['key']}) — {e['name']}")
        else:
            st.markdown(f"-  FAILED — {e['name']}: {e.get('error', 'Unknown error')}")

    # Issues
    st.markdown("**Issues:**")
    for iss in created.get("issues", []):
        if iss.get("key") != "FAILED":
            st.markdown(f"- [{iss['key']}]({base_url}/{iss['key']}) — {iss['summary']}")
        else:
            st.markdown(f"-  FAILED — {iss['summary']}: {iss.get('error', 'Unknown error')}")

    # Sprints
    st.markdown("**Sprints:**")
    for sp in created.get("sprint_results", []):
        if "error" not in sp:
            assigned = ", ".join(sp.get("issues_assigned", []))
            st.markdown(f"-  **{sp['sprint_name']}** — Issues: {assigned}")
        else:
            st.markdown(f"-  FAILED — {sp['sprint_name']}: {sp.get('error', '')}")

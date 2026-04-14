

import time
import requests
from requests.auth import HTTPBasicAuth


class JiraService:
    """Thin wrapper around the Jira Cloud REST v3 + Agile v1 APIs."""

    def __init__(self, domain: str, email: str, api_token: str, project_key: str):
        self.base_url = f"https://{domain}"
        self.auth = HTTPBasicAuth(email, api_token)
        self.project_key = project_key
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ── helpers ───#

    def _req(self, method: str, path: str, json_body: dict | None = None,
             agile: bool = False, retries: int = 2) -> dict:
        """
        Fire an HTTP request with simple retry + back-off on 429.
        Returns the parsed JSON body, or raises with a clear message.
        """
        base = f"{self.base_url}/rest/agile/1.0" if agile else f"{self.base_url}/rest/api/3"
        url = f"{base}{path}"
        for attempt in range(retries + 1):
            resp = requests.request(
                method, url,
                json=json_body,
                auth=self.auth,
                headers=self.headers,
                timeout=30,
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                detail = resp.text[:500]
                raise RuntimeError(
                    f"Jira API {resp.status_code} on {method} {path}: {detail}"
                )
            if resp.status_code == 204 or not resp.text:
                return {}
            return resp.json()
        raise RuntimeError("Jira API rate-limited after retries — try again later.")

    # ── connection ──────#

    def test_connection(self) -> dict:
        """
        Verifies credentials by fetching the project.
        Returns {"ok": True, "project_name": …} or {"ok": False, "error": …}.
        """
        try:
            data = self._req("GET", f"/project/{self.project_key}")
            return {"ok": True, "project_name": data.get("name", self.project_key)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── board discovery ──────#

    def get_board_id(self) -> int | None:
        """Find the first Scrum board associated with the project."""
        try:
            data = self._req("GET",
                             f"/board?projectKeyOrId={self.project_key}",
                             agile=True)
            boards = data.get("values", [])
            for b in boards:
                if b.get("type") == "scrum":
                    return b["id"]
            if boards:
                return boards[0]["id"]
        except Exception:
            pass
        return None

    # ── epics ───────#

    def create_epic(self, name: str, description: str = "") -> dict:
        """Create an Epic issue and return {key, id, name}."""
        body = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": name,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description or name}],
                    }],
                },
                "issuetype": {"name": "Epic"},
            }
        }
        resp = self._req("POST", "/issue", body)
        return {"key": resp["key"], "id": resp["id"], "name": name}

    # ── issues (stories / tasks) ────────#

    def create_issue(self, summary: str, description: str,
                     issue_type: str = "Story",
                     priority: str = "Medium",
                     story_points: int | None = None,
                     epic_key: str | None = None,
                     acceptance_criteria: list[str] | None = None) -> dict:
        """
        Create a Story or Task linked to the given epic_key.
        Returns {key, id, summary}.
        """
        # Build description with acceptance criteria
        desc_parts = [description]
        if acceptance_criteria:
            desc_parts.append("\n\nAcceptance Criteria:")
            for ac in acceptance_criteria:
                desc_parts.append(f"• {ac}")
        full_desc = "\n".join(desc_parts)

        body: dict = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": full_desc}],
                    }],
                },
                "issuetype": {"name": issue_type if issue_type in ("Story", "Task", "Bug") else "Story"},
            }
        }

        # Priority
        prio_map = {"High": "High", "Medium": "Medium", "Low": "Low"}
        if priority in prio_map:
            body["fields"]["priority"] = {"name": prio_map[priority]}

        # Link to epic
        if epic_key:
            body["fields"]["parent"] = {"key": epic_key}

        # Story points (custom field — Jira Cloud uses story_points or customfield_10016)
        if story_points is not None:
            body["fields"]["story_points"] = story_points

        try:
            resp = self._req("POST", "/issue", body)
        except RuntimeError:
            # Retry without story_points if the field doesn't exist
            body["fields"].pop("story_points", None)
            resp = self._req("POST", "/issue", body)

        return {"key": resp["key"], "id": resp["id"], "summary": summary}

    # ── sprints ──────#

    def create_sprint(self, board_id: int, name: str, goal: str = "") -> dict:
        """Create a sprint on the given board. Returns {id, name}."""
        body = {
            "name": name,
            "originBoardId": board_id,
            "goal": goal,
        }
        resp = self._req("POST", "/sprint", body, agile=True)
        return {"id": resp["id"], "name": name}

    def add_issues_to_sprint(self, sprint_id: int, issue_keys: list[str]) -> dict:
        """Move a batch of issues into a sprint."""
        body = {"issues": issue_keys}
        self._req("POST", f"/sprint/{sprint_id}/issue", body, agile=True)
        return {"sprint_id": sprint_id, "moved": issue_keys}

    # ── convenience ─────#

    def issue_url(self, key: str) -> str:
        """Return the browse URL for an issue key."""
        return f"{self.base_url}/browse/{key}"

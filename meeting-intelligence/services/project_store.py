
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from copy import deepcopy

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "projects"


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _project_path(project_id: str) -> Path:
    return DATA_DIR / f"{project_id}.json"


def _default_stages() -> dict:
    """Return the blank stage skeleton for a new project."""
    return {
        "1": {
            "status": "active",
            "transcript": "",
            "extraction": None,
            "corrections": [],
            "approved": False,
        },
        "2": {
            "status": "locked",
            "questions": [],
            "user_questions": [],
            "approved": False,
        },
        "3": {
            "status": "locked",
            "sow": "",
            "changelog": [],
            "feedback_rounds": 0,
            "approved": False,
        },
        "4": {
            "status": "locked",
            "tasks": [],
            "sprints": [],
            "approved": False,
        },
        "5": {
            "status": "locked",
            "jira_config": {},
            "created_items": [],
            "sync_log": [],
            "approved": False,
        },
    }


# ── CRUD ──────#

def create_project(name: str) -> dict:
    """Create a new project with default empty stages."""
    _ensure_dir()
    project = {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": datetime.now().isoformat(),
        "current_stage": 1,
        "stages": _default_stages(),
    }
    save_project(project)
    return project


def save_project(project: dict):
    """Write the full project dict to disk."""
    _ensure_dir()
    path = _project_path(project["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)


def load_project(project_id: str) -> dict | None:
    """Load a project from disk, or return None."""
    path = _project_path(project_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_projects() -> list[dict]:
    """Return [{id, name, created_at, current_stage}, …] for every project."""
    _ensure_dir()
    projects = []
    for fp in sorted(DATA_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                p = json.load(f)
                projects.append({
                    "id": p["id"],
                    "name": p["name"],
                    "created_at": p.get("created_at", ""),
                    "current_stage": p.get("current_stage", 1),
                })
        except Exception:
            continue
    return projects


def delete_project(project_id: str):
    path = _project_path(project_id)
    if path.exists():
        path.unlink()


# ── Helpers ──────#

def advance_stage(project: dict, from_stage: int):
    """Mark *from_stage* as complete and unlock the next one."""
    project["stages"][str(from_stage)]["status"] = "complete"
    project["stages"][str(from_stage)]["approved"] = True
    next_s = from_stage + 1
    if str(next_s) in project["stages"]:
        project["stages"][str(next_s)]["status"] = "active"
        project["current_stage"] = next_s
    save_project(project)


def update_stage_data(project: dict, stage: int, **kwargs):
    """Merge key-value pairs into a stage dict and persist."""
    for k, v in kwargs.items():
        project["stages"][str(stage)][k] = v
    save_project(project)

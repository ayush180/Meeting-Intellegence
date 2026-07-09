# Meeting Intelligence & Project Automation

> AI-powered pipeline that converts client meeting transcripts into structured project scopes, sprint plans, and Jira tickets — with human approval at every stage.

---

## 🏗️ Architecture

```
meeting-intelligence/
├── app.py                      # Streamlit entry point
├── services/
│   ├── ai_service.py           # Google Gemini integration (all prompts)
│   ├── jira_service.py         # Jira Cloud REST API wrapper
│   └── project_store.py        # JSON-based project persistence
├── stages/
│   ├── stage1_extraction.py    # Transcript upload & structured extraction
│   ├── stage2_clarification.py # AI-driven Q&A with follow-ups
│   ├── stage3_sow.py           # Scope of Work generation & revision
│   ├── stage4_sprint.py        # Task & sprint plan generation
│   └── stage5_jira.py          # Jira sync with batch confirmation
├── data/projects/              # Auto-created — stores project state as JSON
├── requirements.txt
├── .env.example
└── README.md                   # ← You are here
```

---

## 🚀 Setup Instructions

### 1. Prerequisites
- **Python 3.10+**
- **Google AI Studio API key** (free): https://aistudio.google.com/apikey
- **Jira Cloud account** (free): https://www.atlassian.com/software/jira/free

### 2. Install dependencies

```bash
cd meeting-intelligence
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 4. Run the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## 📋 How Each Stage Works

### Stage 1 — Transcript Upload & Extraction
- Upload a `.txt` transcript or paste it directly.
- Click **Extract Information** — the AI (Gemini 2.0 Flash) analyzes the transcript and produces a structured extraction:
  - `project_name`, `client_name`, `vendor_name`
  - Modules (name, description, priority, deadline)
  - Requirements (functional, non-functional, integration)
  - Integrations, constraints, assumptions, unknowns
- Every field has a **confidence indicator** (🟢 High / 🟡 Medium / 🔴 Low) showing whether it was explicitly stated, inferred, or guessed.
- **Plain-language corrections**: Type corrections like *"Change the vendor name to Acme Corp"* and the AI updates the extraction.
- Click **Approve Extraction** to lock it and unlock Stage 2.

### Stage 2 — AI Clarification Q&A
- The AI generates **at least 5 targeted questions** based on gaps in the extraction.
- Each question includes a *reason* citing the transcript.
- Answer questions — the AI may follow up if the answer opens a new gap.
- Skip questions with a reason if not applicable.
- **Ask your own questions** — e.g., *"Can we fit the reporting module into Sprint 2?"* — and get contextual AI answers.
- Click **Done** when enough has been clarified.

### Stage 3 — Scope of Work (SoW)
- The AI generates a full SoW document including:
  - Executive summary, in-scope / out-of-scope items
  - Modules with features and acceptance criteria
  - Integrations, constraints, assumptions, open items
  - Timeline overview
- **Feedback loop**: Provide feedback in plain text → the AI revises and shows a changelog.
- Approval only available after **at least one feedback round**.
- Download the final SoW as `.md` or `.txt`.

### Stage 4 — Sprint Planning
- The AI generates detailed tasks from the SoW, each with:
  - Title, description, module, type (Story/Task/Epic)
  - Priority, story points (Fibonacci: 1, 2, 3, 5, 8, 13)
  - Dependencies and acceptance criteria
- Tasks are organised into **2-week sprints** (max 40 story points each).
- Sprint names reflect goals (e.g., *"Sprint 1 — Core Dashboard Setup"*).
- **Move tasks** between sprints using the UI controls.
- Visual warnings for over-capacity sprints.

### Stage 5 — Jira Sync
- Enter Jira credentials (domain, email, API token, project key).
- **Connection test** before any writes.
- Three-phase batch creation with preview and confirmation for each:
  1. **Epics** — one per module
  2. **Issues** — Stories/Tasks linked to parent Epics
  3. **Sprints** — created via the Agile API with issues assigned
- Live progress indicators during creation.
- Final summary table with direct links to every Jira issue.
- Failed calls show clear errors with retry options.

---

## 🔧 Jira Configuration

1. Create a free Jira Cloud account at [atlassian.com](https://www.atlassian.com/software/jira/free).
2. Create a new Scrum project (note the **project key**, e.g., `PROJ`).
3. Generate an API token at [id.atlassian.com/manage-api-tokens](https://id.atlassian.com/manage-api-tokens).
4. In Stage 5, enter:
   - **Domain**: `your-org.atlassian.net`
   - **Email**: your Atlassian account email
   - **API Token**: the token you generated
   - **Project Key**: e.g., `PROJ`

> ⚠️ Credentials are stored in-memory for the session and in the project JSON file. Never commit `.env` or project data to version control.

---

## 🎨 Design Decisions

1. **Streamlit** chosen for rapid, functional UI with built-in session state, tabs, expanders, progress bars, and responsive layout — matching the assessment's focus on functionality over polish.

2. **Google Gemini 2.0 Flash** with JSON-mode responses for reliable structured extraction. The model is fast, free-tier friendly, and supports large context windows for full transcripts.

3. **JSON-file persistence** (`data/projects/*.json`) ensures state survives page refreshes without needing a database. Each project is fully isolated.

4. **Staged approval gates** — each stage's `approved` flag must be `True` before the next stage activates. This is enforced in both the UI and the data layer.

5. **Confidence indicators** use a simple high/medium/low scheme to flag AI certainty. This helps users quickly identify fields that need manual verification.

6. **Batch confirmation for Jira** — Epics, Issues, and Sprints are created in separate confirmed batches to prevent accidental mass writes and allow partial recovery.

---

## ⚠️ Known Limitations

1. **Jira story_points field**: Jira Cloud's story point field is often a custom field (`customfield_10016`). The app attempts `story_points` first and retries without it if the field doesn't exist. Some Jira configurations may require manual mapping.

2. **Rate limiting**: The Jira API has rate limits. The app handles 429 responses with backoff, but very large sprint plans (50+ tasks) may require patience.

3. **AI extraction quality**: Extraction quality depends on transcript clarity. Very informal or short transcripts may produce lower-confidence results. The correction mechanism mitigates this.

4. **No real-time collaboration**: The app is single-user per session. Concurrent access to the same project is not protected with locks.

5. **Transcript format**: The app expects plain-text transcripts. Audio files or PDFs must be converted to text externally.

---

## 🧪 Testing

The app was developed and tested against two provided transcripts:
- **MY CHASE Discovery** — Location-based exploration app
- **AI Money Discovery** — Financial wealth management app

Both transcripts exercise all five pipeline stages end-to-end.

---

## 📜 License

This project was created as a technical assessment submission.

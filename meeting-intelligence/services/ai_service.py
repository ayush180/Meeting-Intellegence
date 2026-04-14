
import json
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted


_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if _API_KEY:
    genai.configure(api_key=_API_KEY)

MODEL_NAME = "gemini-flash-latest"

def _model(json_mode: bool = True):
    """Return a configured GenerativeModel."""
    config = {}
    if json_mode:
        config["response_mime_type"] = "application/json"
    return genai.GenerativeModel(MODEL_NAME, generation_config=config)

def _generate_with_retry(model, prompt, max_retries=5):
    """Wrap API calls with automatic exponential backoff for 429 errors."""
    delay = 5
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except ResourceExhausted as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise


def _parse_json(text: str) -> dict | list:
   
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: find the first { or [ and parse from there
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return json.loads(text[i:])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not parse JSON from LLM response:\n{text[:300]}")



# STAGE 1 — Transcript Extraction


EXTRACTION_PROMPT = """You are a senior business analyst. Analyze the following client meeting transcript and extract ALL structured project information.

For EVERY field, provide a confidence level:
  • "high"   = explicitly stated in the transcript
  • "medium" = reasonably inferred from context
  • "low"    = guessed or ambiguous

Return a single JSON object with this EXACT schema (no extra keys):
{{
  "project_name": {{"value": "...", "confidence": "high|medium|low"}},
  "client_name":  {{"value": "...", "confidence": "high|medium|low"}},
  "vendor_name":  {{"value": "...", "confidence": "high|medium|low"}},
  "modules": [
    {{
      "name": "...",
      "description": "One-paragraph description of this module",
      "priority": "High|Medium|Low",
      "deadline": "any deadline mentioned, or empty string",
      "confidence": "high|medium|low"
    }}
  ],
  "requirements": [
    {{
      "description": "Concise requirement statement",
      "module": "module name it relates to",
      "type": "Functional|Non-Functional|Integration",
      "confidence": "high|medium|low"
    }}
  ],
  "integrations": [
    {{
      "name": "system or service name",
      "description": "what it does / why it is needed",
      "confidence": "high|medium|low"
    }}
  ],
  "constraints": [
    {{"description": "...", "confidence": "high|medium|low"}}
  ],
  "assumptions": [
    {{"description": "...", "confidence": "high|medium|low"}}
  ],
  "unknowns": [
    {{"description": "...", "confidence": "high|medium|low"}}
  ]
}}

Rules:
1. Extract at least 3 modules, 5 requirements, and 3 unknowns – the transcript is a discovery call with lots of implicit information.
2. Assumptions should capture things that were NOT said but you had to infer to make sense of the project.
3. Unknowns should capture every unresolved question, missing detail, or follow-up item.
4. Be thorough — missing a mentioned integration or constraint is unacceptable.

── TRANSCRIPT ──
{transcript}
"""


def extract_from_transcript(transcript: str) -> dict:
    """Stage 1: Parse transcript → structured extraction dict."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, EXTRACTION_PROMPT.format(transcript=transcript))
    return _parse_json(resp.text)


# ── Stage 1 — Refinement via plain-language correction ────────

REFINE_PROMPT = """You are a business analyst. Below is a structured extraction from a meeting transcript.
The user has provided corrections in plain language. Apply ALL corrections and return the updated extraction JSON.
Keep the same schema. Only change what the user asked. If a correction is ambiguous, make your best judgment and note it.

Current extraction:
{extraction}

User's correction:
{correction}

Return the full updated extraction JSON (same schema as above).
"""


def refine_extraction(extraction: dict, correction: str) -> dict:
    """Apply a plain-language correction to the extraction."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, REFINE_PROMPT.format(
        extraction=json.dumps(extraction, indent=2),
        correction=correction,
    ))
    return _parse_json(resp.text)


# STAGE 2 — Clarification Questions

QUESTIONS_PROMPT = """You are a technical project manager preparing to scope a software project.
You have the following structured extraction from a client discovery call:

{extraction}

And the original transcript:
{transcript}

Generate targeted clarification questions to fill gaps and resolve unknowns.

Rules:
1. Generate at MINIMUM 5 questions and at MAXIMUM 10.
2. Each question must be SPECIFIC to this transcript — no generic filler.
3. Each question must include a "reason" that cites or references something from the transcript.
4. Focus on: missing technical details, ambiguous requirements, unstated assumptions, integration unknowns, timeline gaps, budget, compliance.

Return JSON:
{{
  "questions": [
    {{
      "id": "q1",
      "question": "...",
      "reason": "In the transcript, [name] mentioned ... but didn't specify ...",
      "status": "open",
      "answer": "",
      "follow_ups": []
    }}
  ]
}}
"""


def generate_questions(extraction: dict, transcript: str) -> list[dict]:
    """Stage 2: Generate clarification questions from gaps in the extraction."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, QUESTIONS_PROMPT.format(
        extraction=json.dumps(extraction, indent=2),
        transcript=transcript,
    ))
    data = _parse_json(resp.text)
    return data.get("questions", data if isinstance(data, list) else [])


FOLLOWUP_PROMPT = """You are a project manager conducting a clarification session.

Context — extraction:
{extraction}

The question was:
{question}

User's answer:
{answer}

If the answer opens a new gap or follow-up, generate ONE follow-up question.
If the answer is sufficient, respond with no follow-up.

Return JSON:
{{
  "resolved": true/false,
  "follow_up": "follow-up question text or empty string",
  "follow_up_reason": "reason or empty string"
}}
"""


def process_answer(extraction: dict, question: str, answer: str) -> dict:
    """Evaluate an answer and optionally generate a follow-up question."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, FOLLOWUP_PROMPT.format(
        extraction=json.dumps(extraction, indent=2),
        question=question,
        answer=answer,
    ))
    return _parse_json(resp.text)


USER_QUESTION_PROMPT = """You are a knowledgeable project manager. The user is asking a question about the project.

Project extraction:
{extraction}

Clarification Q&A so far:
{qa_history}

User's question:
{user_question}

Provide a clear, helpful answer grounded in the project context. If you don't have enough information, say so and suggest what would be needed.

Return JSON:
{{"answer": "your detailed answer"}}
"""


def answer_user_question(extraction: dict, qa_history: list, user_question: str) -> str:
    """Let the user ask their own question and get a contextual answer."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, USER_QUESTION_PROMPT.format(
        extraction=json.dumps(extraction, indent=2),
        qa_history=json.dumps(qa_history, indent=2),
        user_question=user_question,
    ))
    data = _parse_json(resp.text)
    return data.get("answer", str(data))


# STAGE 3 — Scope of Work Generation

SOW_PROMPT = """You are a senior technical consultant. Write a comprehensive Scope of Work (SoW) document.

Inputs:
1. Structured extraction from the client meeting:
{extraction}

2. All clarification Q&A:
{qa_history}

The SoW MUST include ALL of the following sections (use markdown headers):

# Scope of Work — [Project Name]

## 1. Executive Summary
A concise overview of the project, its purpose, and value proposition.

## 2. In-Scope Items
Group by module. List specific features and capabilities that ARE included.

## 3. Out-of-Scope Items
Explicitly call out things that were mentioned or might be expected but are NOT in this phase. Be specific.

## 4. Modules and Deliverables
For each module:
### Module: [Name]
- **Priority**: High/Medium/Low
- **Features**: list each feature
- **Acceptance Criteria**: testable criteria for each feature

## 5. Integrations
For each integration:
- **System**: name
- **Purpose**: why
- **Type**: API / SDK / Data feed / etc.
- **Data Flow**: what data moves and in which direction

## 6. Constraints and Assumptions
### Constraints
(timeline, budget, compliance, technical)
### Assumptions
(things assumed to be true that weren't confirmed)

## 7. Open Items
Anything still unresolved that needs follow-up.

## 8. Timeline Overview
Sprint-level or phase-level timeline based on any deadlines mentioned.

Return the SoW as a single JSON object:
{{"sow": "full markdown text of the SoW"}}
"""


def generate_sow(extraction: dict, qa_history: list) -> str:
    """Stage 3: Generate the full Scope of Work document."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, SOW_PROMPT.format(
        extraction=json.dumps(extraction, indent=2),
        qa_history=json.dumps(qa_history, indent=2),
    ))
    data = _parse_json(resp.text)
    return data.get("sow", str(data))


REVISE_SOW_PROMPT = """You are a senior consultant revising a Scope of Work based on user feedback.

Current SoW:
{sow}

Project context:
{extraction}

User's feedback:
{feedback}

Instructions:
1. Apply ALL points from the user's feedback.
2. Keep the same section structure.
3. Return the revised SoW AND a changelog.

Return JSON:
{{
  "sow": "full revised markdown SoW",
  "changelog": ["change 1 description", "change 2 description", ...]
}}
"""


def revise_sow(sow: str, feedback: str, extraction: dict) -> dict:
    """Apply user feedback to the SoW and return {sow, changelog}."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, REVISE_SOW_PROMPT.format(
        sow=sow,
        extraction=json.dumps(extraction, indent=2),
        feedback=feedback,
    ))
    return _parse_json(resp.text)



# STAGE 4 — Sprint Planning


SPRINT_PROMPT = """You are a senior engineering manager. From the approved Scope of Work, generate a detailed task list and organise them into sprints.

Approved SoW:
{sow}

Project extraction for context:
{extraction}

── TASK RULES ──
Each task MUST have:
  • title — action-oriented (e.g. "Build user registration form with email verification")
  • description — 2 to 3 sentences
  • module — which module it belongs to
  • type — "Story" | "Task" | "Epic"
  • priority — "High" | "Medium" | "Low"
  • story_points — Fibonacci only: 1, 2, 3, 5, 8, 13
  • dependencies — list of task IDs that must complete first (use "T1", "T2", etc.)
  • acceptance_criteria — at least 2 testable criteria per task

── SPRINT RULES ──
  • 2-week sprints
  • Max 40 story points per sprint — WARN if exceeded
  • Sprint names must reflect the goal, e.g. "Sprint 1 — Core Dashboard Setup"
  • Dependencies respected — no task appears in an earlier sprint than its prerequisites
  • Higher priority modules should be in earlier sprints
  • Show sprint plan as: name, tasks, total story points, goal

Return JSON:
{{
  "tasks": [
    {{
      "id": "T1",
      "title": "...",
      "description": "...",
      "module": "...",
      "type": "Story|Task|Epic",
      "priority": "High|Medium|Low",
      "story_points": 5,
      "dependencies": [],
      "acceptance_criteria": ["...", "..."]
    }}
  ],
  "sprints": [
    {{
      "name": "Sprint 1 — ...",
      "goal": "...",
      "task_ids": ["T1", "T2"],
      "total_points": 13,
      "warning": ""
    }}
  ]
}}
"""


def generate_sprint_plan(sow: str, extraction: dict) -> dict:
    """Stage 4: Generate tasks + sprint plan from the approved SoW."""
    model = _model(json_mode=True)
    resp = _generate_with_retry(model, SPRINT_PROMPT.format(
        sow=sow,
        extraction=json.dumps(extraction, indent=2),
    ))
    return _parse_json(resp.text)

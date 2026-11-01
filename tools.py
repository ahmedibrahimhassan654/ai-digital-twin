"""Tools the twin can call, plus the dispatcher that runs them.

Each tool is three things: a plain Python function, a JSON schema telling the
model when and how to call it, and an entry in `tool_map` so the dispatcher can
find the function by name.
"""

import inspect
import json
import os
import re
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

pushover_user = os.getenv("PUSHOVER_USER")
pushover_token = os.getenv("PUSHOVER_TOKEN")

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_FILE = BASE_DIR / "projects.json"
MAX_PROJECT_MATCHES = 3

# Words that carry no signal when matching a project.
STOPWORDS = {
    "the", "and", "for", "you", "your", "his", "her", "about", "tell", "with",
    "was", "were", "did", "does", "have", "has", "had", "what", "which", "how",
    "project", "projects", "work", "worked", "built", "build", "using", "used",
    "from", "that", "this", "any", "can", "could", "would", "please", "more",
}


def _load_projects():
    """Read the curated project catalogue. Never raises: the twin must boot."""
    try:
        with open(PROJECTS_FILE, encoding="utf-8") as f:
            return json.load(f)["projects"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"projects.json unavailable: {exc!r}", flush=True)
        return []


PROJECTS = _load_projects()

CONTACT = {
    "email": os.getenv("CONTACT_EMAIL", "ahmedibrahimhassan654@gmail.com"),
    "linkedin": "https://www.linkedin.com/in/ahmed-ibrahim5588",
    "portfolio": "https://ahmedwebdev.netlify.app",
    "location": "Cairo, Egypt",
    "languages": ["Arabic (native)", "English (professional)"],
}


def push(text):
    """Send a notification to the owner's phone. Never raises."""
    if not pushover_user or not pushover_token:
        print("Pushover keys missing - skipping notification", flush=True)
        return False

    try:
        response = requests.post(
            PUSHOVER_URL,
            data={
                "token": pushover_token,
                "user": pushover_user,
                "message": text,
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"Pushover failed: {exc!r}", flush=True)
        return False


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording interest from {name} with email {email} and notes {notes}")
    return "OK"


def record_unknown_question(question):
    push(f"Recording {question} asked that I couldn't answer")
    return "OK"


def _searchable(project):
    """Flatten the fields a visitor might search by into one lowercase string."""
    return " ".join(
        [
            project.get("name", ""),
            project.get("company", ""),
            project.get("role", ""),
            " ".join(project.get("stack", [])),
            " ".join(project.get("keywords", [])),
            " ".join(project.get("highlights", [])),
        ]
    ).lower()


def lookup_project(query):
    """Keyword search over projects.json. Returns the best matches, or none."""
    terms = [
        term
        for term in re.findall(r"[a-z0-9+#.]+", (query or "").lower())
        if len(term) > 2 and term not in STOPWORDS
    ]
    if not terms:
        return {"query": query, "matches": [], "note": "no usable search terms"}

    scored = []
    for project in PROJECTS:
        text = _searchable(project)
        name = project.get("name", "").lower()
        score = 0
        for term in terms:
            score += text.count(term)
            if term in name:
                score += 3  # a hit on the project name matters most
        if score:
            scored.append((score, project))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    matches = [project for _, project in scored[:MAX_PROJECT_MATCHES]]
    return {
        "query": query,
        "matches": matches,
        "note": "" if matches else "no project in the catalogue matched",
    }


def get_contact_details():
    """The public ways to reach the owner. No side effects."""
    return dict(CONTACT)


def record_conversation_rating(rating, comment="No comment provided"):
    """Store a 1-5 rating and notify the owner. Validates rather than raises."""
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return {"ok": False, "error": "rating must be a number between 1 and 5"}

    if value != int(value) or not 1 <= value <= 5:
        return {"ok": False, "error": "rating must be a whole number between 1 and 5"}

    rating_int = int(value)
    notified = push(f"Visitor rated the conversation {rating_int}/5. Comment: {comment}")
    return {"ok": True, "rating": rating_int, "notified": bool(notified)}


def escalate_to_human(reason, urgency="normal"):
    """Flag a conversation for a human reply and notify the owner with a ticket."""
    urgency = (urgency or "normal").lower()
    if urgency not in ("low", "normal", "high"):
        urgency = "normal"

    ticket = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    notified = push(f"[{urgency.upper()}] Escalation {ticket}: {reason}")
    return {
        "ok": True,
        "ticket": ticket,
        "urgency": urgency,
        "notified": bool(notified),
        "reason": reason,
    }


record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of this user"},
            "name": {"type": "string", "description": "The user's name, if they provided it"},
            "notes": {
                "type": "string",
                "description": "Any additional info about the conversation that's worth recording to give context",
            },
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question that couldn't be answered"},
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}

lookup_project_json = {
    "name": "lookup_project",
    "description": (
        "Search the project catalogue for details of a specific project, product or "
        "technology the person has worked with. Use when a visitor asks about a "
        "project, what was built at a company, or where a technology was applied."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Project name, company or technology, e.g. 'car rental' or 'Socket.io'",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

get_contact_details_json = {
    "name": "get_contact_details",
    "description": (
        "Return the person's public contact links (email, LinkedIn, portfolio, location). "
        "Use when a visitor asks how to reach them, for their CV links, or where they are based."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}

record_conversation_rating_json = {
    "name": "record_conversation_rating",
    "description": (
        "Record how useful the visitor found this conversation, on a 1-5 scale. "
        "Use only when the visitor rates the chat or gives clear feedback on it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "rating": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Whole number from 1 (poor) to 5 (excellent)",
            },
            "comment": {
                "type": "string",
                "description": "The visitor's comment, if they gave one",
            },
        },
        "required": ["rating"],
        "additionalProperties": False,
    },
}

escalate_to_human_json = {
    "name": "escalate_to_human",
    "description": (
        "Escalate the conversation so the person replies themselves. Use for hiring or "
        "contract enquiries, urgent requests, or when the visitor asks to speak to a human."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why this needs a human reply, including any context the visitor gave",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "description": "How urgent the request is; defaults to normal",
            },
        },
        "required": ["reason"],
        "additionalProperties": False,
    },
}

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json},
    {"type": "function", "function": lookup_project_json},
    {"type": "function", "function": get_contact_details_json},
    {"type": "function", "function": record_conversation_rating_json},
    {"type": "function", "function": escalate_to_human_json},
]

tool_map = {
    "record_user_details": record_user_details,
    "record_unknown_question": record_unknown_question,
    "lookup_project": lookup_project,
    "get_contact_details": get_contact_details,
    "record_conversation_rating": record_conversation_rating,
    "escalate_to_human": escalate_to_human,
}


def handle_tool_calls(tool_calls):
    results = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments or "{}")
        print(f"Tool called: {tool_name} {arguments}", flush=True)

        tool = tool_map.get(tool_name)
        if tool is None:
            result = f"Unknown tool: {tool_name}"
        else:
            # Ignore arguments the function does not accept.
            accepted = inspect.signature(tool).parameters
            kwargs = {key: value for key, value in arguments.items() if key in accepted}
            result = tool(**kwargs)

        results.append(
            {"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id}
        )
    return results

---
title: AI Digital Twin
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: static
pinned: false
short_description: A career chat twin built on my CV and profile.
---

# AI Digital Twin

A chat assistant built on my CV and LinkedIn profile. It answers career questions, looks
projects up on demand, captures a recruiter's email, and pings my phone when someone wants
a human — without inventing experience I don't have.

This Space is a **static showcase**: the six-scenario demo replays real recorded sessions,
including the tool call the model chose and the arguments it sent. The live app needs a
Python process, so it isn't hosted here.

**Source, and one-command local run:** https://github.com/ahmedibrahimhassan654/ai-digital-twin

## Stack

- Python 3.12 + Gradio 6 (`ChatInterface`)
- Gemini 3.1 Flash Lite via Google's OpenAI-compatible endpoint
- Six hand-written tools with JSON schemas and a name-based dispatcher
- Pushover for phone notifications

## What the real app does

| Tool | Fires when | Effect |
|---|---|---|
| `record_user_details` | A visitor leaves an email | Pushover with email and context |
| `record_unknown_question` | The answer isn't in the profile | Logs the gap |
| `lookup_project` | A project or technology comes up | Keyword search over 8 curated projects |
| `get_contact_details` | Someone asks how to reach me | Returns fixed links, never a guess |
| `record_conversation_rating` | A visitor rates the chat | Validates 1–5, then notifies me |
| `escalate_to_human` | Recruiter or urgent request | Mints an `ESC-…` ticket with urgency |

Run it locally:

```bash
git clone https://github.com/ahmedibrahimhassan654/ai-digital-twin.git
cd ai-digital-twin
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # GOOGLE_API_KEY, PUSHOVER_USER, PUSHOVER_TOKEN
python app.py
```

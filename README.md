# AI Digital Twin

**An AI that answers for me.** A chat assistant built on my CV and LinkedIn profile that talks to
visitors, captures their email, and pings my phone when someone wants a human — or asks something
I can't answer.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/UI-Gradio-FF7C00)](https://www.gradio.app/)
[![Gemini](https://img.shields.io/badge/LLM-Gemini%203.1%20Flash%20Lite-4285F4)](https://ai.google.dev/)

**Live demo:** [huggingface.co/spaces/AhmedIbrahim5588/ahmed-digital-twin](https://huggingface.co/spaces/AhmedIbrahim5588/ahmed-digital-twin) — a static walkthrough of six real sessions.
**Live chat:** `python app.py --share` prints a public `*.gradio.live` link in seconds.

## What it does

- Answers career questions from `summary.txt` and the full `linkedin.pdf`.
- Looks projects up on demand — `lookup_project` searches a curated catalogue, so "tell me about the car rental work" returns specifics, not the whole CV.
- Gives out real links — `get_contact_details` returns configured values, never a guess.
- Captures leads, ratings and escalations, and notifies me via Pushover.
- Stays honest and on topic: if the answer isn't in the profile it says so.

## How it works

The agent loop is the whole idea: ask the model, run whatever tools it asks for, feed the results
back, repeat until it answers in plain text.

```python
response = client.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools)

while response.choices[0].finish_reason == "tool_calls":
    msg = response.choices[0].message
    results = handle_tool_calls(msg.tool_calls)

    messages.append(assistant_turn(msg))   # what the model asked for
    messages.extend(results)               # what actually happened
    response = client.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools)

return response.choices[0].message.content
```

Three details that matter: the full conversation is resent every turn (all of the "memory"),
history is rebuilt as clean `{role, content}` pairs because Gradio 6 adds metadata the API rejects,
and the loop is capped at 5 tool rounds.

Gemini exposes an OpenAI-compatible endpoint, so the standard `openai` SDK works unchanged.

## Tools

| Tool | Fires when | Effect |
|---|---|---|
| `record_user_details` | A visitor leaves an email | Pushover with email and context |
| `record_unknown_question` | The answer isn't in the profile | Logs the gap |
| `lookup_project` | A project, company or technology comes up | Keyword search over 8 curated projects |
| `get_contact_details` | Someone asks how to reach me | Fixed links, never paraphrased |
| `record_conversation_rating` | A visitor rates the chat | Validates 1–5, then notifies me |
| `escalate_to_human` | Recruiter, contract or urgent request | Mints an `ESC-…` ticket with urgency |

Each tool is a JSON schema, a Python function, and a `tool_map` entry — adding one touches three places.

## Quickstart

```bash
git clone https://github.com/ahmedibrahimhassan654/ai-digital-twin.git
cd ai-digital-twin
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py                                       # http://127.0.0.1:7860
```

| Variable | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `PUSHOVER_USER` / `PUSHOVER_TOKEN` | [pushover.net](https://pushover.net) dashboard / new application |
| `MODEL_NAME` | Optional, defaults to `gemini-3.1-flash-lite` |

Pushover keys are optional — without them the tools log instead of notifying.

## Testing

```bash
python check.py --tools     # 6 tool checks, no API calls
python check.py --offline   # env, PDF, prompt, history, tools
python check.py             # + four real model conversations
python check.py --push      # + a real Pushover notification
```

Current run: **14/14 checks pass**, including a full tool round trip and a history check proving the
model sees prior turns.

## Deploying

| Option | Cost | Notes |
|---|---|---|
| `python app.py --share` | free | Public `*.gradio.live` URL while your machine runs |
| Static Space (`space/`) | free | Showcase page, replays recorded sessions — no Python |
| [Render](https://render.com) via `render.yaml` | free tier | Permanent URL, sleeps after 15 min idle |

```bash
python scripts/deploy_space.py --sdk static   # showcase + app source
python scripts/deploy_space.py --sdk gradio   # real Gradio Space (needs PRO or a 30-day-old account)
```

The Render blueprint needs no config — **New → Blueprint → select this repo**, then paste the three
secrets. Gradio binds to Render's port through `GRADIO_SERVER_NAME` / `GRADIO_SERVER_PORT`, which
`render.yaml` already sets.

## Limits

- **No persistence** — leads, ratings and escalations live only in the notification. A durable store is the next step.
- **Keyword matching, not retrieval** — `lookup_project` scores word overlaps, so it misses paraphrases an embedding index would catch.
- **Prompt injection is possible** — a determined visitor can try to talk the twin out of character; private details are kept out of the prompt.

One honest gap: the model sometimes drops the visitor's comment when recording a rating, so the
notification says *No comment provided*. Making `comment` required is the fix.

---

Built as part of an AI engineering course, then extended with a Gemini backend, a hardened agent
loop and a test script.

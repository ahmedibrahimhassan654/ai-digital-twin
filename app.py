"""Gradio front end for the digital twin.

`chat()` below is the whole agent: ask the model, run whatever tools it asks
for, feed the results back, and repeat until it answers in plain text.
"""

import os
import sys

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

from context import TWIN_SYSTEM_PROMPT
from styles import CSS, EXAMPLES, JS
from tools import handle_tool_calls, tools

load_dotenv(override=True)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.1-flash-lite")
MAX_TOOL_ROUNDS = 5

# Gemini exposes an OpenAI-compatible endpoint, so the standard SDK works.
client = OpenAI(base_url=GEMINI_BASE_URL, api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_MESSAGE = [{"role": "system", "content": TWIN_SYSTEM_PROMPT}]


def clean_history(history):
    """Keep only role/content keys.

    Gradio 6 adds metadata (durations, options, attachments) to history items
    that the API rejects, so the history is rebuilt before every request.
    """
    cleaned = []
    for item in history or []:
        if isinstance(item, dict):
            role, content = item.get("role"), item.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def assistant_turn(message):
    """Rebuild the assistant message as a clean dict for the next request.

    Gemini 3 attaches a `thought_signature` to every function call in
    `extra_content` and rejects the follow-up request if it is not sent back,
    so it is carried over verbatim.
    """
    tool_calls = []
    for call in message.tool_calls or []:
        entry = {
            "id": call.id,
            "type": "function",
            "function": {
                "name": call.function.name,
                "arguments": call.function.arguments,
            },
        }
        extra_content = getattr(call, "extra_content", None)
        if extra_content:
            entry["extra_content"] = extra_content
        tool_calls.append(entry)

    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": tool_calls,
    }


def chat(message, history):
    messages = SYSTEM_MESSAGE + clean_history(history) + [{"role": "user", "content": message}]

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME, messages=messages, tools=tools
        )

        rounds = 0
        while response.choices[0].finish_reason == "tool_calls" and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            assistant_message = response.choices[0].message
            results = handle_tool_calls(assistant_message.tool_calls)
            messages.append(assistant_turn(assistant_message))
            messages.extend(results)
            response = client.chat.completions.create(
                model=MODEL_NAME, messages=messages, tools=tools
            )
    except Exception as exc:  # a dropped request should not crash the chat
        print(f"Chat failed: {exc!r}", flush=True)
        return "Sorry, I hit a technical problem just now. Please try again in a moment."

    return response.choices[0].message.content or "I've noted that and will follow up."


if __name__ == "__main__":
    # `python app.py --share` (or GRADIO_SHARE=1) prints a public *.gradio.live
    # URL so a recruiter can try the twin without you deploying anything.
    share = "--share" in sys.argv or os.getenv("GRADIO_SHARE", "").lower() in ("1", "true", "yes")

    gr.ChatInterface(
        chat,
        examples=EXAMPLES,
        title="Digital Twin",
        description="Talk to my AI twin about my career",
        chatbot=gr.Chatbot(show_label=False),
    ).launch(css=CSS, js=JS, theme=gr.themes.Base(), share=share)

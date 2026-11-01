"""Smoke checks for the digital twin.

Three groups of checks:

* offline  - environment, file loading, history cleaning. No network, no cost.
* live     - real calls to Gemini. Takes a few seconds and a few tokens.
* --push   - tools that send a real notification to your phone.

Usage:
    python check.py            # offline + live chat checks
    python check.py --offline  # offline only (no API calls, no cost)
    python check.py --push     # everything, including a real notification
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)


# --------------------------------------------------------------------------
# offline checks
# --------------------------------------------------------------------------


def env_keys():
    missing = [name for name in ("GOOGLE_API_KEY",) if not os.getenv(name)]
    assert not missing, f"missing environment variables: {', '.join(missing)}"
    return "GOOGLE_API_KEY found"


def pushover_keys():
    missing = [name for name in ("PUSHOVER_USER", "PUSHOVER_TOKEN") if not os.getenv(name)]
    assert not missing, f"missing environment variables: {', '.join(missing)}"
    assert os.getenv("PUSHOVER_USER", "").startswith("u"), "PUSHOVER_USER should start with u"
    assert os.getenv("PUSHOVER_TOKEN", "").startswith("a"), "PUSHOVER_TOKEN should start with a"
    return "both Pushover keys found"


def loads_context():
    import context

    assert context.summary.strip(), "summary.txt is empty"
    assert len(context.linkedin) > 1000, "linkedin.pdf produced almost no text"
    assert "digital twin" in context.TWIN_SYSTEM_PROMPT.lower()
    return f"prompt built from {len(context.linkedin)} chars of PDF text"


def cleans_history():
    from app import clean_history

    dirty = [
        {"role": "user", "content": "hi", "metadata": {"id": 1}, "duration": 1.2},
        {"role": "assistant", "content": "hello", "options": []},
        {"role": "user", "content": ""},
        {"role": "system", "content": "must be dropped"},
    ]
    cleaned = clean_history(dirty)
    expected = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert cleaned == expected, f"got {cleaned}"
    return "metadata and empty turns removed"


def tools_registered():
    from tools import tool_map, tools

    names = {entry["function"]["name"] for entry in tools}
    assert names == set(tool_map), f"schema and tool_map disagree: {names} vs {set(tool_map)}"
    return f"{len(names)} tools: {', '.join(sorted(names))}"


# --------------------------------------------------------------------------
# live checks (these call Gemini)
# --------------------------------------------------------------------------


def smoke_chat():
    from app import chat

    reply = chat("Hello! In one sentence, who are you?", [])
    assert reply and len(reply) > 20, f"short reply: {reply!r}"
    return reply.replace("\n", " ")[:100]


def remembers_name():
    from app import chat

    history = [
        {"role": "user", "content": "Hi, my name is Ahmed."},
        {"role": "assistant", "content": "Nice to meet you, Ahmed."},
    ]
    reply = chat("What is my name?", history)
    assert "ahmed" in reply.lower(), f"history was ignored: {reply!r}"
    return "history reached the model"


def answers_without_crashing():
    from app import chat

    reply = chat("What is the capital of France?", [])
    assert reply and len(reply) > 10, f"empty reply: {reply!r}"
    return "off-topic question handled"


# --------------------------------------------------------------------------
# notification checks (--push)
# --------------------------------------------------------------------------


def pushover_delivery():
    from tools import push

    sent = push("check.py: test notification")
    assert sent is True, "Pushover rejected the request - check PUSHOVER_USER / PUSHOVER_TOKEN"
    return "notification sent to your phone"


def record_user_details_tool():
    from tools import record_user_details

    result = record_user_details("check@example.com", "Check.py", "test run")
    assert result == "OK", result
    return "lead tool ran"


def record_unknown_question_tool():
    from tools import record_unknown_question

    result = record_unknown_question("Does check.py work?")
    assert result == "OK", result
    return "unknown-question tool ran"


# --------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Run smoke checks for the digital twin.")
    parser.add_argument("--offline", action="store_true", help="skip checks that call the LLM")
    parser.add_argument("--push", action="store_true", help="also run checks that notify your phone")
    args = parser.parse_args()

    checks = [env_keys, pushover_keys, loads_context, cleans_history, tools_registered]

    if not args.offline:
        checks += [smoke_chat, remembers_name, answers_without_crashing]

    if args.push:
        checks += [pushover_delivery, record_user_details_tool, record_unknown_question_tool]

    failures = 0
    for check in checks:
        label = check.__name__.replace("_", " ")
        try:
            detail = check()
            print(f"PASS  {label}  -  {detail}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {label}  -  {exc}")
        except Exception as exc:  # noqa: BLE001 - report, do not abort the run
            failures += 1
            print(f"ERROR {label}  -  {type(exc).__name__}: {exc}")

    passed = len(checks) - failures
    print(f"\n{passed}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

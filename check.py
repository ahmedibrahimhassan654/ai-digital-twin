"""Smoke checks for the digital twin.

Three groups of checks:

* offline  - environment, file loading, history cleaning, every tool called directly.
             No network, no cost, no notifications.
* live     - real calls to Gemini. Takes a few seconds and a few tokens.
* --push   - tools that send a real notification to your phone.

Usage:
    python check.py            # offline + live chat checks
    python check.py --offline  # offline only (no API calls, no cost)
    python check.py --tools    # only the six tool checks
    python check.py --push     # everything, including a real notification
"""

import argparse
import os
import sys
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv(override=True)


@contextmanager
def stub_push(module):
    """Swap push() for a recorder so a check never buzzes a real phone."""
    sent = []

    def fake_push(text):
        sent.append(text)
        return True

    original = module.push
    module.push = fake_push
    try:
        yield sent
    finally:
        module.push = original


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


def keeps_thought_signature():
    from types import SimpleNamespace

    from app import assistant_turn

    signature = {"google": {"thought_signature": "abc123"}}
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(
                    name="record_user_details", arguments='{"email":"a@b.com"}'
                ),
                extra_content=signature,
            )
        ],
    )
    call = assistant_turn(message)["tool_calls"][0]
    assert call.get("extra_content") == signature, (
        "thought_signature dropped - Gemini rejects the follow-up request"
    )
    return "tool calls keep their thought_signature"


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


def completes_tool_round():
    """An email should produce a tool round trip, not the apology sentence.

    `push` is stubbed so a live run does not buzz the phone; `--push` covers
    real delivery.
    """
    import tools
    from app import chat

    with stub_push(tools) as sent:
        reply = chat("I'd like to get in touch - check@example.com", [])

    assert "technical problem" not in reply.lower(), f"tool round failed: {reply!r}"
    assert sent, f"the model never called a tool: {reply!r}"
    return f"tool round trip completed, {len(sent)} notification stubbed"


# --------------------------------------------------------------------------
# tool checks (offline - every tool is called directly, push is stubbed)
# --------------------------------------------------------------------------


def lookup_project_catalogue():
    import tools

    assert tools.PROJECTS, "projects.json is empty or missing"
    result = tools.lookup_project("car rental")
    assert result["matches"], result
    top = result["matches"][0]["name"]
    assert "car rental" in top.lower(), f"unexpected top match: {top}"

    unrelated = tools.lookup_project("quantum basket weaving")
    assert not unrelated["matches"], f"matched something irrelevant: {unrelated}"
    return f"{len(result['matches'])} match(es) for 'car rental', unrelated query rejected"


def contact_details():
    import tools

    details = tools.get_contact_details()
    for field in ("email", "linkedin", "portfolio", "location"):
        assert details.get(field), f"missing {field}: {details}"
    assert details["linkedin"].startswith("https://"), details["linkedin"]
    return f"{len(details)} fields, portfolio {details['portfolio']}"


def rating_tool():
    import tools

    with stub_push(tools) as sent:
        good = tools.record_conversation_rating(5, "very helpful")
        too_high = tools.record_conversation_rating(9)
        not_a_number = tools.record_conversation_rating("great")

    assert good["ok"] is True and good["notified"] is True, good
    assert too_high["ok"] is False, too_high
    assert not_a_number["ok"] is False, not_a_number
    assert len(sent) == 1, f"expected one notification, got {len(sent)}"
    return "1-5 accepted, 9 and non-numeric rejected, 1 notification"


def escalation_tool():
    import tools

    with stub_push(tools) as sent:
        high = tools.escalate_to_human("Contract enquiry from a recruiter", "high")
        default = tools.escalate_to_human("Wants to speak to a human")

    assert high["ok"] and high["ticket"].startswith("ESC-"), high
    assert high["urgency"] == "high", high
    assert default["urgency"] == "normal", default
    assert high["ticket"] != default["ticket"], "tickets must be unique"
    assert sent[0].startswith("[HIGH]"), sent[0]
    return f"ticket {high['ticket']} at high urgency, urgency defaults to normal"


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
    parser.add_argument("--tools", action="store_true", help="only run the tool checks")
    parser.add_argument("--push", action="store_true", help="also run checks that notify your phone")
    args = parser.parse_args()

    tool_checks = [lookup_project_catalogue, contact_details, rating_tool, escalation_tool]

    if args.tools:
        checks = tool_checks
    else:
        checks = [
            env_keys,
            pushover_keys,
            loads_context,
            cleans_history,
            tools_registered,
            keeps_thought_signature,
        ] + tool_checks

        if not args.offline:
            checks += [
                smoke_chat,
                remembers_name,
                answers_without_crashing,
                completes_tool_round,
            ]

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

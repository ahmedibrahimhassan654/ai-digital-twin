"""Build and upload the Hugging Face Space bundle.

    python scripts/deploy_space.py --sdk static    # showcase page + app source (grant-ready)
    python scripts/deploy_space.py --sdk gradio    # real ZeroGPU Space (needs PRO or a 30-day-old account)

Only runtime files are copied into `.space-build/`, so `.env`, `.history/` and
the virtualenv can never reach the Hub. The Space gets its own requirements.txt
(huggingface_hub forbids pinning gradio / spaces / huggingface_hub) and a README
with the frontmatter matching the chosen SDK.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / ".space-build"
SPACE_ID = "AhmedIbrahim5588/ahmed-digital-twin"
GRADIO_VERSION = "6.31.0"

APP_FILES = [
    "app.py",
    "context.py",
    "tools.py",
    "styles.py",
    "projects.json",
    "summary.txt",
    "linkedin.pdf",
]

SECRET_KEYS = ["GOOGLE_API_KEY", "PUSHOVER_USER", "PUSHOVER_TOKEN"]

STATIC_README = """\
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

A chat assistant built on my CV and LinkedIn profile. It answers career questions,
looks projects up on demand, captures a recruiter's email, and pings my phone when
someone wants a human — without inventing experience I don't have.

This Space is a **static showcase**: the six-scenario demo replays real recorded
sessions, including the tool call the model chose and the arguments it sent.

The Gradio app source is in this repo too, so the Space only needs its `sdk:` line
flipped to `gradio` once hardware is available.

**Source, and one-command local run:** https://github.com/ahmedibrahimhassan654/ai-digital-twin
"""

GRADIO_README = f"""\
---
title: AI Digital Twin
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: {GRADIO_VERSION}
app_file: app.py
python_version: "3.12"
startup_duration_timeout: 30m
pinned: false
short_description: A career chat twin built on my CV and profile.
---

# AI Digital Twin

Ask my CV anything. A Gradio chat assistant built on my summary and LinkedIn
profile, with a hand-written agent loop: the model can call six tools, the app runs
them, and the results are fed back until it answers in plain text.

- `lookup_project` — keyword search over a curated project catalogue
- `get_contact_details` — fixed links, never a guess
- `record_user_details` / `record_conversation_rating` / `escalate_to_human` — Pushover notifications
- `record_unknown_question` — logs what the profile can't answer

The app never touches a GPU; `app.py` imports `spaces` and exposes one no-op
`@spaces.GPU` function because ZeroGPU requires it.

**Source:** https://github.com/ahmedibrahimhassan654/ai-digital-twin
"""


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def build(sdk: str) -> Path:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()

    for name in APP_FILES:
        src = ROOT / name
        if not src.exists():
            raise SystemExit(f"missing required file: {name}")
        shutil.copy2(src, BUILD / name)

    # The Space installs gradio itself; pinning it breaks resolution.
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line.strip() and not line.lower().startswith("gradio")]
    (BUILD / "requirements.txt").write_text("\n".join(kept) + "\n", encoding="utf-8")

    if sdk == "static":
        shutil.copy2(ROOT / "space" / "index.html", BUILD / "index.html")
        (BUILD / "README.md").write_text(STATIC_README, encoding="utf-8")
    else:
        (BUILD / "README.md").write_text(GRADIO_README, encoding="utf-8")

    return BUILD


def upload(folder: Path) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    api.upload_folder(
        folder_path=str(folder),
        repo_id=SPACE_ID,
        repo_type="space",
        commit_message="Deploy digital twin Space",
        ignore_patterns=["**/__pycache__/**", "*.pyc", ".env"],
    )
    print(f"uploaded -> https://huggingface.co/spaces/{SPACE_ID}")


def push_secrets() -> None:
    from huggingface_hub import HfApi

    env = read_env(ROOT / ".env")
    missing = [key for key in SECRET_KEYS if not env.get(key)]
    if missing:
        raise SystemExit(f"missing in .env: {', '.join(missing)}")

    api = HfApi()
    for key in SECRET_KEYS:
        api.add_space_secret(SPACE_ID, key, env[key])
        print(f"secret set: {key}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", choices=["static", "gradio"], default="static")
    parser.add_argument("--build-only", action="store_true", help="assemble .space-build/ without uploading")
    args = parser.parse_args()

    folder = build(args.sdk)
    print(f"built {folder} ({len(list(folder.iterdir()))} files, sdk={args.sdk})")

    if args.build_only:
        return 0

    upload(folder)
    if args.sdk == "gradio":
        push_secrets()
    return 0


if __name__ == "__main__":
    sys.exit(main())

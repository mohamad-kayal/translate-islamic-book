#!/bin/sh
# From a fresh clone to a working tool. Safe to re-run; run it again after moving this folder,
# because the skill links are absolute.
set -e
cd "$(dirname "$0")"
REPO=$(pwd -P)

if [ ! -x .venv/bin/python ]; then
    for candidate in python3.12 python3.13 python3.14 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then PY=$candidate; break; fi
    done
    [ -n "$PY" ] || { echo "Python 3.9 or newer is required."; exit 1; }
    echo "Creating .venv with $("$PY" --version)"
    "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q -r requirements.txt -r requirements-dev.txt

echo "Downloading the pinned datasets (about 210 MB, checked against data/MANIFEST.json)"
.venv/bin/python scripts/setup_data.py | tail -1

# Claude Code reads ~/.claude/skills; Codex, Gemini CLI and others read ~/.agents/skills.
for dir in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
    mkdir -p "$dir"
    for skill in skills/*/; do
        name=$(basename "$skill")
        ln -sfn "$REPO/skills/$name" "$dir/$name"
    done
done

.venv/bin/python -m scripts.doctor

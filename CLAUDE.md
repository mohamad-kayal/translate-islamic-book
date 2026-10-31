@AGENTS.md

## Claude Code

The skills in `.claude/skills/` are this repo's entry points. Large fan-outs run as Workflows from
`.claude/workflows/` (each skill says when), and the usage gate in `scripts.run_status --gate` needs
the statusline from `scripts/statusline_usage.py`.

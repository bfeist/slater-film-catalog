# Agent Instructions

## /o/ Drive — CRITICAL SAFETY RULE

The `/o/` path (network share with archival video) is **STRICTLY READ-ONLY**.

- **NEVER** write files to `/o/`
- **NEVER** delete files from `/o/`
- **NEVER** modify files on `/o/`
- **NEVER** run any command that could alter `/o/` contents (no `mv`, `rm`, `cp ... /o/`, `rsync --delete`, etc.)
- Only use `/o/` as a **read source** for video discovery, metadata extraction, and analysis

This rule has NO exceptions.

## Verification — IMPORTANT

After any code change, find and run the project's verification command before considering work done. If it fails, fix and re-run.

- Look in `package.json` scripts, `Makefile`, `justfile`, or CI config for the canonical command.
- Common examples: `npm run test:all`, `pytest`, `npm test && npm run lint && npm run typecheck`

## Environment

- Default shell is GitBash (Windows).
- Do NOT start dev servers (`npm run dev`, `python manage.py runserver`, etc.) — assume one is already running.
- For testing and exploration, use temporary scripts rather than modifying existing code.

## Subagents

- Subagents are preferred for normal tasks. Use the main agent only for coordination and oversight in order to preserve its context window for high-level reasoning.

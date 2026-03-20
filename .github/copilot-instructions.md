# NASA Slater Film Catalog — Copilot Instructions

## What This Is

A read-only catalog of NASA 16mm/35mm archival film reels. Users browse, search, and view metadata for ~12,000 film rolls. Authenticated users (via `?key=SECRET` URL param → `sessionStorage.revealKey`) get real identifiers, filenames, and file paths; unauthenticated users see obfuscated data.

## Stack

- **Frontend**: React 19, React Router 7, TypeScript 5 (strict), Vite 7
- **Backend**: Express 5 API, Better-SQLite3 (read-only DB), bundled with esbuild
- **UI system**: **Radix UI primitives** (Dialog, Switch, Checkbox) + **CSS Modules** (`*.module.css`) + `clsx` for conditional classes
- **Theme**: CSS custom properties in `src/styles/theme.css` (`--color-*`, `--shadow-*`, etc.), dark default, switchable via `[data-theme="light"]` on `<html>`
- **Testing**: Vitest + jsdom. Lint: ESLint (with `css-modules` plugin enforcing camelCase) + Stylelint

## Key Conventions

- CSS Module classes must be **camelCase** (enforced by ESLint `css-modules/no-undef-class`)
- Global utility classes (`.muted`, `.mono-cell`, `.path-cell`, `quality-bucket-*`) live in `src/styles/global.css` — use these directly as strings alongside module classes via `clsx`
- New modals must use **Radix Dialog** with `position: fixed; inset: 0; z-index: 200` on the overlay and `position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); z-index: 201` on the content
- The `revealed` boolean (from API response) gates all sensitive data exposure — always thread it through to child components; never assume it's `true`

## Auth / Data Exposure Rules

| `revealed` | What changes                                                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `false`    | Identifier column hidden in table; filenames → `transfer-file-N`; file paths hidden; titles → alternate title; NARA citations hidden; PDF tab labels → `Document N` |
| `true`     | Full real data shown                                                                                                                                                |

## Verification

```
npm run test:all
```

## Env / Infrastructure

- Dev server: Vite on `:9300`, API on `:9301` (proxied via `/api/*`)
- `/o/` network share is **read-only archival storage** — never write to it
- Default shell: GitBash (Windows)
- Do NOT start dev servers — assume they are already running

## /o/ Drive — CRITICAL SAFETY RULE

The `/o/` path (network share with archival video) is **STRICTLY READ-ONLY**.

- **NEVER** write files to `/o/`
- **NEVER** delete files from `/o/`
- **NEVER** modify files on `/o/`
- **NEVER** run any command that could alter `/o/` contents (no `mv`, `rm`, `cp ... /o/`, `rsync --delete`, etc.)
- Only use `/o/` as a **read source** for video discovery, metadata extraction, and analysis

This rule has NO exceptions.

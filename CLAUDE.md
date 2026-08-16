# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A CV/resume generator with no application code of its own — it's a set of Claude Code
skills that turn a [JSON Resume](https://jsonresume.org/schema) document into a themed
PDF. There is no server, build system, or test suite; almost all logic lives in
`.claude/skills/*/SKILL.md`, executed by the agent itself, backed by small helper
scripts for the parts that must be deterministic (network calls, PDF rendering).

## The three skills and how they chain

1. **`linkedin-jsonresume-export`** — downloads a member's data via LinkedIn's Member
   Snapshot API (`fetch_linkedin_profile.py`) and maps it into a JSON Resume document at
   `temp/linkedin_resume.json`. Requires `LINKEDIN_ACCESS_TOKEN` in `.env` (Prerequisites
   in the README). Only EU/EEA/Switzerland members can consent to this data-portability
   flow. After running, the agent must manually translate `languages[].language` values
   to English (LinkedIn returns them in the account's UI locale) — this is intentionally
   done as an agent post-processing step, not scripted or API-driven.
2. **`jsonresume-theme-template`** — given a theme name from the
   [JSON Resume registry](https://jsonresume.org/themes), fetches visual reference
   material (README, screenshots, style files) via `fetch_theme_reference.py` using
   plain HTTP against the npm registry / unpkg — **never runs `npm install` or executes
   package code** — then the agent writes an original `themes/<theme-name>/index.html` +
   `style.css` pair that captures the visual feel without copying the source theme's
   code.
3. **`jsonresume-pdf`** — the agent populates a theme template's placeholder HTML with
   real resume JSON data (also done by the agent directly, not a templating script,
   since field mapping requires judgment), then renders it to PDF via Puppeteer
   (`html_to_pdf.js`).

Each skill's `SKILL.md` is the authoritative spec for its behavior (placeholder
conventions, field-mapping rules, error handling) — read it before modifying the
corresponding script, since the script and the doc are meant to stay in sync.

## Editing skills

When asked to change a skill's behavior, only edit files scoped to that skill's own
directory (`.claude/skills/<skill-name>/SKILL.md`, its `scripts/`, etc.). **Never** edit
temporary skill outputs instead (files under `temp/`, generated `themes/<theme-name>/`
files, populated resume HTML, rendered PDFs) — those are run artifacts, not the source
of the behavior, and changing them doesn't fix anything for the next run.

## Commands

Render a populated resume HTML to PDF (first run installs Puppeteer into the skill's
own `node_modules`):

```bash
cd .claude/skills/jsonresume-pdf/scripts && npm install   # first run only
cd /Volumes/Sources/petrkoutnycz/claude-cv-generator
node .claude/skills/jsonresume-pdf/scripts/html_to_pdf.js <input.html> <output.pdf>
```

Fetch LinkedIn profile data:

```bash
export LINKEDIN_ACCESS_TOKEN="<token>"   # or set it in .env
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py
```

Fetch theme reference material for building a new theme template:

```bash
python3 .claude/skills/jsonresume-theme-template/scripts/fetch_theme_reference.py <theme-name> \
  --out <scratchpad>/theme-ref-<theme-name>
```

There is no lint/test/build command — correctness is verified by opening the generated
HTML/PDF and visually checking it.

## Architecture conventions

- **Themes** (`themes/<theme-name>/`) are static, self-contained `index.html` +
  `style.css` pairs — no build step, no template engine, must open directly in a
  browser. `index.html` is a reference template: JSON-Resume-schema sections in source
  order, each marked with an `<!-- sectionName -->` comment, containing example
  `.entry`/`.entry-card` blocks with generic `[bracket]` placeholders. `themes/even/`
  and `themes/californian-warm/` are the canonical reference examples for the
  placeholder pattern and CSS/comment conventions respectively.
- **Populating a theme with real data is an agent judgment task, not a script.** Both
  the PDF skill (populating placeholders) and the theme-template skill (translating a
  registry theme's visual identity into original markup) deliberately push these steps
  to the calling agent instead of hardcoding template logic — resume content varies too
  much in shape (array lengths, missing fields, long text) for a fixed mapping.
- **`.claude/skills/<skill-name>/scripts/`** — each skill's helper scripts and their
  dependencies (e.g. `jsonresume-pdf`'s own `node_modules`) live under that skill's own
  folder, not in a shared repo-level scripts directory.
- **`temp/`** is gitignored and holds all generated/downloaded artifacts: LinkedIn
  exports (`linkedin_raw.json`, `linkedin_resume.json`) and rendered PDFs. Personal data
  should never be committed — keep it under `temp/`.
- **`profile_photo.jpg`** at the repo root is the one piece of personal data checked
  into the working tree (not committed — see `.gitignore`); resume JSON's `basics.image`
  is expected to point at it, and the LinkedIn export script always sets it to that
  fixed filename since LinkedIn's API has no photo field.
- **`.env`** holds `LINKEDIN_ACCESS_TOKEN`, required only for the LinkedIn export skill.

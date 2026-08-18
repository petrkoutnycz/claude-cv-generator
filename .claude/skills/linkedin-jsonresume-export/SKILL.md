---
name: linkedin-jsonresume-export
description: Download a LinkedIn member's profile data (work history, education, skills, certifications, etc.) via LinkedIn's official Member Data Portability API and convert it into a JSON Resume (jsonresume.org) document. Use when the user asks to import/download/export their LinkedIn profile, pull LinkedIn data for a CV/resume, or generate a JSON Resume file from LinkedIn.
---

# LinkedIn → JSON Resume export

Fetches a consenting member's data from LinkedIn's **Member Snapshot API** (part of the
Member Data Portability product, built for DMA/GDPR-style data portability) and maps it
into a spec-conformant [JSON Resume](https://jsonresume.org/schema) document that this
CV generator can consume.

This is the *real* portability API (`api.linkedin.com/rest/memberSnapshotData`) — not
scraping, and not LinkedIn's general-purpose "Sign In / Share" APIs.

## Prerequisites

1. A LinkedIn Developer app with the **Member Data Portability (3rd Party)** product
   approved (requires a verified LinkedIn Company Page and business verification).
2. An OAuth access token already obtained via the Authorization Code flow, with scope
   `r_dma_portability_3rd_party` (app acting on behalf of a member) or
   `r_dma_portability_member` (member downloading their own data). **Obtaining that
   token is out of scope for this skill** — get one first, then make it available to
   the script one of two ways:

   - Add it to the repo-root `.env` file (preferred — gitignored, persists across
     runs):

     ```
     LINKEDIN_ACCESS_TOKEN=<token>
     ```

     The script loads this file automatically before checking for the token.

   - Or export it in the shell for a one-off run (e.g. a different token in CI); an
     exported value always takes precedence over `.env`:

     ```bash
     export LINKEDIN_ACCESS_TOKEN="<token>"
     ```

3. Only members located in the **EU/EEA or Switzerland** can consent to share their data
   this way — this is a LinkedIn platform restriction, not a limitation of the script.

## Usage

```bash
# Default: fetch the CV-relevant domains and write temp/linkedin_resume.json
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py

# Only specific domains
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py \
  --domain PROFILE --domain POSITIONS

# Every documented snapshot domain (slow, includes non-CV data)
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py --all-domains

# Custom output path, and also keep the untrimmed raw LinkedIn data
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py \
  --output temp/resume.json --save-raw temp/linkedin_raw.json

# Re-run just the JSON Resume mapping from a previously saved raw dump
# (no network call — fast iteration while tuning field mappings)
python3 .claude/skills/linkedin-jsonresume-export/scripts/fetch_linkedin_profile.py \
  --from-raw temp/linkedin_raw.json --output temp/resume.json
```

All output paths (`--output`, `--save-raw`) are created automatically if their directory
doesn't exist yet, and default to living under `temp/` at the repo root, which is
gitignored — keeping downloaded LinkedIn data out of the repo root and out of git.

By default the script fetches the domains useful for building a CV/resume:
`PROFILE, POSITIONS, EDUCATION, SKILLS, CERTIFICATIONS, HONORS, LANGUAGES, PROJECTS,
RECOMMENDATIONS, VOLUNTEERING_EXPERIENCES`. LinkedIn documents 60+ snapshot domains in
total (e.g. `CONNECTIONS`, `ADS_CLICKED`, `SEARCHES`) — pass `--all-domains` to fetch
everything, or repeat `--domain` to pick an exact set.

## Output

The script writes a JSON Resume document (`$schema: https://jsonresume.org/schema`)
built with a **strict allowlist mapping**: only LinkedIn fields that have a defined home
in the JSON Resume schema are copied over (e.g. `basics`, `work`, `education`, `skills`,
`certificates`, `awards`, `languages`, `projects`, `volunteer`, `references`). Anything
LinkedIn returns that has no JSON Resume equivalent — zip code, geo location, internal
IDs/URNs, recommendation status metadata, and the entire long tail of non-CV domains — is
dropped, not stuffed into a custom extension field. If you want the untrimmed data too,
pass `--save-raw`.

LinkedIn's Member Snapshot API has no profile-photo field, so the script instead checks
whether a `profile_photo.jpg` file exists at the repo root — this matches the repo's
convention (see the `jsonresume-pdf` skill) of keeping a manually-maintained photo there
for themes to pick up. If found, `basics.image` is set to `"profile_photo.jpg"`; if not,
`basics.image` is left unset rather than pointing at a nonexistent file.

## Post-processing

LinkedIn reports several fields in the account's own LinkedIn UI locale, not necessarily
English — the script passes these through unchanged, with no translation logic and no
LLM API call. After generating the output file, translate each of the following fields
to English yourself (you're the agent running this skill, so no extra API key or
dependency is needed) and write the corrected values back into the output file:

- `languages[].language` — e.g. Czech `čeština` → `Czech`, `angličtina` → `English`,
  `japonština` → `Japanese`.
- `languages[].fluency` — LinkedIn's proficiency levels, e.g. `Rodilý mluvčí nebo
  dvojjazyčná znalost` → `Native or bilingual proficiency`.
- `basics.location.region` — a free-text city/country string LinkedIn builds from the
  member's `Geo Location`/`Location` field, e.g. `Praha, Česko` → `Prague, Czech
  Republic`.

This only covers fields LinkedIn itself generates in the account's UI locale. Leave
everything the member typed themselves untouched — job/position titles, company names,
summaries, descriptions, degree names, project names, etc. — even if it contains
non-English words; that's the person's own wording, not a LinkedIn UI artifact, and
translating it would change the resume's actual content.

## Troubleshooting

- **`LINKEDIN_ACCESS_TOKEN is not set`** — the script checks the shell environment and
  then the repo-root `.env` file; set the token in one of those before running (see
  Prerequisites). The script fails fast here rather than making a request.
- **`401` / `403`** — the token is missing/expired, lacks the
  `r_dma_portability_3rd_party` / `r_dma_portability_member` scope, or the member hasn't
  consented (only EU/EEA/Switzerland members can).
- **`426 NONEXISTENT_VERSION`** — LinkedIn's Member Snapshot API currently only accepts
  `Linkedin-Version: 202312`; this is hardcoded in the script but is worth checking first
  if LinkedIn changes the requirement.
- **A section is empty even though the account has that data** — LinkedIn does not
  formally document per-domain field names beyond `PROFILE`; the mapper's key-name
  guesses (mirroring LinkedIn's known personal-data-export CSV headers) may not match
  what your account returns. Run with `--save-raw` and inspect the raw JSON to find the
  actual key, then adjust the candidate keys in `fetch_linkedin_profile.py`.

## Security

- The script never prints the access token or the `Authorization` header.
- Exported profile data is personal data — the default output paths live under `temp/`
  at the repo root, which is gitignored. Don't commit real exports.

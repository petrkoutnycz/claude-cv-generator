---
name: jsonresume-pdf
description: Generate a PDF resume by populating one of this repo's themes (themes/<theme-name>/) with data from a JSON Resume-compatible file (schema at jsonresume.org/schema) and rendering it to PDF. Use when the user asks to create/export/generate a resume or CV PDF, given a theme name and a path to resume JSON data.
---

# JSON Resume → PDF

Takes two parameters:

- **theme** — a theme name matching a folder under `themes/` in the repo root (e.g. `even`,
  `californian-warm`). Run `ls themes/` to see what's available. If the requested theme
  doesn't exist, say so and offer to run the `jsonresume-theme-template` skill to create it
  first, rather than guessing a substitute.
- **resume JSON path** — path to a [JSON Resume](https://jsonresume.org/schema)-compatible
  file. It must parse as JSON and have at least a `basics` object. Defaults to
  `temp/linkedin_resume.json` unless the user specifies otherwise.

Output: a PDF file. Always write it to `<repo-root>/temp/<slugified-name>-<theme>.pdf`
(e.g. `temp/petr-koutny-even.pdf`), creating the `temp/` folder if it doesn't exist yet.

## Process

### 1. Read the inputs

Read `themes/<theme>/index.html` and `themes/<theme>/style.css`, and the resume JSON file.
The theme's `index.html` is a static template: JSON-Resume-schema sections in source order,
each marked with an `<!-- sectionName -->` comment, containing one or two example `.entry`
blocks with generic `[bracket]` placeholders (see
[themes/even/index.html](../../../themes/even/index.html) for the reference shape).

### 2. Populate the template yourself — don't script this step

Write the populated HTML directly (with the Write tool); do not write a generic templating
script or code up per-field mapping rules. Turning arbitrary resume content into a specific
theme's markup takes judgment a fixed script can't anticipate — how many entries there are,
whether a field exists at all, how to compress a long summary into the space the design
gives it. Do it the way you populated the theme's own placeholders when the theme was
created, just in reverse.

Rules to follow while populating:

- **One entry block per array item.** For each repeatable section (work, education, skills,
  projects, awards, certificates, publications, languages, interests, references,
  volunteer), use the template's example `.entry`/`.entry-card` block as the markup pattern
  and repeat it once per item in the corresponding JSON array — not just for however many
  example blocks the template happened to show.
- **Drop empty sections entirely.** If the resume JSON has no data for a section (missing or
  empty array, e.g. no `projects`), delete that whole `<section>` rather than leaving
  placeholder content in it.
- **No leftover `[bracket]` placeholders.** Every bracket placeholder in the final HTML must
  be replaced with real data or have its containing element (line/`<li>`/field) removed. Do
  the same for optional single fields with no data (e.g. `basics.url`, `basics.phone`).
- **Dates**: format as the template implies (e.g. `Jan 2022`), and use "Present" for a
  `work`/`volunteer` entry with no `endDate`.
- **Duration** (only if the theme's date markup has a dedicated duration element, e.g.
  `.date-duration` in `industrial-engineer`): compute it from `startDate`/`endDate` — using
  today's date when `endDate` is absent — with inclusive month counting:
  `months = (endYear*12 + endMonth) - (startYear*12 + startMonth) + 1`, then
  `years = months // 12`, `remainder = months % 12`. Format as `"X yrs Y mos"`, dropping
  whichever part is zero (`"X yrs"` or `"Y mos"` alone), and singularize the unit when it
  equals 1 (`"1 yr"`, `"1 mo"`).
- **Escape HTML**: escape `&`, `<`, `>` in every inserted text value.
- **Long text fields** (`basics.summary`, `work[].summary`): use judgment to fit the
  template's structure — e.g. split into an intro sentence plus a bullet list if the source
  text has embedded bullet markers, or split into short paragraphs on sentence boundaries.
  Don't invent new CSS classes; only use classes already defined in the theme's `style.css`.
- **Skills grouping**: if the template groups skills under category headings and the JSON
  data has real groupings (via `skills[].name` as category + `keywords`), use those; if the
  data is a flat list (just `skills[].name`), put them under one sensible heading rather than
  inventing categories the data doesn't support.
- **Photo**: only fill an avatar/photo placeholder if the theme's `index.html` has one (e.g.
  `even`'s `<div class="avatar" aria-hidden="true">[Photo]</div>`) *and* `basics.image` is
  set — if either is missing, remove the photo element rather than leaving a placeholder
  (e.g. `californian-warm` has no avatar element at all, so photos never apply there). When
  both are present, resolve `basics.image`: a local path relative to the resume JSON's
  directory (this repo's `resume.json` sets it to `profile_photo.jpg` at the repo root), or
  download it first if it's a URL.

  Before referencing it, downscale it to a print-appropriate size rather than embedding the
  source file as-is — camera-original photos (multi-megapixel, several MB) get baked into
  the PDF at full resolution otherwise, since Chromium's print-to-PDF doesn't downsample
  based on how small the avatar is actually rendered (a 150×150 CSS px circle in most
  themes), and that alone can bloat a several-page PDF from a few hundred KB to 8+ MB. Resize
  so the longer edge is ~600px (roughly 2-4x the avatar's CSS display size, plenty for a
  crisp circular crop) using `sips` (built into macOS, no extra dependency):
  `sips -Z 600 <resolved-source> --out <scratchpad-dir>/<name>-avatar.jpg`. Save the resized
  copy next to the populated HTML (a build artifact, not something to commit) and use *that*
  file's path for `src`, not the original.

  Replace the placeholder element with an `<img>` using the same class (so the existing
  avatar circle sizing/`border-radius`/`object-fit: cover` styling applies) and an absolute
  filesystem path or `file://` URI for `src`, e.g.:
  `<img class="avatar" src="/path/to/scratchpad/petr-koutny-avatar.jpg" alt="Petr Koutný">`.
  A non-square photo will be center-cropped by `object-fit: cover`; if the default crop cuts
  off the subject awkwardly, add an inline `style="object-position: 50% 20%"` (tuned by eye)
  rather than editing the theme's shared CSS.
- **Stylesheet link**: keep the `<link rel="stylesheet" href="style.css">` tag but rewrite
  `href` to the theme's absolute path (e.g.
  `file:///Volumes/Sources/petrkoutnycz/claude-cv-generator/themes/<theme>/style.css`) since
  the populated HTML file won't live inside `themes/<theme>/`.

Save the populated HTML to the session's scratchpad directory (or another temp location) —
it's an intermediate build artifact, not something to commit.

### 3. Sanity check

Skim the written HTML file for leftover `[bracket]` text, and confirm section/entry counts
match the JSON array lengths (e.g. same number of `.entry` blocks under Experience as
`work` items).

### 4. Render to PDF

This skill's `scripts/` folder is self-contained with its own Puppeteer install. If
`.claude/skills/jsonresume-pdf/scripts/node_modules` doesn't exist yet (first run), install it
once:

```bash
cd .claude/skills/jsonresume-pdf/scripts && npm install
```

Then render, from the repo root (creating `temp/` first if needed):

```bash
mkdir -p temp
node .claude/skills/jsonresume-pdf/scripts/html_to_pdf.js <path-to-populated-html> temp/<slugified-name>-<theme>.pdf
```

This launches headless Chromium, loads the HTML by `file://` URL, and prints it to A4 with
`printBackground: true`, 15 mm top/bottom page margins (so content clears the paper edge on
every page, including interior page breaks), and zero left/right margins — each theme owns
its horizontal gutter via the print-mode `.resume` padding.

### 5. Report

Tell the user the output PDF path. If the resume JSON has more/less content than a theme
was designed around (e.g. a very long `work` history), mention if the PDF ran long/short so
they can decide whether to trim the source data.

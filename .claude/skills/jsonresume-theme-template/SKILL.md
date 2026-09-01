---
name: jsonresume-theme-template
description: Create a static HTML/CSS resume template visually inspired by a named theme from the JSON Resume registry (jsonresume.org/themes), without installing the theme's npm package. Use when the user asks to create/add/generate a new resume theme or template based on a specific JSON Resume registry theme by name.
---

# JSON Resume theme → template

Produces a standalone, static HTML/CSS resume template that captures the *visual feel*
of a theme published on the [JSON Resume registry](https://jsonresume.org/themes) —
palette, typography, spacing, card/section styling — as an **original implementation**,
not a copy of the theme's code, and without ever running `npm install` on it.

Argument: the theme name as it appears on jsonresume.org/themes (e.g. `elegant`,
`kendall`, `stackoverflow`, `even`).

## Output

Two files, matching this repo's established theme-template pattern (see
[themes/californian-warm/](../../../themes/californian-warm/) for the reference
example):

- `themes/<theme-name>/index.html`
- `themes/<theme-name>/style.css`

Use the theme name itself (lowercase, hyphenated) as the folder name.

## Process

### 1. Gather visual reference material — no install

Run the helper script, which resolves the theme name to its npm package
(`jsonresume-theme-<name>`) and pulls reference material via plain HTTP (npm registry
metadata + the unpkg CDN) — it never runs `npm install` or executes any package code:

```bash
python3 .claude/skills/jsonresume-theme-template/scripts/fetch_theme_reference.py <theme-name> \
  --out <scratchpad>/theme-ref-<theme-name>
```

Use the session's scratchpad directory for `--out` if one is available. This downloads:

- the package README
- any screenshot/preview images it links to, into `<out>/screenshots/`
- a filtered list of the package's style files (`.css`/`.less`/`.scss`) and template
  files (`.hbs`/`.pug`/`.html`/...), as ready-to-fetch unpkg URLs

Some themes (especially newer ones built with esbuild/vite/rollup) don't publish raw
style/template files at all — everything is bundled into one JS file, with CSS inlined
as a string. When `style_files`/`template_files` come back empty, the script instead
returns `bundle_files` (the package's `main`/`module`/`unpkg`/`browser` entry points).
`curl` those and grep the text for `--color-*`/custom-property declarations, `font`,
`grid-template-columns`, `border-radius`, and hex colors — bundlers keep these as
recognizable literal strings even after minification. Also check the README: some
themes document their default color palette directly (e.g. as a JSON snippet).

If the script can't find a matching npm package (theme names on the listing page don't
always map 1:1 to `jsonresume-theme-<name>`), check https://jsonresume.org/themes for
the theme's card and its "Preview theme" link — the `?theme=` query value there is the
canonical slug — then re-run with `--package <exact-npm-name>`.

### 2. Study the reference material

- **View every downloaded screenshot** with your image-reading tool. This is the most
  reliable signal for layout (single column vs. sidebar vs. timeline), color palette,
  card/border treatment, and iconography — far better than trying to infer it from
  rendered-then-markdown-converted HTML, which loses all CSS.
- **Read a handful of the listed style files** (`curl` the unpkg URLs) as plain text to
  pin down exact colors, font-family choices, spacing scale, and border-radius/shadow
  conventions. Skim rather than read every file — a `theme.css`/`theme.less`/`base.less`
  plus one or two section-specific stylesheets is usually enough.
- Optionally skim a template file (`.pug`/`.hbs`) to see section ordering and structure,
  but the HTML you write should be your own markup, not a translation of theirs.
- If a screenshot shows a real person's photo, name, or contact details (common — many
  theme READMEs use the author's own resume as the demo), that's fine to *look at* for
  layout/color reference, but never copy that person's identifying details into the
  output template.

### 3. Write an original implementation

Build `themes/<theme-name>/index.html` + `themes/<theme-name>/style.css` following the
conventions already established in this repo (see the californian-warm example):

- **Static and self-contained** — plain HTML/CSS, no Handlebars/Mustache/template
  tokens, no build step, no JS framework. It must open directly in a browser.
- **Generic bracket placeholders** everywhere real content would go — `[Full Name]`,
  `[Job Title]`, `[Company Name]`, `[email@example.com]`, etc. Never fill in invented
  realistic-looking personal data, and never copy identifying details spotted in a
  reference screenshot.
- **Cover the JSON Resume schema sections** — header/basics (name, title, summary,
  email, phone, website, location, profiles), work, education, skills, projects, awards,
  certificates, publications, languages, interests, volunteer — but weight
  and style them the way the source theme does. A sidebar theme should get a sidebar; a
  single-column card theme should stay single-column; a timeline theme should render a
  timeline. Match its visual identity, not just its section list.
- **CSS in the separate `style.css`**, with a short header comment naming which JSON
  Resume registry theme inspired it and noting this is an original implementation (no
  code copied from the source package) — mirror the comment style already at the top of
  `themes/californian-warm/style.css`.
- **Matching web font**: if the reference uses a distinctive typeface, pull the closest
  Google Fonts equivalent via a `<link>` tag (same pattern as the existing example).
- **Responsive + print**: include a mobile breakpoint and a `@media print` block, same
  as the existing example. In the print block, the top-level `.resume` wrapper should
  carry only horizontal padding — the PDF renderer supplies the top/bottom page margins
  on every page, so re-adding a large `.resume` top padding just makes page 1 sit lower
  than the pages after it.

### 4. Sanity check

Open `themes/<theme-name>/index.html` in a browser (or otherwise visually verify) to
confirm it renders as a coherent, readable resume before considering the task done.

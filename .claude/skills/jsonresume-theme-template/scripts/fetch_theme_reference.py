#!/usr/bin/env python3
"""Gather visual reference material for a JSON Resume registry theme, without installing it.

Resolves a theme name to its npm package (jsonresume-theme-<slug>), then pulls:
  - npm registry metadata (version, repo, homepage)
  - the package README (for context + embedded screenshot links)
  - any screenshot/preview images referenced in the README
  - the list of style/template files inside the published package (via unpkg)

Nothing is installed and no package code is executed - everything is a plain HTTP GET
against the public npm registry / unpkg CDN, purely for the calling agent to read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

NPM_REGISTRY = "https://registry.npmjs.org"
UNPKG = "https://unpkg.com"
USER_AGENT = "jsonresume-theme-template-skill (+https://jsonresume.org/themes)"
STYLE_EXTS = (".css", ".scss", ".sass", ".less")
TEMPLATE_EXTS = (".hbs", ".html", ".htm", ".ejs", ".pug", ".njk", ".mustache")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
MAX_IMAGES = 6
MAX_LISTED_FILES = 20
NOISE_PATH_MARKERS = ("/lib/", "/node_modules/", "demo-files", "/icomoon/")
BADGE_URL_MARKERS = (
    "shields.io", "badge.fury.io", "travis-ci.", "circleci.com", "coveralls.io",
    "codecov.io", "badge.svg", "workflow/status", "netlify.com", "librariesio",
    "github.com/sponsors", "opencollective.com",
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def resolve_package(theme_name: str, explicit_package: str | None):
    if explicit_package:
        candidates = [explicit_package]
    else:
        slug = slugify(theme_name)
        candidates = [f"jsonresume-theme-{slug}"]

    for pkg in candidates:
        try:
            meta = fetch_json(f"{NPM_REGISTRY}/{pkg}")
            return pkg, meta
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    tried = ", ".join(candidates)
    raise SystemExit(
        f"Could not find an npm package for theme '{theme_name}' (tried: {tried}).\n"
        "Check https://jsonresume.org/themes for the exact theme slug used in its "
        "'?theme=' preview link, then re-run with --package <exact-npm-package-name>."
    )


def repo_url_of(meta: dict) -> str | None:
    repo = meta.get("repository")
    if isinstance(repo, dict):
        repo = repo.get("url")
    if not repo:
        return None
    repo = re.sub(r"^git\+", "", repo)
    repo = re.sub(r"\.git$", "", repo)
    repo = repo.replace("git://", "https://")
    return repo


def find_image_urls(readme_text: str, pkg: str, version: str, repo_url: str | None):
    urls = []
    for _alt, src in re.findall(r"!\[([^\]]*)\]\(([^)\s]+)\)", readme_text):
        urls.append(src)
    for src in re.findall(r'src="([^"]+)"', readme_text):
        urls.append(src)

    resolved = []
    for u in urls:
        if not u.lower().endswith(IMAGE_EXTS):
            continue
        if any(marker in u.lower() for marker in BADGE_URL_MARKERS):
            continue
        if u.startswith("http://") or u.startswith("https://"):
            resolved.append(u)
        else:
            base = f"{UNPKG}/{pkg}@{version}/"
            resolved.append(urljoin(base, u))

    seen = set()
    deduped = []
    for u in resolved:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped[:MAX_IMAGES]


def list_package_files(pkg: str, version: str):
    try:
        meta = fetch_json(f"{UNPKG}/{pkg}@{version}/?meta")
    except (urllib.error.HTTPError, urllib.error.URLError):
        return []

    return [f["path"] for f in meta.get("files", []) if "path" in f]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("theme_name", help="Theme name as listed on jsonresume.org/themes, e.g. 'elegant'")
    parser.add_argument("--package", help="Exact npm package name, if it doesn't match jsonresume-theme-<slug>")
    parser.add_argument("--out", help="Directory to write reference material into (default: a temp dir)")
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="jsonresume-theme-ref-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    shots_dir = out_dir / "screenshots"

    pkg, meta = resolve_package(args.theme_name, args.package)
    version = meta.get("dist-tags", {}).get("latest", "")
    version_meta = meta.get("versions", {}).get(version, {})
    repo_url = repo_url_of(meta)
    homepage = meta.get("homepage") or version_meta.get("homepage")
    description = meta.get("description") or version_meta.get("description")

    readme_path = None
    image_paths = []
    try:
        readme_bytes = fetch_bytes(f"{UNPKG}/{pkg}@{version}/README.md")
        readme_text = readme_bytes.decode("utf-8", errors="replace")
        readme_path = out_dir / "README.md"
        readme_path.write_text(readme_text, encoding="utf-8")

        for img_url in find_image_urls(readme_text, pkg, version, repo_url):
            try:
                data = fetch_bytes(img_url)
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue
            shots_dir.mkdir(exist_ok=True)
            fname = re.sub(r"[^A-Za-z0-9._-]", "_", img_url.split("/")[-1]) or "image"
            fpath = shots_dir / fname
            if fpath.exists():
                fpath = shots_dir / f"{len(image_paths)}-{fname}"
            fpath.write_bytes(data)
            image_paths.append(str(fpath))
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass

    all_files = [f for f in list_package_files(pkg, version) if not any(m in f for m in NOISE_PATH_MARKERS)]
    all_files.sort(key=len)
    style_files = [f for f in all_files if f.lower().endswith(STYLE_EXTS)][:MAX_LISTED_FILES]
    template_files = [f for f in all_files if f.lower().endswith(TEMPLATE_EXTS)][:MAX_LISTED_FILES]

    bundle_files = []
    note = (
        "Nothing was installed. Open the screenshots with your image-reading tool, "
        "and curl any of the style/template file URLs above to read their source as "
        "plain text for color/typography/layout reference."
    )
    if not style_files and not template_files:
        # Modern themes are often published pre-bundled (esbuild/vite/rollup), with
        # CSS inlined into a JS template-literal string rather than shipped as raw
        # .css/.hbs files. Fall back to the package's declared entry points so the
        # agent can grep the bundle text for CSS custom properties, colors, grid
        # templates, font stacks, etc.
        for field in ("unpkg", "browser", "main", "module"):
            entry = version_meta.get(field)
            if isinstance(entry, str):
                bundle_files.append(f"{UNPKG}/{pkg}@{version}/{entry.lstrip('./')}")
        bundle_files = list(dict.fromkeys(bundle_files))
        if bundle_files:
            note = (
                "Nothing was installed. No raw style/template files were published for "
                "this package - it ships pre-bundled. Fetch the URLs in bundle_files "
                "and grep the text for CSS custom properties (--color-*, --scale-*), "
                "font-family, grid-template-columns, border-radius, etc. Also open any "
                "downloaded screenshots, and check the README for a documented default "
                "color palette (some themes list one explicitly)."
            )

    summary = {
        "theme_name": args.theme_name,
        "npm_package": pkg,
        "version": version,
        "description": description,
        "repository": repo_url,
        "homepage": homepage,
        "reference_dir": str(out_dir),
        "readme_path": str(readme_path) if readme_path else None,
        "downloaded_screenshots": image_paths,
        "style_files": [f"{UNPKG}/{pkg}@{version}{f}" for f in style_files],
        "template_files": [f"{UNPKG}/{pkg}@{version}{f}" for f in template_files],
        "bundle_files": bundle_files,
        "note": note,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

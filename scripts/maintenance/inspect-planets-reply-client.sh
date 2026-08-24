#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BASE_URL="${PLANETS_BASE_URL:-https://planets.nu/}"
LOG_DIR="$ROOT_DIR/logs/maintenance"
STAMP="$(date '+%Y%m%d-%H%M%S')"
WORK_DIR="$LOG_DIR/${STAMP}-planets-reply-client"
mkdir -p "$WORK_DIR"

python3 - "$BASE_URL" "$WORK_DIR" <<'PY'
from __future__ import annotations

import gzip
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

base_url = sys.argv[1]
work_dir = Path(sys.argv[2])
assets_dir = work_dir / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


def fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/javascript,text/javascript,*/*;q=0.8",
            "Accept-Encoding": "gzip",
        },
    )
    with urlopen(request, timeout=20) as response:
        data = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
        return data


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs}
        if tag.lower() == "script" and values.get("src"):
            self.urls.append(values["src"] or "")
        if tag.lower() == "link" and values.get("href"):
            rel = (values.get("rel") or "").lower()
            href = values["href"] or ""
            if "modulepreload" in rel or href.split("?", 1)[0].endswith((".js", ".mjs")):
                self.urls.append(href)


print(f"===== FETCH PLANETS.NU CLIENT =====")
print(f"base={base_url}")
try:
    html_bytes = fetch(base_url)
except (HTTPError, URLError, TimeoutError) as exc:
    raise SystemExit(f"failed to fetch {base_url}: {exc}")

html_text = html_bytes.decode("utf-8", errors="replace")
(work_dir / "index.html").write_text(html_text, encoding="utf-8")

parser = ScriptParser()
parser.feed(html_text)

base_host = urlparse(base_url).netloc
queue: list[str] = []
seen_urls: set[str] = set()
for value in parser.urls:
    absolute = urljoin(base_url, value)
    if urlparse(absolute).netloc == base_host:
        queue.append(absolute)

# Also capture obvious JS references embedded in bootstrapping HTML.
for match in re.finditer(r"[\"']([^\"']+?\.(?:js|mjs)(?:\?[^\"']*)?)[\"']", html_text, re.I):
    absolute = urljoin(base_url, match.group(1))
    if urlparse(absolute).netloc == base_host:
        queue.append(absolute)

manifest: list[dict[str, object]] = []
texts: list[tuple[str, str]] = [("index.html", html_text)]
max_assets = 120

# Common minified-bundle forms for lazy chunks and dynamic imports.
js_ref_patterns = [
    re.compile(r"[\"']([^\"']+?\.(?:js|mjs)(?:\?[^\"']*)?)[\"']", re.I),
    re.compile(r"import\(\s*[\"']([^\"']+)[\"']\s*\)", re.I),
]

while queue and len(seen_urls) < max_assets:
    url = queue.pop(0)
    if url in seen_urls:
        continue
    seen_urls.add(url)
    try:
        raw = fetch(url)
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:  # diagnostic: keep crawling other chunks
        manifest.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        continue

    index = len(texts)
    name = f"asset-{index:03d}.js"
    (assets_dir / name).write_text(text, encoding="utf-8")
    texts.append((name, text))
    manifest.append({"url": url, "file": name, "bytes": len(raw)})

    base_for_asset = url
    for pattern in js_ref_patterns:
        for match in pattern.finditer(text):
            ref = match.group(1)
            # Ignore data/blob URLs and obvious non-JS resource strings.
            if ref.startswith(("data:", "blob:")):
                continue
            if ".js" not in ref and ".mjs" not in ref:
                continue
            absolute = urljoin(base_for_asset, ref)
            if urlparse(absolute).netloc == base_host and absolute not in seen_urls:
                queue.append(absolute)

(work_dir / "manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print(f"downloaded_assets={len(texts) - 1}")
print(f"saved={work_dir}")

patterns = [
    ("account/post", re.compile(r"account/post", re.I)),
    ("game/sendmessage", re.compile(r"game/sendmessage", re.I)),
    ("account/thread", re.compile(r"account/thread", re.I)),
    ("parentid", re.compile(r"parentid", re.I)),
    ("parent_id", re.compile(r"parent_id", re.I)),
    ("replycount", re.compile(r"replycount", re.I)),
    ("_replies", re.compile(r"_replies", re.I)),
    ("replyto", re.compile(r"replyto", re.I)),
    ("activityid", re.compile(r"activityid", re.I)),
    ("privateactivity", re.compile(r"privateactivity", re.I)),
]

results_file = work_dir / "matches.txt"
printed: set[tuple[str, int, str]] = set()
result_lines: list[str] = []
max_matches_per_pattern = 20
context_chars = 700

for label, pattern in patterns:
    result_lines.append(f"\n===== {label} =====")
    count = 0
    for filename, text in texts:
        for match in pattern.finditer(text):
            if count >= max_matches_per_pattern:
                break
            # Collapse whitespace so minified and formatted bundles are both readable.
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            key = (filename, match.start() // 200, label)
            if key in printed:
                continue
            printed.add(key)
            count += 1
            result_lines.append(f"[{filename} offset={match.start()}]")
            result_lines.append(snippet)
        if count >= max_matches_per_pattern:
            break
    if count == 0:
        result_lines.append("(no matches)")

results = "\n".join(result_lines) + "\n"
results_file.write_text(results, encoding="utf-8")
print(results)
print("===== SUMMARY =====")
print(f"full_matches={results_file}")
print(f"manifest={work_dir / 'manifest.json'}")
print("No authentication or API key is used by this inspector.")
PY

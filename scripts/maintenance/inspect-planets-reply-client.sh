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
pages_dir = work_dir / "pages"
assets_dir.mkdir(parents=True, exist_ok=True)
pages_dir.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


def is_planets_host(host):
    host = (host or "").split(":", 1)[0].lower()
    return host == "planets.nu" or host.endswith(".planets.nu")


def fetch(url):
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
        return {
            "data": data,
            "final_url": response.geturl(),
            "content_type": response.headers.get("Content-Type", ""),
            "status": getattr(response, "status", 200),
        }


class AssetParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = {key.lower(): value for key, value in attrs}
        tag = tag.lower()
        if tag == "script" and values.get("src"):
            self.urls.append(values["src"] or "")
        if tag == "link" and values.get("href"):
            rel = (values.get("rel") or "").lower()
            href = values["href"] or ""
            if (
                "modulepreload" in rel
                or "preload" in rel
                or href.split("?", 1)[0].lower().endswith((".js", ".mjs"))
            ):
                self.urls.append(href)


entry_urls = []
for candidate in (
    base_url,
    "https://planets.nu/",
    "https://play.planets.nu/",
    "https://mobile.planets.nu/",
):
    if candidate not in entry_urls:
        entry_urls.append(candidate)

manifest = []
texts = []
queue = []
seen_urls = set()
page_count = 0

print("===== FETCH PLANETS.NU CLIENT =====")
print("entry_points={}".format(", ".join(entry_urls)))

for entry_url in entry_urls:
    try:
        response = fetch(entry_url)
    except Exception as exc:
        manifest.append({
            "kind": "entry",
            "url": entry_url,
            "error": "{}: {}".format(type(exc).__name__, exc),
        })
        print("entry FAIL {} -> {}: {}".format(entry_url, type(exc).__name__, exc))
        continue

    page_count += 1
    html_text = response["data"].decode("utf-8", errors="replace")
    page_name = "entry-{:02d}.html".format(page_count)
    (pages_dir / page_name).write_text(html_text, encoding="utf-8")
    texts.append((page_name, html_text, response["final_url"]))
    manifest.append({
        "kind": "entry",
        "url": entry_url,
        "final_url": response["final_url"],
        "file": "pages/{}".format(page_name),
        "bytes": len(response["data"]),
        "content_type": response["content_type"],
        "status": response["status"],
    })
    print(
        "entry OK   {} -> {} bytes={} type={}".format(
            entry_url,
            response["final_url"],
            len(response["data"]),
            response["content_type"] or "<unknown>",
        )
    )

    parser = AssetParser()
    parser.feed(html_text)
    refs = list(parser.urls)
    for match in re.finditer(
        r"[\"']([^\"']+?\.(?:js|mjs)(?:\?[^\"']*)?)[\"']",
        html_text,
        re.I,
    ):
        refs.append(match.group(1))

    for ref in refs:
        if ref.startswith(("data:", "blob:", "javascript:")):
            continue
        absolute = urljoin(response["final_url"], ref)
        if is_planets_host(urlparse(absolute).netloc) and absolute not in seen_urls:
            queue.append(absolute)

# The classic Nu client has historically exposed nu.js directly or under a js/
# prefix on different Planets.nu frontends. Probe a small explicit set so the
# inspector remains useful even when the landing HTML bootstraps the client via
# redirects, frames, service workers or dynamically generated markup.
legacy_paths = (
    "nu.js",
    "nu.min.js",
    "js/nu.js",
    "js/nu.min.js",
    "scripts/nu.js",
    "client/nu.js",
)
legacy_bases = (
    "https://planets.nu/",
    "https://play.planets.nu/",
    "https://mobile.planets.nu/",
)
legacy_candidates = []
for legacy_base in legacy_bases:
    for path in legacy_paths:
        legacy_candidates.append(urljoin(legacy_base, path))

# Crawl discovered JavaScript references first, then explicit legacy probes.
for candidate in legacy_candidates:
    if candidate not in queue:
        queue.append(candidate)

max_assets = 160
js_ref_patterns = [
    re.compile(r"[\"']([^\"']+?\.(?:js|mjs)(?:\?[^\"']*)?)[\"']", re.I),
    re.compile(r"import\(\s*[\"']([^\"']+)[\"']\s*\)", re.I),
]

legacy_hits = []
asset_count = 0
while queue and len(seen_urls) < max_assets:
    url = queue.pop(0)
    if url in seen_urls:
        continue
    seen_urls.add(url)

    try:
        response = fetch(url)
        text = response["data"].decode("utf-8", errors="replace")
    except Exception as exc:
        manifest.append({
            "kind": "asset",
            "url": url,
            "error": "{}: {}".format(type(exc).__name__, exc),
        })
        continue

    asset_count += 1
    name = "asset-{:03d}.js".format(asset_count)
    (assets_dir / name).write_text(text, encoding="utf-8")
    texts.append((name, text, response["final_url"]))
    is_legacy = url in legacy_candidates
    if is_legacy:
        legacy_hits.append((url, response["final_url"], len(response["data"])))
    manifest.append({
        "kind": "asset",
        "url": url,
        "final_url": response["final_url"],
        "file": "assets/{}".format(name),
        "bytes": len(response["data"]),
        "content_type": response["content_type"],
        "status": response["status"],
        "legacy_probe": is_legacy,
    })

    for pattern in js_ref_patterns:
        for match in pattern.finditer(text):
            ref = match.group(1)
            if ref.startswith(("data:", "blob:", "javascript:")):
                continue
            if ".js" not in ref.lower() and ".mjs" not in ref.lower():
                continue
            absolute = urljoin(response["final_url"], ref)
            if (
                is_planets_host(urlparse(absolute).netloc)
                and absolute not in seen_urls
                and absolute not in queue
            ):
                queue.append(absolute)

(work_dir / "manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("downloaded_pages={}".format(page_count))
print("downloaded_assets={}".format(asset_count))
print("saved={}".format(work_dir))
print("\n===== LEGACY CLIENT PROBES =====")
if legacy_hits:
    for original, final_url, size in legacy_hits:
        print("HIT  {} -> {} bytes={}".format(original, final_url, size))
else:
    print("No explicit legacy nu.js candidate returned successfully.")

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
    ("ingameactivity", re.compile(r"ingameactivity", re.I)),
    ("privatemessage", re.compile(r"privatemessage", re.I)),
]

results_file = work_dir / "matches.txt"
printed = set()
result_lines = []
max_matches_per_pattern = 20
context_chars = 900

for label, pattern in patterns:
    result_lines.append("\n===== {} =====".format(label))
    count = 0
    for filename, text, source_url in texts:
        for match in pattern.finditer(text):
            if count >= max_matches_per_pattern:
                break
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            key = (filename, match.start() // 250, label)
            if key in printed:
                continue
            printed.add(key)
            count += 1
            result_lines.append(
                "[{} source={} offset={}]".format(filename, source_url, match.start())
            )
            result_lines.append(snippet)
        if count >= max_matches_per_pattern:
            break
    if count == 0:
        result_lines.append("(no matches)")

results = "\n".join(result_lines) + "\n"
results_file.write_text(results, encoding="utf-8")
print(results)
print("===== SUMMARY =====")
print("full_matches={}".format(results_file))
print("manifest={}".format(work_dir / "manifest.json"))
print("No authentication or API key is used by this inspector.")
PY

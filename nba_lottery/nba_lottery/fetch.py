"""Fetch raw lottery data from Wikipedia and store in data/raw/.

We use the Wikipedia Parse API to pull structured wikitext for each
`{year}_NBA_draft` page. Each raw payload is stored immutably in
`data/raw/wiki/{year}_NBA_draft.wikitext` with a `.meta.json` sidecar
recording URL, fetch timestamp, and SHA-256.

Why Wikipedia: the {year}_NBA_draft pages carry a well-structured lottery
table that lists participants, their season record, lottery chances
(integer combinations), the full probability matrix per pick position, the
actual lottery result, and conditional-protection footnotes for traded
picks. Every fact in the table cites primary sources (NBA.com, official
press releases) via inline <ref>s, which we preserve via `source_audit.csv`.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


USER_AGENT = (
    "nba_lottery-research/0.1 (non-commercial research; "
    "contact: github.com/davevanveen)"
)

WIKI_API = "https://en.wikipedia.org/w/api.php"


def _wiki_parse(page_title: str, max_retries: int = 5) -> dict:
    """Call the Wikipedia parse API for a page's wikitext.

    Retries with exponential backoff on HTTP 429 (rate limiting).
    """
    params = {
        "action": "parse",
        "page": page_title,
        "format": "json",
        "prop": "wikitext|revid",
        "formatversion": "2",
        "redirects": "1",
    }
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                # Honor Retry-After if present, else exponential backoff
                retry_after = e.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 2.0 * (2 ** attempt)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Failed after {max_retries} retries: {last_err}")


def fetch_year(year: int, raw_dir: Path) -> Path:
    """Fetch the {year}_NBA_draft wikitext, write to raw_dir with meta sidecar.

    Returns the path to the wikitext file. Idempotent: if the file already
    exists and the sidecar is valid, skips the network call.
    """
    out_dir = raw_dir / "wiki"
    out_dir.mkdir(parents=True, exist_ok=True)
    wikitext_path = out_dir / f"{year}_NBA_draft.wikitext"
    meta_path = out_dir / f"{year}_NBA_draft.wikitext.meta.json"

    if wikitext_path.exists() and meta_path.exists():
        return wikitext_path

    page_title = f"{year}_NBA_draft"
    result = _wiki_parse(page_title)
    if "error" in result:
        raise RuntimeError(
            f"Wikipedia parse API error for {page_title}: {result['error']}"
        )
    wikitext = result["parse"]["wikitext"]
    revid = result["parse"].get("revid")

    wikitext_bytes = wikitext.encode("utf-8")
    sha256 = hashlib.sha256(wikitext_bytes).hexdigest()

    wikitext_path.write_bytes(wikitext_bytes)
    meta = {
        "page_title": page_title,
        "url": f"https://en.wikipedia.org/wiki/{page_title}",
        "api_url": f"{WIKI_API}?action=parse&page={page_title}&format=json&prop=wikitext&formatversion=2&redirects=1",
        "fetch_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sha256": sha256,
        "revid": revid,
        "bytes": len(wikitext_bytes),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return wikitext_path


def fetch_years(years: list[int], raw_dir: Path, throttle_s: float = 1.5) -> list[Path]:
    """Fetch multiple years with polite throttling between uncached requests."""
    paths = []
    for i, y in enumerate(years):
        cached = (raw_dir / "wiki" / f"{y}_NBA_draft.wikitext").exists()
        if not cached and i > 0:
            time.sleep(throttle_s)
        paths.append(fetch_year(y, raw_dir))
    return paths

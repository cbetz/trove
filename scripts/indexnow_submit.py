"""Tell IndexNow search engines (Bing and others) which pages changed.

IndexNow is a push protocol: instead of waiting for a crawl, the site posts the
URLs that changed. Bing, Yandex, Naver, Seznam and Yep take part; Google does
not. Run it after a deploy, never before: the engines fetch the key file and
the URLs straight away.

The protocol needs a key file at the site root. On first run this script
creates one (``web/<key>.txt``) and stops, so it can be committed and deployed.
Run it again once the deploy is live.

Usage::

    uv run python scripts/indexnow_submit.py              # every URL in the sitemap
    uv run python scripts/indexnow_submit.py --since 2026-11-26   # only pages changed since
    uv run python scripts/indexnow_submit.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HOST = "troveproject.com"
WEB = Path("web")
SITEMAP = WEB / "sitemap.xml"
ENDPOINT = "https://api.indexnow.org/indexnow"
_KEY_FILE_RE = re.compile(r"[0-9a-f]{32}\.txt")
_URL_RE = re.compile(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>")


def find_key() -> str | None:
    for path in sorted(WEB.glob("*.txt")):
        if _KEY_FILE_RE.fullmatch(path.name) and path.read_text().strip() == path.stem:
            return path.stem
    return None


def changed_urls(since: str | None) -> list[str]:
    pairs = _URL_RE.findall(SITEMAP.read_text())
    return [loc for loc, lastmod in pairs if since is None or lastmod >= since]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", help="only URLs whose sitemap lastmod is on or after YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="print what would be sent")
    args = parser.parse_args()

    key = find_key()
    if key is None:
        key = secrets.token_hex(16)
        (WEB / f"{key}.txt").write_text(key + "\n")
        raise SystemExit(
            f"Created web/{key}.txt. Commit and deploy it, check that "
            f"https://{HOST}/{key}.txt returns the key, then run this again."
        )
    urls = changed_urls(args.since)
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"https://{HOST}/{key}.txt",
        "urlList": urls,
    }
    print(f"{len(urls)} URLs" + (f" changed since {args.since}" if args.since else ""))
    if args.dry_run or not urls:
        return
    req = Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            # 200 or 202 means the list was accepted; indexing is not guaranteed.
            print(f"IndexNow answered {resp.status}")
    except HTTPError as exc:
        if exc.code == 403:
            # Seen on the very first submission, seconds after the key file went
            # live: the same request succeeded a minute later.
            raise SystemExit(
                "IndexNow answered 403: it could not validate the key. Check that "
                f"https://{HOST}/{key}.txt returns the key, wait a minute and run this again."
            ) from exc
        raise SystemExit(f"IndexNow answered {exc.code}: {exc.reason}") from exc


if __name__ == "__main__":
    main()

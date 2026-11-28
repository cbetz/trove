"""Read the drugs@FDA application overview page.

The overview page (e.g. https://www.accessdata.fda.gov/scripts/cder/daf/
index.cfm?event=overview.process&ApplNo=218614) carries the sponsor's
name, the marketing status, and links to every approval-package
document for an application.

accessdata.fda.gov stopped serving these pages to this project's scraper in
November 2026, so by default only pages already in the local cache are read
and nothing is requested. openFDA's Drugs@FDA endpoint (``fda_sba.drugsfda``)
carries the same data and is what the index is refreshed from. Set
``TROVE_FDA_FETCH_PAGES=1`` to let this module request pages again.
"""

from __future__ import annotations

import os
import re
import time
import warnings
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd

OVERVIEW_URL_TEMPLATE = (
    "https://www.accessdata.fda.gov/scripts/cder/daf/"
    "index.cfm?event=overview.process&ApplNo={appl_no}"
)
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"

# Seconds to wait after each request to accessdata.fda.gov. FDA throttles
# clients that ask too fast: a run of a few hundred back-to-back requests got
# this project's address blocked ("excessive requests") in November 2026.
REQUEST_DELAY = 2.0


class FdaBlockedError(RuntimeError):
    """accessdata.fda.gov refused the request as abusive or excessive."""


class PageNotCachedError(RuntimeError):
    """The page is not in the local cache and requesting it is switched off."""


# Set once FDA refuses a request; every later fetch in the same run fails fast
# instead of sending more requests to a server that has asked us to stop.
_blocked_reason: str | None = None
# Applications whose page could not be fetched in this run, so the three
# enrichment passes do not each ask for it again.
_failed: dict[str, str] = {}
# accessdata.fda.gov also answers 404 for pages that exist when it does not
# accept the client. A run of these is a refusal, not a run of missing pages.
_consecutive_404 = 0
_MAX_CONSECUTIVE_404 = 3

# The overview page renders the sponsor as
#   <span class="prodBoldText">Company:</span> <span class="appl-details-top">{NAME} ...</span>
# The value cell is heavily padded with trailing whitespace.
_COMPANY_RE = re.compile(
    r'Company:\s*</span>\s*<span[^>]*class="appl-details-top"[^>]*>([^<]+)',
    re.I | re.S,
)


# Rows of the "Original Approvals or Tentative Approvals" table:
#   <td>11/17/2022</td> <td>ORIG-1</td> <td> Approval </td>
# "Tentative Approval" rows are deliberately not matched.
_ORIG_APPROVAL_RE = re.compile(
    r"<td>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*<td>\s*ORIG-\d+\s*</td>\s*<td>\s*Approval\s*</td>",
    re.I,
)


def fetch_application_overview(
    appl_no: str,
    cache_dir: Path | str = "data/raw/fda/overview",
    *,
    force: bool = False,
) -> Path:
    """Return the cached drugs@FDA overview HTML for ``appl_no``.

    A page that is not cached is requested only when the environment variable
    ``TROVE_FDA_FETCH_PAGES=1`` is set (and ``TROVE_FDA_OFFLINE`` is not);
    otherwise this raises ``PageNotCachedError``. When requesting, it waits
    ``REQUEST_DELAY`` seconds after each request and stops asking for the rest
    of the run once FDA refuses one (``FdaBlockedError``).
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{appl_no}.html"
    if target.exists() and not force:
        return target
    global _blocked_reason, _consecutive_404
    if os.environ.get("TROVE_FDA_OFFLINE") or not os.environ.get("TROVE_FDA_FETCH_PAGES"):
        raise PageNotCachedError(
            f"the drugs@FDA page for application {appl_no} is not cached and page requests "
            "are off (set TROVE_FDA_FETCH_PAGES=1 to allow them)"
        )
    if _blocked_reason:
        raise FdaBlockedError(_blocked_reason)
    if appl_no in _failed:
        raise RuntimeError(_failed[appl_no])
    url = OVERVIEW_URL_TEMPLATE.format(appl_no=appl_no)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read()
            final_url = resp.geturl()
    except HTTPError as exc:
        if exc.code in (403, 429):
            _blocked_reason = f"accessdata.fda.gov answered {exc.code} for application {appl_no}"
            raise FdaBlockedError(_blocked_reason) from exc
        _failed[appl_no] = f"accessdata.fda.gov answered {exc.code} for application {appl_no}"
        if exc.code == 404:
            _consecutive_404 += 1
            if _consecutive_404 >= _MAX_CONSECUTIVE_404:
                _blocked_reason = (
                    f"accessdata.fda.gov answered 404 for {_consecutive_404} applications in a "
                    "row; it does that when it does not accept the client"
                )
                raise FdaBlockedError(_blocked_reason) from exc
        raise
    finally:
        time.sleep(REQUEST_DELAY)
    _consecutive_404 = 0
    if "apology_objects" in final_url or b"apology_objects" in body[:2000]:
        _blocked_reason = f"accessdata.fda.gov served its apology page for application {appl_no}"
        raise FdaBlockedError(_blocked_reason)
    target.write_bytes(body)
    return target


def parse_sponsor(html_bytes: bytes) -> str | None:
    """Return the sponsor (Company) name from a drugs@FDA overview HTML.

    Falls back to None if the field can't be located.
    """
    if not html_bytes:
        return None
    text = html_bytes.decode("utf-8", errors="replace")
    m = _COMPANY_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Title-case is more readable than the all-caps FDA stores. Apply only
    # when the value is fully uppercase; preserve mixed-case as-is.
    return _normalize(raw)


def parse_original_approval_date(html_bytes: bytes) -> date | None:
    """Return the original-approval action date from a drugs@FDA overview HTML.

    This is the action date of the ORIG approval submission — the date on the
    approval letter. ``None`` when the page has no such row (e.g. the
    application has since been withdrawn and dropped from drugs@FDA).
    """
    if not html_bytes:
        return None
    text = html_bytes.decode("utf-8", errors="replace")
    dates = []
    for m in _ORIG_APPROVAL_RE.finditer(text):
        try:
            dates.append(datetime.strptime(m.group(1), "%m/%d/%Y").date())
        except ValueError:
            continue
    return min(dates) if dates else None


# The "Original Approvals or Tentative Approvals" table, one <tr> per submission:
#   Action Date | Submission | Action Type | Submission Classification |
#   Review Priority; Orphan Status | Letters, Reviews, Labels | Notes | Url
_ORIG_TABLE_RE = re.compile(r'id="exampleApplOrig".*?</table>', re.S)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_DOC_LINK_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*title="Links to (Label|Letter|Review)"', re.I)


def _cell_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def parse_original_approval_documents(html_bytes: bytes) -> dict[str, str | None]:
    """Return the documents FDA posted for an application's original approval.

    Reads the first ``ORIG`` submission whose action type is ``Approval`` from
    the drugs@FDA overview page and returns ``approval_letter_url``,
    ``review_url`` (the approval package: FDA's review documents),
    ``label_url`` (the label approved with the original approval) and
    ``submission_classification`` (e.g. ``Type 1 - New Molecular Entity``;
    blank for BLAs). Every value is ``None`` when the page has no such row.
    """
    out: dict[str, str | None] = {
        "approval_letter_url": None,
        "review_url": None,
        "label_url": None,
        "submission_classification": None,
    }
    if not html_bytes:
        return out
    table = _ORIG_TABLE_RE.search(html_bytes.decode("utf-8", errors="replace"))
    if not table:
        return out
    candidates = []
    for tr in _TR_RE.finditer(table.group(0)):
        cells = _TD_RE.findall(tr.group(1))
        if len(cells) < 6:
            continue
        submission = re.fullmatch(r"ORIG-(\d+)", _cell_text(cells[1]))
        if not submission or _cell_text(cells[2]) != "Approval":
            continue
        candidates.append((int(submission.group(1)), cells))
    if not candidates:
        return out
    _, cells = min(candidates, key=lambda c: c[0])
    links = {kind.lower(): url for url, kind in _DOC_LINK_RE.findall(cells[5])}
    out["approval_letter_url"] = links.get("letter")
    out["review_url"] = links.get("review")
    out["label_url"] = links.get("label")
    out["submission_classification"] = _cell_text(cells[3]) or None
    return out


def enrich_with_approval_documents(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/overview",
) -> pd.DataFrame:
    """Add ``approval_letter_url``, ``review_url`` and ``submission_classification``.

    Also fills ``label_pdf_url`` from the original-approval row when FDA's
    annual list linked the drug name to the drugs@FDA overview instead of to a
    label PDF. A label link the list already carries is left alone. Uses the
    overview pages cached by ``enrich_with_sponsor``.
    """
    out = df.copy()
    cache = Path(cache_dir)
    letters: list[str | None] = []
    reviews: list[str | None] = []
    classes: list[str | None] = []
    labels = [v if isinstance(v, str) and v else None for v in out["label_pdf_url"].tolist()]
    for i, appl_no in enumerate(out["application_number"].fillna("").tolist()):
        docs = parse_original_approval_documents(b"")
        if appl_no:
            try:
                docs = parse_original_approval_documents(
                    fetch_application_overview(appl_no, cache).read_bytes()
                )
            except PageNotCachedError:
                pass  # openFDA's Drugs@FDA record supplies these rows
            except Exception as exc:  # noqa: BLE001
                warnings.warn(
                    f"{appl_no}: could not read the drugs@FDA overview ({exc!r}); "
                    "no approval documents recorded",
                    stacklevel=2,
                )
        letters.append(docs["approval_letter_url"])
        reviews.append(docs["review_url"])
        classes.append(docs["submission_classification"])
        if labels[i] is None:
            labels[i] = docs["label_url"]
    out["approval_letter_url"] = letters
    out["review_url"] = reviews
    out["submission_classification"] = classes
    out["label_pdf_url"] = labels
    return out


def reconcile_approval_dates(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/overview",
) -> pd.DataFrame:
    """Replace list-page approval dates with the drugs@FDA action date where they differ.

    FDA's annual Novel Drug Approvals page is hand-maintained and occasionally
    off by a day from the approval letter (Tzield is listed as 11/18/22; its
    approval letter and drugs@FDA both say November 17, 2022). drugs@FDA is
    FDA's system of record for the action date, so it wins. The list-page date
    is kept when drugs@FDA has no original-approval row, or when the two
    disagree about the *year* — that is too large a gap to resolve silently,
    so it is reported instead. Uses the overview pages already cached by
    ``enrich_with_sponsor``; makes no extra requests once that has run.
    """
    out = df.copy()
    cache = Path(cache_dir)
    dates = list(out["approval_date"])
    apps = out["application_number"].fillna("").tolist()
    names = out["drug_name"].tolist()
    for i, appl_no in enumerate(apps):
        if not appl_no:
            continue
        try:
            official = parse_original_approval_date(
                fetch_application_overview(appl_no, cache).read_bytes()
            )
        except Exception:  # noqa: BLE001
            continue
        if official is None or official == dates[i]:
            continue
        if official.year != dates[i].year:
            warnings.warn(
                f"{names[i]}: drugs@FDA original approval {official.isoformat()} and the "
                f"Novel Drug Approvals list ({dates[i].isoformat()}) disagree by year; "
                "keeping the list date",
                stacklevel=2,
            )
            continue
        dates[i] = official
    out["approval_date"] = dates
    return out


def enrich_with_sponsor(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/overview",
    *,
    progress: bool = True,
) -> pd.DataFrame:
    """Add a ``sponsor`` column to a DataFrame produced by ``build_index``.

    Skips rows without an ``application_number``. Caches the overview HTML
    per app number so re-runs are free after the first.
    """
    out = df.copy()
    sponsors: list[str | None] = []
    cache = Path(cache_dir)
    apps = out["application_number"].fillna("").tolist()
    for i, appl_no in enumerate(apps, start=1):
        if not appl_no:
            sponsors.append(None)
            continue
        if progress and i % 25 == 0:
            print(f"  sponsor enrichment: {i}/{len(apps)}", flush=True)
        try:
            page = fetch_application_overview(appl_no, cache)
            sponsors.append(parse_sponsor(page.read_bytes()))
        except PageNotCachedError:
            sponsors.append(None)
        except Exception as exc:  # noqa: BLE001
            if progress:
                print(f"    skip {appl_no}: {exc!r}")
            sponsors.append(None)
    out["sponsor"] = sponsors
    return out


def _normalize(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return name
    letters = [c for c in name if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        # Title-case all-caps names but keep recognized acronyms uppercase.
        keep_upper = {
            "INC",
            "LLC",
            "LTD",
            "LP",
            "LLP",
            "PLC",
            "USA",
            "AG",
            "SA",
            "SAS",
            "SPA",
            "BV",
            "GMBH",
            "CO",
            "CORP",
            "AB",
            "AS",
            "OY",
        }
        words = [w for w in re.split(r"\s+", name) if w]
        out = []
        for w in words:
            stripped = re.sub(r"[^A-Z]", "", w)
            if stripped in keep_upper:
                out.append(w)
            else:
                out.append(w[0] + w[1:].lower() if len(w) > 1 else w)
        return " ".join(out)
    return name

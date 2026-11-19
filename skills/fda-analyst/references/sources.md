# Data layout — FDA novel drug approvals index

## The bundle

- Parquet: `https://troveproject.com/data/fda_approvals_nme_recent.parquet`
- JSON: `https://troveproject.com/data/fda_approvals_nme_recent.json`

217 rows covering FDA novel drug approvals whose original approval falls in calendar years 2021–2024. Both regulatory centers are included: 192 CDER (NMEs + novel antibody BLAs from the annual *Novel Drug Approvals* pages) plus 25 CBER (cell and gene therapies from the *Approved Cellular and Gene Therapy Products* page). Approvals from 2025 onward are not in the bundle yet.

**If `troveproject.com` is unreachable** (sandboxes commonly block it — the symptom is a DNS or connection error, not an HTTP status), the same files are in the GitHub repo, which sandboxes normally allow:

```bash
git clone --depth 1 https://github.com/cbetz/trove
# trove/web/data/fda_approvals_nme_recent.json      (same JSON envelope as below)
# trove/web/data/fda_approvals_nme_recent.parquet
# trove/artifacts/fda_approvals_nme_recent.csv
```

## JSON envelope shape

The JSON is **not** a top-level array. It's an object:

```json
{
  "totals": {
    "drugs": 217,
    "year_min": 2021,
    "year_max": 2024,
    "by_year": {"2021": 54, "2022": 42, "2023": 62, "2024": 59}
  },
  "rows": [ /* one object per drug */ ]
}
```

When iterating, use `data["rows"]`, not `data` directly.

## Columns

| Column | Description |
|--------|-------------|
| `year` | Calendar year of approval |
| `drug_name` | FDA brand name |
| `active_ingredient` | International nonproprietary or USAN name |
| `sponsor` | Company that holds the application. CDER: parsed from drugs@FDA, title-cased from FDA's all-caps stored form. CBER: parsed from the per-product page's "Manufacturer" field. 216 of 217 rows populated. |
| `approval_date` | Date of the **original** approval, ISO `YYYY-MM-DD`, never null. CDER: the original-approval action date in drugs@FDA (the date on the approval letter), which occasionally differs by a day from FDA's annual list. CBER: the date of the original approval letter — not a later supplement letter. |
| `indication` | FDA-approved use string |
| `application_number` | NDA / BLA application number (6 digits). For CBER products this is the STN. |
| `application_type` | "NDA" or "BLA". CBER products are always BLA. |
| `label_pdf_url` | Direct link to the FDA-approved label PDF (CDER) or Package Insert (CBER). |
| `drugs_at_fda_url` | CDER: drugs@FDA application-overview URL. CBER: per-product FDA page under `fda.gov/vaccines-blood-biologics/` — that page is the canonical hub for the approval letter, package insert, clinical review memo, and Summary Basis for Regulatory Action. |
| `trials_snapshot_url` | Drug Trials Snapshot URL (CDER only; CBER doesn't publish Trials Snapshots — `null`) |
| `regulatory_center` | `"CDER"` or `"CBER"`. CDER = small molecules + most antibody biologics. CBER = cell and gene therapies. |

## Query patterns

DuckDB is the canonical query path, but **don't assume it's installed.** Many environments have only `curl` and `python3` stdlib. The fallback below is fully equivalent for lookup-style queries.

### With DuckDB (CLI or Python)

**Find a drug by name:**

```sql
SELECT * FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
WHERE LOWER(drug_name) LIKE '%hemophilia%'
   OR LOWER(active_ingredient) LIKE '%hemophilia%';
```

**Recent approvals in a therapeutic area:**

```sql
SELECT drug_name, active_ingredient, approval_date, indication
FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
WHERE LOWER(indication) LIKE '%cystic fibrosis%'
ORDER BY approval_date DESC;
```

### Without DuckDB (curl + python3 stdlib only)

Equally fast for the lookup queries this skill does most often. **Note the JSON envelope** — iterate `data["rows"]`, not `data`.

```bash
UA='trove-fda-analyst/1.0 (+https://troveproject.com)'
curl -sSfL -A "$UA" 'https://troveproject.com/data/fda_approvals_nme_recent.json' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
hits = [r for r in data['rows']
        if 'hemophilia' in (r.get('drug_name') or '').lower()
        or 'hemophilia' in (r.get('active_ingredient') or '').lower()]
for r in hits:
    print(r['drug_name'], r['application_type'], r['application_number'], r['approval_date'])
"
```

For a single drug lookup, the smallest working invocation:

```bash
curl -sSfL -A "$UA" 'https://troveproject.com/data/fda_approvals_nme_recent.json' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([r for r in d['rows'] if 'tryngolza' in (r.get('drug_name') or '').lower()])"
```

`-f` makes curl fail on an HTTP error instead of piping an error page into the JSON parser. If curl cannot connect at all, use the `git clone` fallback above and `python3 -c "import json; d=json.load(open('trove/web/data/fda_approvals_nme_recent.json')) ..."`.

## The actual approval-package documents

The Parquet bundle is just an *index*. The actual content (medical review, statistical review, etc.) lives at `drugs_at_fda_url`. That URL is FDA's application overview page; it links to every approval-package document FDA released for that drug.

**URL pattern for the application overview:**

```
https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no}
```

That page is static HTML, but **FDA only serves it to a client with a descriptive `User-Agent`** — see below. To get the actual document URLs:

1. **Fetch the application-overview HTML** — it links the original approval letter and the label as direct PDF URLs, and its "Review" link (`.../drugsatfda_docs/nda/{year}/{appl_no}Orig{N}s000TOC.html`) tells you which `{year}` directory the review package is published under and which original-application number `{N}` its filenames use. `{N}` is usually 1 but not always (Zurzuvae, NDA 217369, is `Orig2s000`), so read it from this link instead of assuming `Orig1`. The TOC page itself is JavaScript-rendered and does not contain usable PDF links.
2. **Probe for the review PDFs.** They live at `https://www.accessdata.fda.gov/drugsatfda_docs/nda/{year}/{appl_no}Orig{N}s000{doc_code}.pdf` where `{doc_code}` is one of the codes in `references/document_types.md` (e.g., `IntegratedR`, `MultidisciplineR`, `MedR`, `StatR`). The exact filename varies by drug and era, so probe candidates with `fda_probe` rather than assuming one. `fda_package_base` in `references/document_types.md` does step 1 and returns the prefix to probe.

```bash
UA='trove-fda-analyst/1.0 (+https://troveproject.com)'
curl -sSfL --max-redirs 3 --proto-redir '=https' -A "$UA" \
  'https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=761183' \
  | grep -o 'https://www.accessdata.fda.gov/drugsatfda_docs/[^" ]*' | sort -u
```

## Fetching PDFs

PDFs at accessdata.fda.gov and www.fda.gov are public and need no auth, but they are not a plain file host:

- **A descriptive `User-Agent` is required.** With curl's or Python urllib's default User-Agent, `www.accessdata.fda.gov` answers every request with `302` to `/apology_objects/abuse-detection-apology.html`. Following that redirect yields an HTML "FDA Apology" page (status `404`), not a document. Always send `-A 'trove-fda-analyst/1.0 (+https://troveproject.com)'`, and always confirm the response is `200`, `Content-Type: application/pdf`, and begins with `%PDF-` before treating it as a document.
- **Sizes range from under 1 MB to about 45 MB.** Approval letters and labels are small; clinical reviews are commonly 5–15 MB and several exceed 10 MB (Tryngolza's Integrated Review is 43 MB, 373 pages). Read `Content-Length` from a `HEAD` request first. Download anything over ~10 MB to disk and read it in page ranges; never load it whole.
- **Follow redirects, narrowly**: `-L --max-redirs 3 --proto-redir '=https'`.

The `fda_probe` and `fda_get` helpers in `references/document_types.md` do all of this; use them for every FDA request. "Reading a large review" in the same file covers page-range reading.

If FDA cannot be reached at all (DNS failure, timeout, or a proxy `403`), the sandbox is blocking the domain. FDA documents have no mirror: give the user the exact URL and ask them either to allow `www.accessdata.fda.gov` and `www.fda.gov` for code-execution network access in their Claude settings, or to download the PDF in a browser and upload it.

## What's NOT in the bundle

- **Document text content.** The bundle is metadata; document text is in the PDFs at FDA. Fetch at query time.
- **Approvals before 2021 or after 2024.** Not in the bundle. 2025–2026 approvals have not been ingested yet.
- **Generic (ANDA) and supplemental (sNDA) approvals.** The bundle covers FDA's "Novel Drug Approvals" curated lists only.

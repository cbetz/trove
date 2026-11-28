# Data layout — FDA novel drug approvals index

## The bundle

- Parquet: `https://troveproject.com/data/fda_approvals_nme_recent.parquet`
- JSON: `https://troveproject.com/data/fda_approvals_nme_recent.json`

331 rows covering FDA novel drug approvals whose original approval falls in calendar years 2021–2026. Both regulatory centers are included: 295 CDER (NMEs + novel antibody BLAs from the annual *Novel Drug Approvals* pages) plus 36 CBER (cell and gene therapies from the *Approved Cellular and Gene Therapy Products* page). 2026 is in progress: its CDER rows run to the "current as of" date on FDA's 2026 list (`totals.year_in_progress.cder_list_current_as_of`, 2026-11-24 in this build), and FDA lists that year's drugs without links, so each is matched to its application in openFDA's Drugs@FDA data by brand name and approval date.

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
    "drugs": 331,
    "year_min": 2021,
    "year_max": 2026,
    "by_year": {"2021": 54, "2022": 42, "2023": 62, "2024": 59, "2025": 51, "2026": 63},
    "sources_read": {"cder_lists": "2026-11-26", "drugs_at_fda_api": "2026-11-28", "cber": "2026-11-26", "openfda": "2026-11-26"},
    "year_in_progress": {"year": 2026, "cder_list_current_as_of": "2026-11-24"}
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
| `sponsor` | Company that holds the application. CDER: parsed from drugs@FDA, title-cased from FDA's all-caps stored form. CBER: parsed from the per-product page's "Manufacturer" field. For 2025 CDER rows and for withdrawn products such as Pepaxto this is the applicant named in FDA's NME compilation instead, which is spelled out rather than abbreviated. For 2026 CDER rows it is the sponsor in openFDA's Drugs@FDA record, in the same abbreviated form as the drugs@FDA page. Populated for all 331 rows. |
| `approval_date` | Date of the **original** approval, ISO `YYYY-MM-DD`, never null. CDER: the original-approval action date in drugs@FDA (the date on the approval letter), which occasionally differs by a few days from FDA's annual list (Pimjetmi is listed as November 13, 2026; its original approval is November 10). CBER: the date of the original approval letter — not a later supplement letter. |
| `indication` | CDER: FDA's one-line approved-use summary from its annual list. CBER: the indication on the product page **as it read when fetched**, which can include indications added after the original approval; several indications are joined with `; `, and text over 600 characters is cut with `…`. |
| `application_number` | NDA / BLA application number (6 digits). For CBER products this is the STN. |
| `application_type` | "NDA" or "BLA". CBER products are always BLA. |
| `label_pdf_url` | Direct link to the FDA-approved label PDF (CDER) or Package Insert (CBER). |
| `drugs_at_fda_url` | CDER: drugs@FDA application-overview URL. CBER: per-product FDA page under `fda.gov/vaccines-blood-biologics/` — that page is the canonical hub for the approval letter, package insert, clinical review memo, and Summary Basis for Regulatory Action. |
| `trials_snapshot_url` | Drug Trials Snapshot URL (CDER only; CBER doesn't publish Trials Snapshots — `null`) |
| `regulatory_center` | `"CDER"` or `"CBER"`. CDER = small molecules + most antibody biologics. CBER = cell and gene therapies. |
| `approval_letter_url` | CDER only. The approval letter FDA posted for the original approval (PDF), from drugs@FDA. From openFDA's Drugs@FDA record. 294 of 295 CDER rows (Pepaxto, since withdrawn, has none). |
| `review_url` | CDER only. The approval package for the original approval: an HTML table of contents linking each FDA review PDF (clinical, statistical, clinical pharmacology, summary review). 281 of 295 CDER rows; 12 of the 14 without one were approved in 2026 and FDA had not posted the reviews yet. **Start here** instead of scraping the drugs@FDA overview page. |
| `submission_classification` | CDER NDAs only. FDA's classification on drugs@FDA, e.g. `Type 1 - New Molecular Entity`. Null for BLAs. |
| `fda_receipt_date` | CDER only. Date FDA received the first complete application, ISO. |
| `dosage_form`, `route_of_administration` | CDER only. As FDA lists them at original approval; `; `-separated when a product has more than one. |
| `review_designation` | CDER only. `Priority` or `Standard`, sometimes qualified, e.g. `Priority (used priority review voucher)`. |
| `orphan_drug_designation`, `accelerated_approval`, `breakthrough_therapy_designation`, `fast_track_designation`, `qualified_infectious_disease_product` | CDER only. `Yes` / `No`, sometimes qualified, e.g. `Yes (indication [A] only)`. Test with `LIKE 'Yes%'`. |
| `priority_review_voucher_issued`, `priority_review_voucher_redeemed` | CDER only. Issued is `TD`, `RPD`, `MTMC` or `No`. |
| `designations_source` | Where `review_designation` and `orphan_drug_designation` came from: `compilation` (FDA's NME compilation, approvals through 2025) or `openfda` (the application's Drugs@FDA record, for a year the compilation does not cover yet). Null for CBER rows. On `openfda` rows the other designation columns, `fda_receipt_date`, `dosage_form` and `route_of_administration` are null, meaning "not recorded yet"; `orphan_drug_designation` is `Yes` or null, never `No`; and the orphan flag belongs to the application, so it can reflect a designation for a use other than the one approved. On the 237 approvals from 2021 through 2025 that both sources cover, Drugs@FDA's review priority matched the compilation for 236 and its orphan flag for 235 (it was set on two applications the compilation records as not orphan). |
| `documents_read` | ISO date the row's Drugs@FDA record was read through openFDA (`2026-11-28` in this build), on every CDER row openFDA has. Null for CBER rows and for a withdrawn application openFDA no longer lists. If a link 404s or a review seems to be missing, FDA may have posted or moved documents since this date: check the overview page. |
| `pharm_class_epc` | FDA's Established Pharmacologic Class for the product, from openFDA's label data, e.g. `Kinase Inhibitor`; `; `-separated when there is more than one. Populated for 116 of 331 rows: FDA assigns a class only where the active moiety has been indexed, so null means "not recorded", not "no class". No CBER row has one. |
| `pharm_class_moa` | Mechanism-of-action classes from the same source (95 rows). These include interaction classes such as `Cytochrome P450 3A Inducers`, so do not present the list as the drug's therapeutic mechanism without reading the label. |

For approvals through 2025 the designation columns come from FDA's Compilation of CDER NME and New Biologic Approvals and describe the application **at the time of original approval** (see `designations_source` for 2026). They answer "was X approved under accelerated approval / with breakthrough designation?" without opening a PDF; cite the compilation when you use them. They are null for every CBER row. `label_pdf_url` is populated for 325 of 331 rows; five of the six without one are November 2026 approvals whose label FDA had not posted.

The whole compilation (every CDER novel approval, 1985–2025, 1,387 rows, same designation columns) is published separately at `https://troveproject.com/data/fda_nme_compilation.parquet` and `.csv`; column definitions are at `https://troveproject.com/drugs/compilation/index.md`. Use it for questions about approvals outside 2021–2026 or about trends (approvals per year, share with priority review). It has no document links.

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
- **Approvals before 2021 or after 2025.** Not in the bundle. 2025–2026 approvals have not been ingested yet.
- **Generic (ANDA) and supplemental (sNDA) approvals.** The bundle covers FDA's "Novel Drug Approvals" curated lists only.

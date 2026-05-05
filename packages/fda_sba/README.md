# fda_sba

Index of recent FDA novel drug approvals (NMEs + novel BLA approvals) with links to their approval-package documents on accessdata.fda.gov. Source: FDA's annual "Novel Drug Approvals" pages.

**Status:** v0.1 — index only, no document extraction. Each row carries enough metadata to *find* the approval package (drug name, active ingredient, application number, approval date, indication) and direct links to the drugs@FDA detail page where the actual PDFs live. Sponsor isn't extracted in v0.1; it's available on each drug's drugs@FDA application-overview page.

## What's covered

- **Calendar years 2021–2024** of FDA's annual *Novel Drug Approvals* lists. Those lists curate the meaningful approvals — new molecular entities (NMEs) approved via NDA, plus novel BLA approvals. We scrape the curated lists rather than every FDA approval, because they're the set most public discourse cares about.
- 192 drugs total across 4 years.
- 2020 isn't included — FDA's 2020 page isn't reachable on the current site. Pre-2020 needs a different source (Wayback Machine or alternative).
- Each row includes a direct link to the drugs@FDA application overview, which is FDA's index of every PDF document FDA released for that approval (label, medical review, statistical review, pharmacology review, chemistry review, etc.).

## What's not covered (v0.1)

- **Document extraction.** trove doesn't pre-extract content from approval-package PDFs. The companion Claude skill (`fda-analyst`) reads PDFs at query time when a user asks about a specific approval.
- **Older approvals.** Pre-2020 approvals are out of scope for v0.1; older drugs are typically scanned PDFs needing OCR, which is a separate project.
- **Device approvals.** This covers drugs (Center for Drug Evaluation and Research). Devices and biologics that aren't on FDA's "novel drug" lists aren't included.
- **Generic approvals (ANDAs).** Out of scope.

## Usage

```python
from fda_sba import scrape_nme_year, build_index

# Scrape one year's FDA novel-drug approvals page
rows = scrape_nme_year(2024, cache_dir="data/raw/fda")

# Build the full index across multiple years
df = build_index(years=range(2020, 2025), cache_dir="data/raw/fda")
df.head()
```

## Fields

| Field | Description |
|-------|-------------|
| `year` | Calendar year of the FDA novel-drug approvals page |
| `drug_name` | FDA brand name (as listed in the FDA novel-drug page) |
| `active_ingredient` | International nonproprietary or USAN name |
| `approval_date` | Approval date (date type) |
| `indication` | Short indication string from FDA's page |
| `application_number` | NDA or BLA number, parsed from the label PDF URL when present |
| `application_type` | "NDA" or "BLA" (inferred from application number prefix) |
| `label_pdf_url` | Direct link to the FDA-approved label PDF (when listed) |
| `drugs_at_fda_url` | Direct link to the drugs@FDA application overview (lists every PDF in the approval package) |
| `trials_snapshot_url` | Drug Trials Snapshot URL (when FDA published one) |

## Source pages

- Novel Drug Approvals for 2024: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2024
- Novel Drug Approvals for 2023: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2023
- Novel Drug Approvals for 2022: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2022
- Novel Drug Approvals for 2021: https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2021

These pages are HTML tables. trove fetches the raw HTML, parses with `lxml`, and produces tidy records. The HTML structure has been stable across the four years we cover.

## Licensing

FDA content (including the novel-drug-approvals pages and the underlying approval-package documents) is US government work and public domain. trove redistributes derived index columns freely; users should cite "U.S. Food and Drug Administration, Drugs@FDA database" when publishing.

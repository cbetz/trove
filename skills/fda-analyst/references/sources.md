# Data layout — FDA novel drug approvals index

## The bundle

`https://troveproject.com/data/fda_approvals_nme_recent.parquet` (and the same data as JSON at `…fda_approvals_nme_recent.json`).

192 rows × 10 columns covering FDA Novel Drug Approvals for calendar years 2021–2024.

## Columns

| Column | Description |
|--------|-------------|
| `year` | Calendar year of the FDA novel-drug-approvals page |
| `drug_name` | FDA brand name |
| `active_ingredient` | International nonproprietary or USAN name |
| `approval_date` | Approval date |
| `indication` | FDA-approved use string from the FDA novel-drug page |
| `application_number` | NDA or BLA application number (6 digits) |
| `application_type` | "NDA" or "BLA" (inferred from the application number prefix) |
| `label_pdf_url` | Direct link to the FDA-approved label PDF |
| `drugs_at_fda_url` | Direct link to the drugs@FDA application overview — lists every PDF in the approval package |
| `trials_snapshot_url` | Drug Trials Snapshot URL (when FDA published one) |

## Query patterns

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

**By application type:**

```sql
SELECT application_type, COUNT(*) FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
GROUP BY application_type;
```

## The actual approval-package documents

The Parquet bundle is just an *index*. The actual content (medical review, statistical review, etc.) lives at `drugs_at_fda_url`. That URL is FDA's application overview page; it links to every approval-package document FDA released for that drug.

**URL pattern for the application overview:**

```
https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no}
```

That page is HTML. To get the actual document URLs, you can:

1. **Fetch the application-overview HTML and parse it** — links to "Approval Letter," "Label," "Medical Review," "Statistical Review," etc., with PDF URLs.
2. **Construct PDF URLs directly when the pattern is known.** Approval-package PDFs typically live at `https://www.accessdata.fda.gov/drugsatfda_docs/nda/{year}/{appl_no}Orig1s000{doc_code}.pdf` where `{doc_code}` is one of the codes in `references/document_types.md` (e.g., `MedR` for medical review, `StatR` for statistical review). The exact filename varies, so the application overview is the more reliable source.

For most questions, follow the `drugs_at_fda_url`, identify the right document, fetch the PDF, and read it.

## Fetching PDFs

PDFs at accessdata.fda.gov are public, no auth, often 1–10 MB each. Fetch with a normal HTTP GET. Claude can read PDFs directly when they're attached to a query.

## What's NOT in the bundle

- **Document text content.** The bundle is metadata; document text is in the PDFs at FDA. Fetch at query time.
- **Older approvals (pre-2021).** Out of scope for v0.1.
- **Generic (ANDA) and supplemental (sNDA) approvals.** The bundle covers FDA's "Novel Drug Approvals" curated lists only.
- **Sponsor name.** Not present in v0.1 — we scrape FDA's novel-drug pages, which list drug name + active ingredient + date but not sponsor. The Drugs@FDA application overview includes sponsor; fetch from there if you need it.

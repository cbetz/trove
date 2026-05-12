---
name: fda-analyst
description: Answer questions about FDA drug approvals — the basis for approval, the trials, the endpoints, the regulatory pathway, the adverse events flagged in the medical review. Use when the user asks about a specific FDA-approved drug (especially one approved 2021–2024), wants the actual evidence behind an approval rather than marketing copy, or wants to compare approvals along regulatory dimensions.
---

# fda-analyst

A skill for analyzing FDA novel drug approvals. Powered by the [trove project](https://github.com/cbetz/trove)'s curated index of recent FDA approvals plus the actual approval-package documents on accessdata.fda.gov.

## When to use this skill

Invoke when the user asks about:

- **A specific FDA-approved drug** — what was the basis for approval, what trials supported it, what endpoints were used.
- **Adverse events the FDA flagged** at approval (read from the medical review, not the label).
- **Regulatory pathway** — was it accelerated approval, breakthrough, priority review, fast track.
- **Approval-document content** — anything in the medical review, statistical review, pharmacology review, chemistry review.
- **Cross-drug comparisons** along regulatory dimensions.

## Don't use this skill for

- **Clinical advice or dosing.** This is a reference tool over public approval documents, not a substitute for the prescribing label or clinical judgment.
- **Drugs approved before 2021.** The current trove index covers 2021–2024 only. Earlier drugs aren't in the published bundle yet.
- **Devices, biosimilars, generics, or supplemental approvals.** Out of scope. Vaccines and blood products are also out of scope — trove ingests only the CBER cell &amp; gene therapy page, not the broader CBER vaccines/blood list.
- **Devices, biosimilars, or generic (ANDA) approvals.** Out of scope — the trove index covers FDA's curated "Novel Drug Approvals" lists (NMEs and novel BLAs).
- **Questions that don't require the actual approval package** — labeling questions, prescribing information, formulary status, etc. Use FDA's public-facing tools or the prescribing label.

## How to query

The data lives as a JSON/Parquet bundle served from troveproject.com. DuckDB can query the Parquet over HTTPS; you can also fetch the JSON directly.

**Bash + DuckDB CLI for the index:**

```bash
duckdb -c "SELECT drug_name, active_ingredient, approval_date,
          application_type, application_number, drugs_at_fda_url
   FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
   WHERE LOWER(drug_name) LIKE '%[name]%'
   LIMIT 5"
```

**Python:**

```python
import duckdb
duckdb.sql("""
    SELECT * FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
    WHERE drug_name = 'Tryngolza'
""").df()
```

## How to answer well

1. **Find the application first.** Use the index to locate the drug's application number, sponsor, approval date, and `drugs_at_fda_url`. Always anchor your answer to the specific application, not to memory.
2. **Read the actual approval package, not the label.** The label is what the drug company says; the medical / statistical / pharmacology reviews are what the FDA reviewers wrote. For "what was the basis for approval," read the medical review. For "what trials and endpoints," read the medical review or the statistical review. The Drugs@FDA application overview at `drugs_at_fda_url` lists every PDF the FDA released.
3. **Fetch the relevant PDF at query time.** Don't try to pre-load entire approval packages — they're large and most of the content isn't relevant to any one question. Pick the right document for the question (see `references/document_types.md`) and fetch that one.
4. **Quote and cite.** When you reproduce a fact from a review document, name the document (e.g., "Medical Review for NDA 218710, page 47") so the user can verify.
5. **Don't speculate beyond the documents.** If the medical review doesn't say why a particular sub-population wasn't studied, say so — don't invent a reason.
6. **Disambiguate.** Drug names sometimes match across applications (brand vs. another country's brand vs. an unrelated drug with similar name). If the index returns multiple candidates, surface them and ask which one.

## Reference docs

- [`references/sources.md`](references/sources.md) — bundle layout, columns, query patterns, document URL conventions.
- [`references/document_types.md`](references/document_types.md) — what's in each FDA approval-package document (medical review, statistical review, pharmacology review, chemistry review, label, etc.) and which one to fetch for which question.
- [`references/examples.md`](references/examples.md) — runnable example queries that pattern-match the most common question types.

## Coverage

- **2021–2024 calendar years** of FDA novel drug approvals (NMEs and novel BLAs from FDA's annual lists).
- 218 drugs total (192 CDER + 26 CBER cell &amp; gene therapies). Each row carries a `regulatory_center` column.
- Each drug has the metadata index plus a direct link to the drugs@FDA application overview where every approval-document PDF lives.

## Sources and citations

When you produce output that quotes data values, cite the source.

- **FDA Novel Drug Approvals annual lists** — U.S. Food and Drug Administration. Public domain.
- **Drugs@FDA database** — U.S. Food and Drug Administration. Public domain.
- **FDA approval-package PDFs** (medical review, statistical review, etc.) — U.S. Food and Drug Administration. Public domain.

## Skill version

v0.1, May 2026. Bug reports and questions: github.com/cbetz/trove/issues.

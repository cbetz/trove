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
- **Drugs approved before 2021 or after 2024.** The trove index covers original approvals dated 2021–2024 only. A drug outside that window is not in the bundle; say so rather than answering from memory. (The document-fetch recipes below still work for any application number the user supplies.)
- **Devices, biosimilars, generics (ANDA), or supplemental approvals.** Out of scope — the index covers FDA's curated "Novel Drug Approvals" lists (NMEs and novel BLAs). Vaccines and blood products are also out of scope: trove ingests only the CBER cell & gene therapy page, not the broader CBER vaccines/blood list.
- **Questions that don't require the actual approval package** — labeling questions, prescribing information, formulary status, etc. Use FDA's public-facing tools or the prescribing label.

## How to query

The data lives as a JSON/Parquet bundle served from troveproject.com. DuckDB can query the Parquet over HTTPS; you can also fetch the JSON directly (see `references/sources.md` for a `curl` + `python3` path that needs no DuckDB).

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

## Fetching FDA documents: three rules

FDA's document servers (`www.accessdata.fda.gov`, `www.fda.gov`) are not a plain file host. Every fetch in this skill follows these rules; the copy-paste helpers `fda_probe` and `fda_get` in `references/document_types.md` implement them.

1. **Send a descriptive `User-Agent`.** With curl's default User-Agent (or Python urllib's), `accessdata.fda.gov` answers every request — real file or not — with `302` to `/apology_objects/abuse-detection-apology.html`. A probe loop that only looks for `200` then finds nothing and wrongly concludes the document does not exist. Use `-A 'trove-fda-analyst/1.0 (+https://troveproject.com)'` on every request.
2. **Never treat the response as a document until you have checked it.** A real hit is HTTP `200` **and** `Content-Type: application/pdf` **and** a body that starts with `%PDF-`. A redirect whose `Location` contains `apology`, a final URL containing `apology_objects`, or an HTML body titled "FDA Apology" means you were blocked: fix the User-Agent, wait a few seconds, retry once. Do not summarize an HTML error page as if it were a review.
3. **Check the size before you read.** Take `Content-Length` from the `HEAD` response. Review PDFs run from under 1 MB to about 45 MB and several hundred pages (the Tryngolza Integrated Review is 43 MB / 373 pages). Anything over ~10 MB: download it to disk, then read it **in page ranges** — never load or attach the whole file. See "Reading a large review" in `references/document_types.md`.

## If the network is blocked (claude.ai, Cowork, and other sandboxes)

Code-execution sandboxes often allow only a short list of domains. By default `troveproject.com`, `www.accessdata.fda.gov`, and `www.fda.gov` may not be on it; the symptom is `Could not resolve host`, a connection timeout, or a `403` from the sandbox proxy. This is different from the FDA apology page above, and a User-Agent will not fix it.

- **The index** has a supported fallback that uses GitHub, which sandboxes normally allow: `git clone --depth 1 https://github.com/cbetz/trove`, then read `trove/web/data/fda_approvals_nme_recent.json` (or `.parquet`, or `trove/artifacts/fda_approvals_nme_recent.csv`). Same data as the hosted bundle.
- **The FDA documents** have no mirror. Tell the user plainly that the sandbox cannot reach FDA, give them the exact document URL, and offer the two things that work: (a) they allow the domains `troveproject.com`, `www.accessdata.fda.gov`, and `www.fda.gov` in their Claude settings for code-execution network access (on Team/Enterprise plans an admin controls this), or (b) they open the URL in a browser, download the PDF, and upload it to the conversation.
- If a web-fetch or web-search tool is available, it may reach FDA when the sandbox cannot — but check the result the same way (rule 2).
- Do not answer from memory as a substitute. Say what could not be fetched.

## How to answer well

1. **Find the application first.** Use the index to locate the drug's application number, sponsor, approval date, and `drugs_at_fda_url`. Always anchor your answer to the specific application, not to memory.
2. **Read the actual approval package, not the label.** The label is what the drug company says; the medical / statistical / pharmacology reviews are what the FDA reviewers wrote. For "what was the basis for approval," read the medical review. For "what trials and endpoints," read the medical review or the statistical review. The Drugs@FDA application overview at `drugs_at_fda_url` lists every PDF the FDA released.
3. **Fetch the relevant PDF at query time.** Don't try to pre-load entire approval packages — they're large and most of the content isn't relevant to any one question. Pick the right document for the question (see `references/document_types.md`), probe for it with `fda_probe`, note its size, and fetch that one with `fda_get`. Read large documents in page ranges.
4. **Quote and cite.** When you reproduce a fact from a review document, name the document (e.g., "Medical Review for NDA 218710, page 47") so the user can verify.
5. **Don't speculate beyond the documents.** If the medical review doesn't say why a particular sub-population wasn't studied, say so — don't invent a reason.
6. **Disambiguate.** Drug names sometimes match across applications (brand vs. another country's brand vs. an unrelated drug with similar name). If the index returns multiple candidates, surface them and ask which one.

## Reference docs

- [`references/sources.md`](references/sources.md) — bundle layout, columns, query patterns, document URL conventions.
- [`references/document_types.md`](references/document_types.md) — what's in each FDA approval-package document (medical review, statistical review, pharmacology review, chemistry review, label, etc.) and which one to fetch for which question.
- [`references/examples.md`](references/examples.md) — runnable example queries that pattern-match the most common question types.

## Coverage

- **2021–2024 calendar years** of FDA novel drug approvals (NMEs and novel BLAs from FDA's annual lists), by date of original approval. Approvals from 2025 onward are not in the index yet.
- 217 drugs total (192 CDER + 25 CBER cell & gene therapies). Each row carries a `regulatory_center` column.
- Each drug has the metadata index plus a direct link to the drugs@FDA application overview where every approval-document PDF lives.

## Sources and citations

When you produce output that quotes data values, cite the source.

- **FDA Novel Drug Approvals annual lists** — U.S. Food and Drug Administration. Public domain.
- **Drugs@FDA database** — U.S. Food and Drug Administration. Public domain.
- **FDA approval-package PDFs** (medical review, statistical review, etc.) — U.S. Food and Drug Administration. Public domain.

## Skill version

Shipped in trove plugin 1.1.0 (November 2026). Corrections and questions: https://github.com/cbetz/trove/issues

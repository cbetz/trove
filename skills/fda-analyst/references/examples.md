# Example queries for fda-analyst

## 1. Find a specific drug

**Q:** "When was Tryngolza approved and what's it for?"

```sql
SELECT drug_name, active_ingredient, approval_date, application_type, application_number, indication, drugs_at_fda_url
FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
WHERE LOWER(drug_name) LIKE '%tryngolza%';
```

If the user wants to know the basis for approval (not just the metadata), follow up by fetching the clinical review — see example 3. The application-overview page at `drugs_at_fda_url` does not link review PDFs directly, so probe for them.

## 2. Recent approvals in a therapeutic area

**Q:** "What new cystic-fibrosis drugs have been approved recently?"

```sql
SELECT drug_name, active_ingredient, approval_date, indication
FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
WHERE LOWER(indication) LIKE '%cystic fibrosis%'
ORDER BY approval_date DESC;
```

## 3. What was the basis for approval

**Q:** "What was the basis for [drug] approval — what trials, what endpoints?"

The drugs@FDA overview links to a JS-rendered TOC page that you can't reliably scrape. The reliable path is **probing** for the right review-document filename. See `document_types.md` "How to actually fetch a review PDF" for the full pattern; the short version:

1. Look the drug up in the index. Get `application_number` and `approval_date`.
2. Define the `fda_probe` / `fda_package_base` / `fda_get` helpers from `document_types.md`. They send the User-Agent FDA requires and reject the abuse-detection page; a bare `curl` gets a `302` for every URL and finds nothing.
3. Get the package prefix with `fda_package_base {application number}`. It reads the year directory and the `Orig{N}` number from the overview page, so neither is guessed (`{N}` is not always 1). Then probe candidate filenames on that prefix, in this order: `IntegratedR.pdf` (2024+), `MultidisciplineR.pdf` (2021–2023), `MedR.pdf` (older split format).
4. The first one reported `OK` is the clinical review document. Note its size. Download it with `fda_get`; if it is over ~10 MB, read it in page ranges ("Reading a large review" in `document_types.md`) rather than whole.
5. Read the Clinical Trials / Efficacy section. Focus on:
   - The pivotal trial(s) — design (RCT vs. single-arm), N, comparator, duration
   - Primary endpoint(s) and effect size
   - Key safety findings
6. Quote with the document name and approximate page when you cite specifics.

**Worked example for Tryngolza (NDA 218614, approved Dec 2024):**

```bash
# Step 0: define UA, fda_probe, fda_package_base and fda_get — copy them from document_types.md

# Step 1: confirm it's in the index
curl -sSfL -A "$UA" 'https://troveproject.com/data/fda_approvals_nme_recent.json' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([r for r in d['rows'] if 'tryngolza' in (r.get('drug_name') or '').lower()])"

# Step 2: read the package location from the overview page, then probe for the review
BASE=$(fda_package_base 218614)    # https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000
for suffix in IntegratedR MultidisciplineR MedR; do
  fda_probe "${BASE}${suffix}.pdf"
done
# → OK 43.1 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf

# Step 3: 43 MB is far too large to read whole. Download once, then read page ranges.
fda_get "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf" review.pdf
pdfinfo review.pdf | grep Pages                    # 373
pdftotext -f 1 -l 12 -layout review.pdf -          # table of contents → find the efficacy and safety sections
pdftotext -f 7 -l 30 -layout review.pdf -          # e.g. the benefit-risk framework and executive summary
```

If step 1 fails to connect, the sandbox is blocking `troveproject.com`: use `git clone --depth 1 https://github.com/cbetz/trove` and read `trove/web/data/fda_approvals_nme_recent.json` instead. If step 2 prints `BLOCKED`, or cannot connect, see the fetching rules and "If the network is blocked" in `SKILL.md`.

## 4. Adverse events FDA flagged

**Q:** "What adverse events did FDA flag in the [drug] medical review?"

Same flow as #3 but read the Safety section of the Medical Review (typically near the end). The label has a redacted/marketing-vetted summary; the Medical Review has the reviewers' actual assessment, including:
- Common adverse events (rates from trials)
- Serious adverse events
- Discontinuations due to AEs
- Deaths and their adjudication
- Drug-related vs. background-rate AEs

## 5. Regulatory pathway

**Q:** "Was [drug] approved via accelerated approval?"

The Approval Letter (a short PDF, 5–15 pages, well under 1 MB — fine to read whole; suffix `Approv.pdf`, fetched with `fda_probe` / `fda_get`) usually states the regulatory pathway explicitly. The Medical Review's introduction also typically notes designations (priority review, breakthrough therapy, accelerated approval, orphan, fast track).

For accelerated approval specifically, look for:
- The phrase "accelerated approval" or "21 CFR 314 subpart H" in the Approval Letter
- A surrogate endpoint and required post-marketing confirmatory studies
- A statement about converting to traditional approval upon confirmation

## 6. Comparing approvals

**Q:** "Compare the regulatory pathways used for [drug A] and [drug B]."

1. Look up both drugs in the index, get their `drugs_at_fda_url`s.
2. Fetch both Approval Letters (the shortest doc with the pathway info) with `fda_probe` / `fda_get`.
3. Identify designations, primary regulatory pathway, and any conditions of approval for each.
4. Present side-by-side.

## When the question doesn't have a SQL answer

Some questions are about drug-development methodology, not about specific drugs:
- "What's the difference between accelerated approval and traditional approval?" → Reference question, no fetch needed. Answer from `references/document_types.md` Regulatory Designations section.
- "What documents are in an FDA approval package?" → Same; answer from `document_types.md`.
- "What's a 'breakthrough therapy' designation?" → Reference question. Brief answer.

For these, no SQL or PDF fetch is needed.

## Cross-domain questions

If the user asks something that spans drugs and hospitals (e.g., "which hospitals report charity-care for [drug]"), that's not in scope for this skill. The hcris-analyst skill handles hospital data; the two skills don't share data and shouldn't be conflated.

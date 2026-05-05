# Example queries for fda-analyst

## 1. Find a specific drug

**Q:** "When was Tryngolza approved and what's it for?"

```sql
SELECT drug_name, active_ingredient, approval_date, application_type, application_number, indication, drugs_at_fda_url
FROM read_parquet('https://troveproject.com/data/fda_approvals_nme_recent.parquet')
WHERE LOWER(drug_name) LIKE '%tryngolza%';
```

If the user wants to know the basis for approval (not just the metadata), follow up by fetching the Medical Review from `drugs_at_fda_url` — go to the application-overview page, find the "Medical Review" or "Multi-Disciplinary Review" PDF, and read it.

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
2. Probe candidate filenames via `HEAD` requests, in this order: `IntegratedR.pdf` (2024+), `MultidisciplineR.pdf` (2021–2023), `MedR.pdf` (older split format). Try both `approval_year` and `approval_year+1` as the URL year subdirectory.
3. The first one returning 200 is the clinical review document. Fetch it.
4. Read the Clinical Trials / Efficacy section. Focus on:
   - The pivotal trial(s) — design (RCT vs. single-arm), N, comparator, duration
   - Primary endpoint(s) and effect size
   - Key safety findings
5. Quote with the document name and approximate page when you cite specifics.

**Worked example for Tryngolza (NDA 218614, approved Dec 2024):**

```bash
# Step 1: confirm it's in the index
curl -s 'https://troveproject.com/data/fda_approvals_nme_recent.json' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([r for r in d['rows'] if 'tryngolza' in (r.get('drug_name') or '').lower()])"

# Step 2: probe for the review (2024 approval, so try 2024 + 2025 subdirs)
for year in 2024 2025; do
  for suffix in IntegratedR MultidisciplineR MedR; do
    url="https://www.accessdata.fda.gov/drugsatfda_docs/nda/$year/218614Orig1s000${suffix}.pdf"
    code=$(curl -sI -o /dev/null -w "%{http_code}" "$url")
    [ "$code" = "200" ] && echo "$url"
  done
done
# → returns: https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf

# Step 3: fetch and read the IntegratedR PDF
```

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

The Approval Letter (a short PDF, 5–15 pages) usually states the regulatory pathway explicitly. The Medical Review's introduction also typically notes designations (priority review, breakthrough therapy, accelerated approval, orphan, fast track).

For accelerated approval specifically, look for:
- The phrase "accelerated approval" or "21 CFR 314 subpart H" in the Approval Letter
- A surrogate endpoint and required post-marketing confirmatory studies
- A statement about converting to traditional approval upon confirmation

## 6. Comparing approvals

**Q:** "Compare the regulatory pathways used for [drug A] and [drug B]."

1. Look up both drugs in the index, get their `drugs_at_fda_url`s.
2. Fetch both Approval Letters (the shortest doc with the pathway info).
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

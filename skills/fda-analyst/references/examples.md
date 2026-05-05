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

1. Find the drug in the index, get its `drugs_at_fda_url`.
2. Fetch the application overview HTML (or open it in a browser).
3. Find the Medical Review PDF link.
4. Fetch and read the Medical Review. Focus on:
   - Section labeled "Clinical Trials" or "Efficacy"
   - The pivotal trial(s) — design (RCT vs. single-arm), N, comparator, duration
   - Primary endpoint(s) and effect size
   - Key safety findings
5. Quote with the document name and approximate page when you cite specifics.

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

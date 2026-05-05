# FDA approval-package document types

When the FDA approves a drug, it releases a multi-document "Approval Package" describing the basis for the decision. Each document type has a specific purpose; pick the right one for the question.

## The documents

| Document | What it covers | When to fetch |
|----------|---------------|---------------|
| **Approval Letter** | Brief regulatory letter from FDA to the sponsor — what's approved, conditions, post-marketing requirements (PMRs/PMCs). | Quick "was this approved?" / "what conditions?" questions. Short. |
| **Label** (USPI) | Prescribing information. Indications, dosing, contraindications, warnings, adverse reactions, clinical pharmacology, clinical studies (summary), how supplied, patient information. | Anything about prescribing info, label warnings, what was studied per the *summary*. Heavily marketing-vetted; not the same as what reviewers wrote. |
| **Medical Review** (or "Multi-Disciplinary Review" / "Cross-Discipline Team Leader Review") | The FDA reviewers' detailed assessment. Trials, endpoints, efficacy, safety, sub-populations, internal disagreements, sponsor's strengths and weaknesses. **The most useful single document for "what was the basis for approval."** | "What trials supported approval?", "What was the primary endpoint?", "What adverse events did FDA flag?", "Did reviewers disagree?", "What's the regulatory pathway story?" |
| **Statistical Review** | Statistical analysis of the trial data. Power, type-I error, multiplicity adjustments, sensitivity analyses, missing data handling. | Statistical methodology questions. Often technical. |
| **Pharmacology Review** | Animal toxicology and pharmacology data. | Safety pharmacology, animal-tox findings, mechanism of action data. |
| **Chemistry Review** (CMC) | Chemistry, manufacturing, and controls. Drug substance, drug product, stability, manufacturing. | CMC and manufacturing questions. Rarely relevant to clinical questions. |
| **Clinical Pharmacology / Biopharmaceutics Review** | Drug pharmacokinetics, drug-drug interactions, special populations (renal, hepatic, geriatric, pediatric), bioequivalence. | PK/PD questions, drug-interaction questions, special-population dosing rationale. |
| **Risk Assessment / Risk-Benefit / Office Director Memo** | Higher-level FDA decision rationale. Often summarizes the inter-disciplinary view. | "Why did FDA approve this?" overview questions. |
| **Drug Trials Snapshot** | FDA's plain-language summary of who was studied (demographics) and how the drug performed across sub-populations. | Plain-language summary; demographics-by-subpopulation efficacy. |

## The defaults

For most "tell me about this drug's approval" questions, fetch in this order:

1. **Medical Review first** — most informative single document.
2. **Drug Trials Snapshot** — quick demographic summary if relevant.
3. **Approval Letter** — only if specific questions about conditions / PMRs.
4. **Statistical Review** — only for statistical methodology questions.
5. **Label** — for prescribing info, NOT for "what was the evidence."

Don't fetch documents you don't need. Each PDF is 50–500 pages.

## How to actually fetch a review PDF

The drugs@FDA application overview at `drugs_at_fda_url` is **not a flat list of PDFs.** It links to a per-application Table-of-Contents page (`{appl_no}Orig1s000TOC.html`), and that TOC page is **JavaScript-rendered** — fetching the HTML with `curl` shows template strings (`' + pdfBaseName + 'Approv.pdf'`), not real URLs. So you can't simply scrape the TOC for PDF links.

**The reliable path is to probe candidate filenames via `HEAD` requests** and fetch the first one that returns 200. The pattern is:

```
https://www.accessdata.fda.gov/drugsatfda_docs/{type}/{year}/{appl_no}Orig1s000{suffix}.pdf
```

where:
- `{type}` is `nda` or `bla` (use `nda` for both unless you confirm otherwise — FDA stores BLAs under `nda/` for some applications)
- `{year}` is **the year FDA published the package**, which is often the approval year *or the year after*. Probe both `approval_year` and `approval_year+1`.
- `{suffix}` is the document code (see "What suffix to look for" below).

### Example: a working probe loop in bash

```bash
APPL_NO=218614  # Tryngolza
for year in 2024 2025; do
  for suffix in IntegratedR MultidisciplineR MedR StatR PharmR ClinPharmR ChemR RiskR Approv lbl AdminCorres OtherR; do
    url="https://www.accessdata.fda.gov/drugsatfda_docs/nda/$year/${APPL_NO}Orig1s000${suffix}.pdf"
    code=$(curl -sI -o /dev/null -w "%{http_code}" "$url")
    [ "$code" = "200" ] && echo "$url"
  done
done
```

### What suffix to look for, by question

For "what was the basis for approval?" the answer is *some* form of clinical review. FDA has used three formats over time, and the right one to look for depends on the approval year:

| Approval era | Primary clinical-review suffix | What it is |
|--------------|--------------------------------|------------|
| **2021–2023** (mostly) | `MultidisciplineR.pdf` | Single consolidated review across disciplines |
| **2023–2024+** (newer) | `IntegratedR.pdf` | The Integrated Review format — clinical + statistical + clinical pharm in one doc |
| **older / split format** | `MedR.pdf` + `StatR.pdf` + `PharmR.pdf` | Separate per-discipline reviews |

Probe in this order: `IntegratedR` → `MultidisciplineR` → `MedR`. The first one that returns 200 is the right document.

### Other suffixes worth knowing

| Suffix | Document |
|--------|----------|
| `Approv.pdf` | Approval letter (short — regulatory pathway, conditions, post-marketing requirements) |
| `lbl.pdf` | The FDA-approved label (USPI). Also `lbledt.pdf` (redacted), `Corrected_lbl.pdf` |
| `RiskR.pdf` | Risk assessment / Office Director memo (high-level decision rationale) |
| `ChemR.pdf` | Chemistry Manufacturing Controls review |
| `ClinPharmR.pdf` | Clinical pharmacology / PK |
| `OtherR.pdf` | Catch-all for additional review documents |
| `AdminCorres.pdf` | Administrative correspondence |

### Validated working examples

These were probed and confirmed to return 200 (May 2026):

```
# Tryngolza (NDA 218614, approved Dec 2024 — Integrated Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000Approv.pdf
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000lbl.pdf

# Alyftrek (NDA 218710, approved Dec 2024 — Integrated Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218710Orig1s000IntegratedR.pdf

# Saphnelo (BLA 761123, approved Aug 2021 — older Multidiscipline Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/761123Orig1s000MultidisciplineR.pdf
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/761123Orig1s000Approv.pdf
```

Use the probe loop above; don't assume a specific filename for a drug you haven't checked.

## Regulatory designations

These often surface in the Medical Review or Approval Letter:

- **Priority Review** — FDA target action date in 6 months instead of 10. Used when the drug offers significant improvement over existing therapy.
- **Breakthrough Therapy** — designation given during development; FDA provides intensive guidance.
- **Fast Track** — designation given during development; expedited review and rolling submission.
- **Accelerated Approval** — approval based on a surrogate endpoint reasonably likely to predict clinical benefit; conditional on confirmatory post-marketing studies.
- **Orphan Designation** — for rare diseases (<200,000 patients in US); confers tax credits and market exclusivity.

When asked "was this drug X-pathway?", look for the designation in the Approval Letter or the early summary sections of the Medical Review.

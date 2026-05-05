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

## Filename conventions

Approval-package PDFs at accessdata.fda.gov follow patterns like:

```
{appl_no}Orig1s000Approv.pdf      ← Approval Letter
{appl_no}Orig1s000lbl.pdf          ← Label (also: lbledt.pdf for redacted)
{appl_no}Orig1s000MedR.pdf         ← Medical Review (varies: also MultiR, CDTL)
{appl_no}Orig1s000StatR.pdf        ← Statistical Review
{appl_no}Orig1s000PharmR.pdf       ← Pharmacology Review
{appl_no}Orig1s000ChemR.pdf        ← Chemistry Review
{appl_no}Orig1s000ClinPharmR.pdf   ← Clinical Pharmacology Review
{appl_no}Orig1s000RiskR.pdf        ← Risk Assessment / Office Director Memo
{appl_no}OrigTOC.pdf               ← Table of contents for the package
```

The actual filenames vary — some applications have "MultiR" instead of separate MedR/StatR/PharmR, some bundle multiple disciplines into one "Cross-Discipline Team Leader Review." When in doubt, fetch the application overview at `drugs_at_fda_url` and look at the document list.

## Regulatory designations

These often surface in the Medical Review or Approval Letter:

- **Priority Review** — FDA target action date in 6 months instead of 10. Used when the drug offers significant improvement over existing therapy.
- **Breakthrough Therapy** — designation given during development; FDA provides intensive guidance.
- **Fast Track** — designation given during development; expedited review and rolling submission.
- **Accelerated Approval** — approval based on a surrogate endpoint reasonably likely to predict clinical benefit; conditional on confirmatory post-marketing studies.
- **Orphan Designation** — for rare diseases (<200,000 patients in US); confers tax credits and market exclusivity.

When asked "was this drug X-pathway?", look for the designation in the Approval Letter or the early summary sections of the Medical Review.

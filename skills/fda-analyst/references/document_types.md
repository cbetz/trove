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

Don't fetch documents you don't need. Each PDF is 50–500 pages and can be tens of megabytes — check the size first and read large ones in page ranges (see "Reading a large review" below).

## How to actually fetch a review PDF

The drugs@FDA application overview at `drugs_at_fda_url` is **not a flat list of PDFs.** It links to a per-application Table-of-Contents page (`{appl_no}Orig{N}s000TOC.html`), and that TOC page is **JavaScript-rendered** — fetching the HTML with `curl` shows template strings (`' + pdfBaseName + 'Approv.pdf'`), not real URLs. So you can't simply scrape the TOC for PDF links.

**The reliable path is to probe candidate filenames via `HEAD` requests** and fetch the first one that is a real PDF. The pattern is:

```
https://www.accessdata.fda.gov/drugsatfda_docs/{type}/{year}/{appl_no}Orig{N}s000{suffix}.pdf
```

where:
- `{type}` is `nda` or `bla` (use `nda` for both unless you confirm otherwise — FDA stores BLAs under `nda/` for some applications)
- `{year}` is **the year FDA published the package**, which is often the approval year *or the year after*.
- `{N}` is the number of the original application inside the NDA or BLA. It is usually `1` (`Orig1s000`), but not always: Zurzuvae (NDA 217369) is published as `Orig2s000`, and probing `Orig1s000` filenames for it finds nothing.
- **Do not guess `{year}` or `{N}`. Read both from the overview page.** The overview at `drugs_at_fda_url` is static HTML (it needs the User-Agent too), and its "Review" link is `.../drugsatfda_docs/nda/{year}/{appl_no}Orig{N}s000TOC.html`. The `fda_package_base` helper below returns that link without the `TOC.html` ending, which is the prefix every document in the package shares. The same page links the original approval letter and label PDFs directly.
- `{suffix}` is the document code (see "What suffix to look for" below).

### The helpers: `fda_probe` and `fda_get`

Define these once per shell session and use them for **every** FDA request. Do not use a bare `curl` against FDA.

```bash
# Identify yourself. www.accessdata.fda.gov answers curl's default User-Agent
# (and python-urllib's) with a 302 to an "abuse detection" apology page, not the file.
UA='trove-fda-analyst/1.0 (+https://troveproject.com)'

# fda_probe URL -> "OK <size> MB <url>" for a real PDF, "BLOCKED <url>" if FDA
# served the apology page, and nothing at all for a filename that does not exist.
fda_probe() {
  curl -sIL --max-redirs 3 --proto-redir '=https' --max-time 30 -A "$UA" "$1" | tr -d '\r' | awk -v url="$1" '
    /^HTTP\//                      { code = $2; type = ""; len = 0 }
    tolower($1) == "content-type:"   { type = $2 }
    tolower($1) == "content-length:" { len = $2 }
    tolower($1) == "location:" && /apology/ { blocked = 1 }
    END {
      if (blocked) print "BLOCKED " url
      else if (code == 200 && type ~ /pdf/) printf "OK %.1f MB %s\n", len / 1048576, url
    }'
}

# fda_package_base APPL_NO -> the URL prefix of the original approval package, read
# from the overview page's "Review" link, e.g.
#   https://www.accessdata.fda.gov/drugsatfda_docs/nda/2023/217369Orig2s000
# Prints nothing if the overview page has no review link (no package published).
fda_package_base() {
  curl -sSfL --max-redirs 3 --proto-redir '=https' --max-time 60 -A "$UA" \
    "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo=$1" \
    | grep -o 'https://www\.accessdata\.fda\.gov/drugsatfda_docs/[a-z]*/[0-9]*/[0-9]*Orig[0-9]*s000TOC\.html' \
    | sort -u | head -n 1 | sed 's/TOC\.html$//'
}

# fda_get URL FILE -> downloads to FILE and refuses anything that is not a PDF.
fda_get() {
  curl -sSL --max-redirs 3 --proto-redir '=https' --max-time 600 -A "$UA" -o "$2" "$1" \
    && head -c 5 "$2" | grep -q '%PDF-' \
    || { echo "NOT A PDF (blocked, missing, or an HTML error page): $1" >&2; rm -f "$2"; return 1; }
}
```

Why each piece is there:

- **`-A "$UA"`** — without a descriptive User-Agent, `www.accessdata.fda.gov` returns `302 → /apology_objects/abuse-detection-apology.html` for every URL, existing or not. Verified November 2026: the same PDF URL returned `302` with curl's default User-Agent and `200 application/pdf` with the User-Agent above. Python's default `urllib` User-Agent is blocked the same way; set the header there too.
- **`-L --max-redirs 3 --proto-redir '=https'`** — follow a legitimate redirect if FDA issues one, but only over HTTPS and only a few hops. (The block itself arrives as a redirect, which is why the next check matters.) Keep the quotes around `'=https'`: zsh, the default shell on macOS, expands an unquoted `=https` as a command lookup and the whole command fails with `https not found`.
- **Content-type and `%PDF-` checks** — following the apology redirect ends in an HTML page (served with a `404`). Checking only "did the download succeed" would hand you that HTML as if it were the review. `fda_probe` reports `BLOCKED`; `fda_get` deletes the file and fails.
- **Size in the probe output** — so you decide how to read the document *before* downloading it.

If you see `BLOCKED`: confirm the User-Agent is set, wait a few seconds, retry once, and keep request rates low (a probe loop is ~20 requests; don't run several in parallel). If it persists, tell the user FDA is rate-limiting and give them the URL. If instead `curl` cannot connect at all, the sandbox is blocking the domain — see "If the network is blocked" in `SKILL.md`.

### Example: a working probe loop (bash or zsh)

```bash
BASE=$(fda_package_base 218614)   # Tryngolza
echo "$BASE"
# https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000
for suffix in IntegratedR MultidisciplineR MedR StatR PharmR ClinPharmR ChemR RiskR Approv lbl AdminCorres OtherR; do
  fda_probe "${BASE}${suffix}.pdf"
done
# OK 43.1 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf
# OK 13.8 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000ChemR.pdf
# OK 1.1 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000RiskR.pdf
# OK 13.3 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000OtherR.pdf
# OK 0.4 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000Approv.pdf
# OK 1.2 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000lbl.pdf
```

An application whose package is not `Orig1`:

```bash
fda_package_base 217369           # Zurzuvae
# https://www.accessdata.fda.gov/drugsatfda_docs/nda/2023/217369Orig2s000
fda_probe "$(fda_package_base 217369)IntegratedR.pdf"
# OK 21.3 MB https://www.accessdata.fda.gov/drugsatfda_docs/nda/2023/217369Orig2s000IntegratedR.pdf
```

No output from a probe means that filename does not exist in the package; it does not mean the package does not exist. If `fda_package_base` itself prints nothing, the overview page has no review link: fall back to probing `{appl_no}Orig1s000` under the approval year and the year after, and if that also finds nothing, tell the user FDA has not published a review package at the usual location and give them the overview URL. `BLOCKED` lines mean the opposite problem — you were not allowed to look.

### Reading a large review

Sizes vary enormously: approval letters are well under 1 MB, most clinical reviews are 5–15 MB, and some exceed 40 MB (Tryngolza's Integrated Review: 43 MB, 373 pages). **Do not load, attach, or `Read` a PDF over ~10 MB in one go** — it will exhaust context or fail outright. Download it to disk once, then work in page ranges:

```bash
fda_get "https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf" review.pdf
pdfinfo review.pdf | grep Pages                       # how long is it?
pdftotext -f 1 -l 12 -layout review.pdf - | less      # the table of contents is in the first ~10 pages
pdftotext -f 20 -l 45 -layout review.pdf -            # then read only the section you need
```

Without poppler (`pdftotext`/`pdfinfo`), use Python:

```python
from pypdf import PdfReader          # pip install pypdf
r = PdfReader("review.pdf")
print(len(r.pages))
print("\n".join(r.pages[i].extract_text() for i in range(19, 45)))   # pages 20–45
```

Working method:

1. Read the table of contents (first ~10–15 pages) and note the page numbers of the sections the question needs — typically the Benefit-Risk/Executive Summary, the efficacy review of the pivotal trial(s), and the safety review.
2. Read those ranges, 20–40 pages at a time. To locate a term without reading everything: `pdftotext -layout review.pdf review.txt && grep -n -i "primary endpoint" review.txt`.
3. If a page range extracts as empty or garbled text, those pages are scanned images. Split them out (`qpdf review.pdf --pages . 20-30 -- part.pdf`) and read that small file as a PDF instead.
4. In Claude Code, the `Read` tool takes a `pages` argument for PDFs (at most 20 pages per call) — use it on the downloaded file rather than reading the whole document.
5. Cite the PDF page numbers you actually read.

Disk is the only cost of the full download; if space is tight, delete the file when done.

### CBER (cell and gene therapy) documents

CBER products are not in drugs@FDA and do not follow the filename pattern above. Their `drugs_at_fda_url` is the product page on `www.fda.gov`; it is static HTML that lists each document (approval letters, Summary Basis for Regulatory Action, clinical review memo, package insert) as a `https://www.fda.gov/media/{id}/download` link. Fetch the page with the User-Agent, pick the link by its text, and use `fda_probe` / `fda_get` on it exactly as above. Two cautions: the page lists supplement approval letters alongside the original one, and documents older than three years move to an archived page linked as "Supporting Documents older than three years".

### What suffix to look for, by question

For "what was the basis for approval?" the answer is *some* form of clinical review. FDA has used three formats over time, and the right one to look for depends on the approval year:

| Approval era | Primary clinical-review suffix | What it is |
|--------------|--------------------------------|------------|
| **2021–2023** (mostly) | `MultidisciplineR.pdf` | Single consolidated review across disciplines |
| **2023–2024+** (newer) | `IntegratedR.pdf` | The Integrated Review format — clinical + statistical + clinical pharm in one doc |
| **older / split format** | `MedR.pdf` + `StatR.pdf` + `PharmR.pdf` | Separate per-discipline reviews |

Probe in this order: `IntegratedR` → `MultidisciplineR` → `MedR`. The first one `fda_probe` reports as `OK` is the right document.

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

These were probed with `fda_probe` and confirmed to return `200 application/pdf` (November 2026), with the sizes shown:

```
# Tryngolza (NDA 218614, approved Dec 2024 — Integrated Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000IntegratedR.pdf       # 43.1 MB — read in page ranges
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000Approv.pdf            # 0.4 MB
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218614Orig1s000lbl.pdf               # 1.2 MB

# Alyftrek (NDA 218710, approved Dec 2024 — Integrated Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2025/218710Orig1s000IntegratedR.pdf       # 5.9 MB

# Saphnelo (BLA 761123, approved Aug 2021 — older Multidiscipline Review format):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/761123Orig1s000MultidisciplineR.pdf  # 8.0 MB
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2021/761123Orig1s000Approv.pdf            # 0.3 MB

# Tzield (BLA 761183, approved Nov 2022 — package published under 2023, split-format review):
https://www.accessdata.fda.gov/drugsatfda_docs/nda/2023/761183Orig1s000MedR.pdf              # 6.6 MB
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

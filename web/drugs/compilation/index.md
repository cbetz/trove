# FDA compilation of CDER NME and new biologic approvals, 1985–2025, as CSV

This is FDA's Compilation of CDER NME and New Biologic Approvals, 1985–2025, as CSV and Parquet. FDA publishes the compilation as an Excel workbook only. The files here hold the same 1,387 approvals, one row each, with ISO dates and application numbers that match Drugs@FDA.

## Download

- CSV: https://troveproject.com/data/fda_nme_compilation.csv (1,387 rows)
- Parquet: https://troveproject.com/data/fda_nme_compilation.parquet
- Provenance: https://troveproject.com/data/fda_nme_compilation_source.json
- FDA's original workbook and data dictionary: https://www.fda.gov/drugs/drug-approvals-and-databases/compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals

## Columns

| Column | What it holds |
|---|---|
| `approval_year` | Calendar year of the FDA approval date. |
| `proprietary_name` | Brand name. FDA writes "[drug marketed without a proprietary name]" when there is none. |
| `active_ingredient` | Active ingredient or active moiety, named as in structured product labeling. |
| `applicant` | The company named in the approval letter. FDA may simplify the name. |
| `application_type` | NDA (new drug application) or BLA (biologics license application). |
| `application_number, _2, _3` | FDA application numbers, zero-padded to the six digits Drugs@FDA uses. A product approved in more than one dosage form can have several. |
| `dosage_form, route_of_administration (and _2, _3)` | Dosage form and route for each application number, in the same order. |
| `fda_receipt_date` | Date FDA received the first complete marketing application (ISO date). |
| `fda_approval_date` | Date FDA originally approved the application (ISO date). |
| `days_receipt_to_approval` | Added by trove: calendar days from fda_receipt_date to fda_approval_date. |
| `abbreviated_indication` | Short indication from the approval letter or original labeling. Filled for approvals before October 1, 2007. |
| `approved_use` | Indications and Usage text of the label at original approval. Filled for approvals from October 1, 2007. |
| `review_designation` | Priority or Standard at the time of approval. For 1985–1991, FDA maps its older type A and B ratings to Priority and type C to Standard. |
| `orphan_drug_designation` | Yes if the sponsor held orphan designation for at least one initially approved indication. |
| `accelerated_approval` | Yes, No, or N/A for approvals before April 15, 1992. |
| `breakthrough_therapy_designation` | Yes, No, or N/A for approvals before July 9, 2012. |
| `fast_track_designation` | Yes, No, or N/A for approvals before November 21, 1997. |
| `qualified_infectious_disease_product` | Yes, No, or N/A for approvals before July 9, 2012. |
| `priority_review_voucher_issued` | TD (tropical disease), RPD (rare pediatric disease) or MTMC (material threat medical countermeasure) when the approval earned a voucher; N/A before September 27, 2007. |
| `priority_review_voucher_redeemed` | Yes when the application got priority review by redeeming a voucher. |
| `notes` | FDA's notes, mostly products moved from NDA to BLA in March 2020. |

## What trove changed

Excel to CSV and Parquet; lower-case column names; ISO dates; application numbers zero-padded to six digits; one added column, `days_receipt_to_approval`. All other values are FDA's text as written.

Source: FDA file "2026 Compilation_of_CDER_NME_and_New_Biologic_Approvals_1985-2025.xlsx", dated May 12, 2026. Page: https://troveproject.com/drugs/compilation/ (updated 2026-11-26).

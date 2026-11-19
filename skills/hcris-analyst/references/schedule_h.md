# IRS Form 990 Schedule H: the fields in `schedule_h_2022.parquet`

**Bundle:** `https://troveproject.com/data/schedule_h_2022.parquet`. One row per tax year 2022 return with a Schedule H that was found in the IRS e-file releases for 2023 through 2026. It is **not** deduplicated: an EIN appears more than once when it filed an amended return, a short-year return next to a full-year one, or when the same return was published in two releases. For the one return per EIN that the matched table uses, see "Which return is used" below, or use `community_benefit_gap_2022.parquet`, which has already made the choice.

## Identity, timing and provenance

| Column | Source on the return | Notes |
|---|---|---|
| `ein` | Filer EIN | 9 characters, text. The join key to the crosswalk and the matched table. |
| `organization_name` | Filer business name | Mixed case or all capitals. Search case-insensitively. |
| `filer_city`, `filer_state` | Filer address | The filing organization's address. For a multi-hospital system this is the parent's office, not each facility. |
| `tax_period_begin`, `tax_period_end` | Return header | The fiscal period the return covers. |
| `tax_year` | `TaxYr` | The year in which the period begins. A tax year 2022 return from a July-to-June filer covers July 2022 to June 2023. |
| `return_version` | `returnVersion` attribute | For example `2022v5.0`. |
| `object_id` | IRS e-file object id | Text. The return's file name in the IRS release, and the key for a ProPublica link. |
| `return_ts` | Return timestamp | When the return was e-filed. A timestamp with time zone; cast it to text (`return_ts::VARCHAR`) if your client cannot display it. |
| `amended_return` | Amended-return indicator | True when the return is marked amended. |
| `release_year`, `batch_id` | Added at ingest | The IRS e-file release year (2023 to 2026) and the ZIP the return was found in. |

## Form 990 totals

| Column | Notes |
|---|---|
| `total_revenue` | Current-year total revenue (Form 990 Part VIII line 12). |
| `total_expenses` | Current-year total expenses (Part IX line 25). The denominator for community benefit as a share of expenses. |

## Schedule H Part I, line 7

Part I line 7 has eleven rows, 7a to 7k. Each row has columns (a) number of activities, (b) persons served, (c) total community benefit expense, (d) direct offsetting revenue, (e) net community benefit expense, and (f) percent of total expense. On the form, (e) = (c) − (d).

For every row the bundle carries three columns: the bare name is column (e), `_gross` is column (c), `_offset_revenue` is column (d).

| Column (e) | Line | What the line is |
|---|---|---|
| `financial_assistance_at_cost` | **7a** | Financial assistance at cost. The IRS figure shown next to CMS S-10 line 23. |
| `unreimbursed_medicaid` | 7b | Medicaid: cost of services less the revenue received. |
| `unreimbursed_other_means_tested` | 7c | Costs of other means-tested government programs. |
| `total_financial_assistance` | 7d | Total of 7a to 7c. |
| `community_health_services` | 7e | Community health improvement services and community benefit operations. |
| `health_professions_education` | 7f | Health professions education. |
| `subsidized_health_services` | 7g | Subsidized health services. |
| `research` | 7h | Research. |
| `cash_and_in_kind_contributions` | 7i | Cash and in-kind contributions for community benefit. |
| `total_other_benefits` | 7j | Total of 7e to 7i. |
| `total_community_benefit` | **7k** | Total of 7d and 7j. |

So line 7a is three columns: `financial_assistance_at_cost_gross` (c), `financial_assistance_at_cost_offset_revenue` (d), `financial_assistance_at_cost` (e).

`total_community_benefit_pct` is line 7k column (f), stored as a fraction (0.15 means 15%).

A blank cell on the return is null here. A reported 0 is 0. Do not treat the two as the same: a null column (d) means the filer left it blank; a 0 means the filer entered zero.

### Line 7a and provider taxes

The Schedule H instructions (Worksheet 1) say that a filer enters Medicaid or provider taxes in the line 7a cost when payments from an uncompensated care pool or DSH program in its state are intended primarily to offset the cost of financial assistance, and reports that pool revenue as direct offsetting revenue in column (d). When the payments are primarily to offset the cost of Medicaid services, both go to line 7b. When state law does not make the purpose clear, the instructions allow a proportional split. This is a classification the instructions permit, it depends on the state, and the worksheet is not part of the public return. It is one reason line 7a can differ from CMS S-10 line 23, where provider taxes are netted on a separate line (line 5).

## Other Schedule H fields

| Column | Source | Notes |
|---|---|---|
| `bad_debt_expense` | Part III line 2 | Bad debt expense. Reported separately from financial assistance. |
| `hospital_facility_count` | Part V Section A | Number of hospital facilities the return covers. Useful next to `ccn_count` on the matched table. |

## Which return is used per EIN

The matched table picks one return per EIN in this order:

1. a full-year return (at least 330 days) over a short-year one;
2. the latest tax period end;
3. the latest e-file timestamp, so an amended return is used over the original;
4. the newest release year.

To reproduce it:

```sql
SELECT * REPLACE (return_ts::VARCHAR AS return_ts)
FROM read_parquet('https://troveproject.com/data/schedule_h_2022.parquet')
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY ein
  ORDER BY (date_diff('day', tax_period_begin, tax_period_end) < 330),
           tax_period_end DESC, return_ts DESC, release_year DESC
) = 1;
```

To see every return on file for one EIN:

```sql
SELECT ein, organization_name, tax_period_begin, tax_period_end,
       release_year, batch_id, amended_return, return_ts::VARCHAR AS e_filed, object_id,
       financial_assistance_at_cost_gross AS line_7a_c,
       financial_assistance_at_cost_offset_revenue AS line_7a_d,
       financial_assistance_at_cost AS line_7a_e
FROM read_parquet('https://troveproject.com/data/schedule_h_2022.parquet')
WHERE ein = '112241326'
ORDER BY return_ts;
```

## How the totals relate

```
7d = 7a + 7b + 7c
7j = 7e + 7f + 7g + 7h + 7i
7k = 7d + 7j
```

When someone quotes a hospital's "community benefit", it is usually line 7k. "Charity care" or "financial assistance" usually means line 7a. A teaching hospital can show a small 7a and a large 7k because of education and research. Do not set line 7k next to CMS S-10 line 23; they are different in scope.

## Coverage

Tax year 2022 only (periods beginning in 2022). Returns were located by opening every ZIP in the IRS e-file releases for 2023 through 2026 and reading each return's own tax year, not by trusting the IRS index files. Most tax year 2022 returns are in the 2023 and 2024 releases; a small number, mostly amended returns, are in 2025. Paper filers and returns the IRS has not released are not here.

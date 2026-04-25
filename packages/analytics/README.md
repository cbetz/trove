# analytics

Composed analytical queries over the `hcris`, `form990`, and `crosswalk` outputs.

## `community_benefit_gap()`

The headline insight. Joins HCRIS Worksheet S-10 (CCN-keyed, per-facility) to IRS 990 Schedule H (EIN-keyed, per parent system) via the crosswalk, summing HCRIS facility numbers across all CCNs that share an EIN, then comparing what each form reports.

```python
from hcris import parse_zip as parse_hcris, pivot_wide
from form990 import parse_zip as parse_990
from crosswalk import load_seed
from analytics import community_benefit_gap

hcris = pivot_wide(parse_hcris("data/raw/hcris/HOSP10FY2023.zip"))
sched_h = parse_990("data/raw/form990/2024_TEOS_XML_01A.zip")
cw = load_seed()
gap = community_benefit_gap(hcris, sched_h, cw)
gap.head(10)
```

Returns one row per matched hospital system, sorted by absolute `charity_gap` (HCRIS charity care minus 990 financial assistance at cost). For `2024_TEOS_XML_01A` alone, Hennepin Healthcare surfaces with **+$30M**: $64.3M reported as charity-care cost on HCRIS S-10 versus $34.4M reported as financial assistance on 990 Schedule H Part I 7a.

## Caveats

- **Time alignment:** HCRIS fiscal years don't always match 990 tax years. Latest 990 per EIN by `tax_period_end` wins; mismatch by up to ~12 months is normal.
- **Definitional differences:** "Charity care at cost" on HCRIS S-10 and "financial assistance at cost" on Schedule H Part I line 7a are *intended* to be the same concept, but the instructions diverge — Schedule H may exclude Medicaid shortfall, partial patient payments are netted differently, and CCR application varies. Treat the gap as a flag for review, not a definitive accusation.
- **Coverage:** Limited to hospital systems whose EIN appears in both CBI's crosswalk and the parsed Schedule H corpus. Across one ZIP this is dozens of systems; across all 12 release ZIPs it's hundreds.

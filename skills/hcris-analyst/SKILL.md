---
name: hcris-analyst
description: Query CMS Medicare Cost Reports (HCRIS) and IRS Form 990 Schedule H filings. Answer questions about hospital financials, beds, staffing, community benefit, peer comparisons, and the meaning of specific cost-report worksheets/lines/columns.
---

# hcris-analyst

**Status:** placeholder. Will be implemented in M5 once the underlying `hcris`, `form990`, `crosswalk`, and `analytics` packages are functional.

Planned capabilities:

- Field glossary lookup (e.g., "what does Worksheet S-3 line 14 column 2 mean?")
- Peer cohort construction (size, geography, teaching status, ownership)
- Margin / occupancy / capex trend queries
- Community-benefit gap detection (Schedule H vs. HCRIS S-10)
- Natural-language → DuckDB SQL over the published Parquet bundles

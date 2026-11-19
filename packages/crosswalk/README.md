# crosswalk

CCN ↔ EIN crosswalk linking CMS Medicare Cost Reports (keyed by CCN) to IRS Form 990 filings (keyed by EIN). It is what lets a hospital's cost report be set next to its Form 990 Schedule H.

```python
from crosswalk import load_seed
cw = load_seed()  # 3,523 rows, 2,385 unique EINs
cw[cw["ccn"] == "330101"]   # NY-Presbyterian → EIN 133957095
```

## Source and provenance

The bundled `cbi.parquet` is derived from Community Benefit Insight's hospital list (`https://www.communitybenefitinsight.org/api/get_hospitals.php`), itself a join of CMS HCRIS, IRS Form 990 e-files, and the AHA Annual Survey produced by RTI International with funding from the Robert Wood Johnson Foundation. The bundled file is the **Dec 6 2024** vintage shown in the `vintage` column.

The factual codes (CCN, EIN) and address fields are derived from public-domain US government sources. We redistribute the curated mapping under MIT with attribution; if/when the CBI API goes offline, the bundled Parquet is durable. Refresh from source with `crosswalk.refresh_from_cbi(out_path)` while it's reachable.

Source: Community Benefit Insight hospital list (RTI International / Robert Wood Johnson Foundation), December 2024 vintage.

## Coverage

3,523 nonprofit hospital facilities, 2,385 unique parent EINs. Hospitals that don't match cleanly (M&A, recent CCN issuance, DBA mismatches) need to be reconciled by hand for now — a future fuzzy-match-against-IRS-BMF pass is on the roadmap.

## Schema

| Column | Type | Notes |
|---|---|---|
| `ccn` | string | 6-char zero-padded CMS Certification Number |
| `ein` | string | 9-char zero-padded Employer Identification Number |
| `hospital_name` | string | Parent organization or facility name |
| `hospital_name_cost_report` | string | Name as written on the HCRIS RPT |
| `street_address`, `city`, `state`, `zip_code`, `county`, `county_fips` | string | Mailing address + 5-digit FIPS county |
| `bed_count` | Int64 | Reported bed count |
| `bed_size_band` | string | `<100 beds`, `100–299 beds`, `>299 beds` |
| `urban`, `children_hospital`, `teaching_hospital`, `church_affiliated` | boolean | Categorical flags |
| `source` | string | `cbi` |
| `vintage` | string | Date of the source snapshot |

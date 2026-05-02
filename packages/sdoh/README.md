# sdoh

Social Determinants of Health enrichments for trove. v0.1 ships county-level Area Deprivation Index (ADI) scores derived from the University of Wisconsin Neighborhood Atlas's block-group ADI release.

## Licensing

UW's terms restrict redistribution of the **raw block-group ADI tables**. trove does not redistribute those — `data/raw/adi/` is gitignored and you must download the source CSV yourself from `https://www.neighborhoodatlas.medicine.wisc.edu/` (registration + click-through agreement required).

What trove **does** redistribute is **derived county-level aggregates** computed from that raw file (one number per county, not 242k block-group rows). Per-county ADI summaries are routinely published in the literature with citation; we follow that convention.

**Citation:** Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458.

## Usage

```python
from sdoh import county_adi_from_block_group

adi = county_adi_from_block_group("data/raw/adi/US_2023_ADI_Census_Block_Group_v4_0_1.csv")
adi.head()
#   county_fips  adi_natrank  adi_state_decile  block_group_count
# 0       01001         53.0               5.0                 12
# 1       01003         48.0               4.0                 64
```

The output is one row per 5-digit county FIPS, with median `ADI_NATRANK` (national percentile, 1-100), median `ADI_STATERNK` (state decile, 1-10), and the count of underlying block groups (so you can filter low-coverage counties if needed).

Suppression codes (`GQ`, `PH`, `GQ-PH`, `QDI`) in the source are treated as NaN before aggregation.

## Why county and not ZIP

The raw ADI file is keyed by Census block group. Aggregating to county is a clean lossless join (block-group FIPS includes county FIPS as a prefix). Aggregating to ZIP requires a separate ZIP-to-block-group population crosswalk — a meaningful additional dependency for marginal precision improvement on a hospital-scale enrichment. v2 may add ZIP-level resolution; v1 is intentionally county-only.

## Caveats

- **County aggregation loses within-county variation.** A hospital in a high-deprivation neighborhood of an otherwise-affluent county shows up with the county median, not its actual neighborhood. For most hospitals the county aggregate is reasonable; for urban counties with sharp socioeconomic gradients (NYC, LA), it's a coarse approximation.
- **Aggregating ranks is not the same as ranking aggregates.** The county "median ADI_NATRANK" is the median of national-percentile ranks of the county's block groups, not the percentile of the county itself among all counties. Treat it as a *typical block-group score for this county*, not as a single composite county rank.
- **Suppressed block groups** are excluded before aggregation. Counties with high suppression rates (mostly group-quarters or low-population areas) may have unstable aggregates.

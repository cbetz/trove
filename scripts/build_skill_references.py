"""Render skill reference docs from the canonical dictionary YAML.

Outputs:
- ``skills/hcris-analyst/references/dictionary.md`` — every HCRIS variable
  with its (worksheet, line, column) and description, grouped by
  worksheet so it's scannable when the skill needs to look something up.

Re-run after editing ``packages/hcris/src/hcris/dictionaries/2552-10.yaml``.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from hcris import load_dictionary

OUT = Path("skills/hcris-analyst/references/dictionary.md")


def main() -> None:
    variables = load_dictionary()
    by_worksheet: dict[str, list] = defaultdict(list)
    for v in variables:
        by_worksheet[v.wksht_cd].append(v)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        f.write("# HCRIS 2552-10 field dictionary\n\n")
        f.write(
            "Every variable trove exposes from the Medicare Cost Report Hospital form, "
            "with the canonical (worksheet, line, column) source and a short description. "
            "Generated from `packages/hcris/src/hcris/dictionaries/2552-10.yaml`.\n\n"
        )
        f.write(
            "**Pivoted Parquet bundles:** "
            "`https://troveproject.com/data/hcris_2022_wide.parquet` and "
            "`https://troveproject.com/data/hcris_2023_wide.parquet` "
            "(CMS fiscal-year files, keyed on the date the reporting period begins; "
            "one row per cost report, every variable below as a named column, plus "
            "`hcris_file_fy`, `rpt_rec_num`, `prvdr_num`, `fy_bgn_dt`, `fy_end_dt`, "
            "`rpt_stus_cd`, `rpt_status`, `proc_dt` and `s10_filed`).\n\n"
        )
        f.write(
            "A null value means the cell is blank or zero on the form: CMS's numeric "
            "file stores no zeros. It is not a reported $0.\n\n"
        )
        f.write(f"Total: **{len(variables)} variables** across {len(by_worksheet)} worksheets.\n\n")

        for wksht in sorted(by_worksheet):
            f.write(f"## Worksheet `{wksht}`\n\n")
            aliases = sorted({a for v in by_worksheet[wksht] for a in v.wksht_cd_aliases})
            if aliases:
                f.write(
                    f"Also read from worksheet code {', '.join(f'`{a}`' for a in aliases)} "
                    "at the same line and column. CMS files Worksheet S-10 as `S100000` "
                    "for cost reporting periods beginning before 2022-10-01 and S-10 "
                    "Part I as `S100001` after; the bundles map both to the variables "
                    "below.\n\n"
                )
            f.write("| Variable | Line | Column | Source | Type | Description |\n")
            f.write("|----------|------|--------|--------|------|-------------|\n")
            for v in by_worksheet[wksht]:
                line = v.line_num.lstrip("0") or "0"
                if v.line_num_end:
                    end = v.line_num_end.lstrip("0") or "0"
                    line = f"{line}–{end} ({v.aggregation})"
                col = v.clmn_num.lstrip("0") or "0"
                desc = (v.description or "").replace("|", r"\|")
                f.write(f"| `{v.name}` | {line} | {col} | {v.source} | {v.type} | {desc} |\n")
            f.write("\n")

    print(f"  → {OUT} ({len(variables)} variables, {OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

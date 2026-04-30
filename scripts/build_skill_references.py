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
            "**Pivoted Parquet bundle:** "
            "`https://troveproject.com/data/hcris_2023_wide.parquet` "
            "(one row per hospital, every variable below as a named column).\n\n"
        )
        f.write(f"Total: **{len(variables)} variables** across {len(by_worksheet)} worksheets.\n\n")

        for wksht in sorted(by_worksheet):
            f.write(f"## Worksheet `{wksht}`\n\n")
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

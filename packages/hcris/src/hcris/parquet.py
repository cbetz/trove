"""Write parsed HCRIS DataFrames to Parquet partitioned by fiscal year."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from hcris.parse import HcrisFiles


def write_parquet(
    files: HcrisFiles,
    year: int,
    out_dir: Path | str = "data/parquet/hcris",
) -> dict[str, Path]:
    """Write ``files`` to ``{out_dir}/{rpt,nmrc,alpha}/year={year}/part.parquet``.

    Returns a mapping from table name to the written path.
    """
    root = Path(out_dir)
    written: dict[str, Path] = {}
    tables = {"rpt": files.rpt, "nmrc": files.nmrc, "alpha": files.alpha}
    for name, df in tables.items():
        path = root / name / f"year={year}" / "part.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
        written[name] = path
    return written

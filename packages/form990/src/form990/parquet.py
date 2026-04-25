"""Write parsed Schedule H DataFrames to Parquet partitioned by tax year."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def write_parquet(
    df: pd.DataFrame,
    tax_year: int,
    out_dir: Path | str = "data/parquet/form990",
) -> Path:
    """Write to ``{out_dir}/schedule_h/year={tax_year}/part.parquet`` and return its path.

    The partition key is named ``year`` (not ``tax_year``) to avoid colliding
    with the ``tax_year`` column already in the DataFrame when pyarrow does
    Hive-partition detection on read.
    """
    path = Path(out_dir) / "schedule_h" / f"year={tax_year}" / "part.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path)
    return path

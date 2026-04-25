from pathlib import Path

import pyarrow.parquet as pq
from form990.parquet import write_parquet
from form990.parse import parse_zip


def test_write_parquet_roundtrip(tmp_path: Path, fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory())
    out = write_parquet(df, tax_year=2022, out_dir=tmp_path)
    assert out.exists()
    assert out.parent.name == "year=2022"
    assert out.parent.parent.name == "schedule_h"
    table = pq.read_table(out)
    assert table.num_rows == len(df)

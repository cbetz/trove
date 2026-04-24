from pathlib import Path

import pyarrow.parquet as pq
from hcris.parquet import write_parquet
from hcris.parse import parse_zip


def test_partitioned_layout(tmp_path: Path, fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    paths = write_parquet(files, year=2023, out_dir=tmp_path)

    for name in ("rpt", "nmrc", "alpha"):
        path = paths[name]
        assert path.exists()
        assert path.parent.name == "year=2023"
        assert path.parent.parent.name == name


def test_roundtrip_preserves_row_counts(tmp_path: Path, fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    paths = write_parquet(files, year=2023, out_dir=tmp_path)
    assert pq.read_table(paths["rpt"]).num_rows == len(files.rpt)
    assert pq.read_table(paths["nmrc"]).num_rows == len(files.nmrc)
    assert pq.read_table(paths["alpha"]).num_rows == len(files.alpha)

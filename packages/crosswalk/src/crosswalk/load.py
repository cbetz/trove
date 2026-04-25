"""Load the bundled CCN <-> EIN crosswalk."""

from __future__ import annotations

from importlib.resources import files as resource_files

import pandas as pd


def load_seed() -> pd.DataFrame:
    """Return the bundled CBI crosswalk DataFrame.

    Frozen at the Dec 6 2024 CBI snapshot. Re-pull with ``refresh_from_cbi`` if
    the source is updated (it isn't currently). 3,523 rows, 2,385 unique EINs.
    """
    path = resource_files("crosswalk.data") / "cbi.parquet"
    return pd.read_parquet(path)

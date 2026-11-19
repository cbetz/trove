"""Load the semantic field dictionary for a HCRIS form."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files as resource_files
from typing import Literal

import yaml

Source = Literal["nmrc", "alpha"]


@dataclass(frozen=True)
class Variable:
    """A single entry in the field dictionary."""

    name: str
    source: Source
    type: str
    wksht_cd: str
    line_num: str
    clmn_num: str
    description: str
    line_num_end: str | None = None
    aggregation: str | None = None
    # Other worksheet codes that carry the same cell at the same line/column.
    # CMS renumbered Worksheet S-10 in Transmittal 18: it is ``S100000`` for cost
    # reporting periods beginning before 2022-10-01 and ``S100001`` (S-10 Part I)
    # after. A report uses exactly one of them; if one ever carried both, the
    # resolver keeps the primary code only (and warns) rather than adding them.
    wksht_cd_aliases: tuple[str, ...] = ()

    @property
    def wksht_cds(self) -> tuple[str, ...]:
        """Every worksheet code this variable resolves from, primary first."""
        return (self.wksht_cd, *self.wksht_cd_aliases)


def load_dictionary(form: str = "2552-10") -> tuple[Variable, ...]:
    """Load and validate the dictionary for ``form``. Returns an immutable tuple."""
    path = resource_files("hcris.dictionaries") / f"{form}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    variables = tuple(_parse_variable(v) for v in raw["variables"])
    _validate(variables)
    return variables


def _parse_variable(raw: dict) -> Variable:
    end = raw.get("line_num_end")
    return Variable(
        name=raw["name"],
        source=raw["source"],
        type=raw["type"],
        wksht_cd=raw["wksht_cd"],
        line_num=_pad(raw["line_num"]),
        clmn_num=_pad(raw["clmn_num"]),
        description=raw.get("description", ""),
        line_num_end=_pad(end) if end is not None else None,
        aggregation=raw.get("aggregation"),
        wksht_cd_aliases=tuple(str(a) for a in raw.get("wksht_cd_aliases", ())),
    )


def _pad(v: int | str) -> str:
    """Zero-pad integer line/column codes to the 5-char strings CMS emits."""
    if isinstance(v, int):
        return f"{v:05d}"
    return str(v)


def _validate(variables: tuple[Variable, ...]) -> None:
    names = [v.name for v in variables]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise ValueError(f"duplicate variable name(s) in dictionary: {sorted(dupes)}")
    for v in variables:
        if v.source not in ("nmrc", "alpha"):
            raise ValueError(f"variable {v.name!r}: source must be 'nmrc' or 'alpha'")
        if v.wksht_cd in v.wksht_cd_aliases:
            raise ValueError(f"variable {v.name!r}: wksht_cd_aliases repeats the primary wksht_cd")
        if v.line_num_end is not None and v.aggregation is None:
            raise ValueError(f"variable {v.name!r}: line_num_end requires aggregation (e.g. 'sum')")

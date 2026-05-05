"""Tests for fda_sba.scrape parsing logic."""

from __future__ import annotations

from pathlib import Path

import pytest
from fda_sba.scrape import (
    _appl_no_from_label_url,
    _appl_type,
    _drugs_at_fda_url,
    scrape_nme_year,
)


@pytest.fixture
def fda_year_page(tmp_path: Path) -> Path:
    """Synthetic FDA novel-drug-approvals-style table."""
    html_doc = """<html><body>
    <table>
      <thead><tr><th>No.</th><th>Drug Name</th><th>Active Ingredient</th>
      <th>Approval Date</th><th>FDA-approved use</th></tr></thead>
      <tbody>
        <tr>
          <td>50.</td>
          <td><a href="https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/761315s000lbl.pdf">Alhemo</a></td>
          <td>concizumab-mtci</td>
          <td>12/20/2024</td>
          <td>For routine prophylaxis to prevent bleeding in hemophilia A and B<br>
          <a href="/node/366301">Drug Trials Snapshot</a></td>
        </tr>
        <tr>
          <td>49.</td>
          <td><a href="https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/218710s000lbl.pdf">Alyftrek</a></td>
          <td>vanzacaftor, tezacaftor, and deutivacaftor</td>
          <td>12/20/2024</td>
          <td>For the treatment of cystic fibrosis</td>
        </tr>
      </tbody>
    </table>
    </body></html>"""
    cache = tmp_path / "data" / "raw" / "fda"
    cache.mkdir(parents=True)
    (cache / "nme_2024.html").write_bytes(html_doc.encode("utf-8"))
    return tmp_path / "data" / "raw" / "fda"


def test_appl_no_extracted_from_label_url() -> None:
    assert _appl_no_from_label_url(
        "https://www.accessdata.fda.gov/drugsatfda_docs/label/2024/761315s000lbl.pdf"
    ) == "761315"
    assert _appl_no_from_label_url("https://example.com/no-match.pdf") is None
    assert _appl_no_from_label_url(None) is None


def test_appl_type_inferred() -> None:
    assert _appl_type("761315") == "BLA"
    assert _appl_type("218710") == "NDA"
    assert _appl_type(None) is None


def test_drugs_at_fda_url() -> None:
    assert _drugs_at_fda_url("218710") == (
        "https://www.accessdata.fda.gov/scripts/cder/daf/"
        "index.cfm?event=overview.process&ApplNo=218710"
    )
    assert _drugs_at_fda_url(None) is None


def test_scrape_year_returns_two_rows(fda_year_page: Path) -> None:
    df = scrape_nme_year(2024, cache_dir=fda_year_page)
    assert len(df) == 2
    assert set(df["drug_name"]) == {"Alhemo", "Alyftrek"}


def test_scrape_extracts_application_metadata(fda_year_page: Path) -> None:
    df = scrape_nme_year(2024, cache_dir=fda_year_page).set_index("drug_name")
    assert df.loc["Alhemo", "application_number"] == "761315"
    assert df.loc["Alhemo", "application_type"] == "BLA"
    assert df.loc["Alyftrek", "application_number"] == "218710"
    assert df.loc["Alyftrek", "application_type"] == "NDA"
    assert "scripts/cder/daf" in df.loc["Alhemo", "drugs_at_fda_url"]


def test_indication_strips_snapshot_text(fda_year_page: Path) -> None:
    df = scrape_nme_year(2024, cache_dir=fda_year_page).set_index("drug_name")
    assert "Drug Trials Snapshot" not in df.loc["Alhemo", "indication"]
    assert "hemophilia" in df.loc["Alhemo", "indication"].lower()


def test_snapshot_url_resolved(fda_year_page: Path) -> None:
    import pandas as pd

    df = scrape_nme_year(2024, cache_dir=fda_year_page).set_index("drug_name")
    assert df.loc["Alhemo", "trials_snapshot_url"].startswith("https://www.fda.gov/")
    alyftrek_url = df.loc["Alyftrek", "trials_snapshot_url"]
    assert pd.isna(alyftrek_url) or alyftrek_url in (None, "")

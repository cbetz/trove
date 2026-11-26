"""Synthetic 990 XML fixtures for form990 tests."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest


def _filing_xml(
    *,
    ein: str,
    name: str,
    tax_period_begin: str,
    tax_period_end: str,
    tax_year: int,
    schedule_h: bool = True,
    return_type: str = "990",
    total_revenue: int = 1_000_000_000,
    total_expenses: int = 950_000_000,
    fa_at_cost_net: int = 50_000_000,
    fa_at_cost_gross: int | None = None,
    fa_at_cost_offset: int | None = None,
    return_ts: str = "2023-11-15T10:00:00-05:00",
    amended: bool = False,
    medicaid_net: int = 30_000_000,
    total_community_benefit_net: int = 100_000_000,
    total_community_benefit_pct: str = "0.10500",
    bad_debt: int = 5_000_000,
    facility_count: int = 1,
) -> str:
    sch_h_block = ""
    gross = (
        ""
        if fa_at_cost_gross is None
        else f"<TotalCommunityBenefitExpnsAmt>{fa_at_cost_gross}</TotalCommunityBenefitExpnsAmt>"
    )
    offset = (
        ""
        if fa_at_cost_offset is None
        else f"<DirectOffsettingRevenueAmt>{fa_at_cost_offset}</DirectOffsettingRevenueAmt>"
    )
    amended_block = "<AmendedReturnInd>X</AmendedReturnInd>" if amended else ""
    if schedule_h:
        sch_h_block = f"""
    <IRS990ScheduleH documentId="RetDoc1">
      <FinancialAssistanceAtCostTyp>
        {gross}{offset}
        <NetCommunityBenefitExpnsAmt>{fa_at_cost_net}</NetCommunityBenefitExpnsAmt>
      </FinancialAssistanceAtCostTyp>
      <UnreimbursedMedicaidGrp>
        <NetCommunityBenefitExpnsAmt>{medicaid_net}</NetCommunityBenefitExpnsAmt>
      </UnreimbursedMedicaidGrp>
      <TotalCommunityBenefitsGrp>
        <NetCommunityBenefitExpnsAmt>{total_community_benefit_net}</NetCommunityBenefitExpnsAmt>
        <TotalExpensePct>{total_community_benefit_pct}</TotalExpensePct>
      </TotalCommunityBenefitsGrp>
      <BadDebtExpenseAmt>{bad_debt}</BadDebtExpenseAmt>
      <HospitalFacilitiesCnt>{facility_count}</HospitalFacilitiesCnt>
    </IRS990ScheduleH>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Return xmlns="http://www.irs.gov/efile" returnVersion="2022v5.0">
  <ReturnHeader>
    <ReturnTs>{return_ts}</ReturnTs>
    <TaxPeriodBeginDt>{tax_period_begin}</TaxPeriodBeginDt>
    <TaxPeriodEndDt>{tax_period_end}</TaxPeriodEndDt>
    <ReturnTypeCd>{return_type}</ReturnTypeCd>
    <TaxYr>{tax_year}</TaxYr>
    <Filer>
      <EIN>{ein}</EIN>
      <BusinessName>
        <BusinessNameLine1Txt>{name}</BusinessNameLine1Txt>
      </BusinessName>
      <USAddress>
        <CityNm>SPRINGFIELD</CityNm>
        <StateAbbreviationCd>IL</StateAbbreviationCd>
      </USAddress>
    </Filer>
  </ReturnHeader>
  <ReturnData>
    <IRS990 documentId="RetDoc0">
      {amended_block}
      <CYTotalRevenueAmt>{total_revenue}</CYTotalRevenueAmt>
      <CYTotalExpensesAmt>{total_expenses}</CYTotalExpensesAmt>
    </IRS990>{sch_h_block}
  </ReturnData>
</Return>"""


@pytest.fixture
def fake_zip_factory(tmp_path: Path):
    """Build a synthetic IRS bulk-XML ZIP with a configurable mix of filings."""

    def build(
        filings: list[dict] | None = None,
        zip_name: str = "fake_TEOS_XML_01A.zip",
    ) -> Path:
        if filings is None:
            # Default: two hospitals + one non-hospital control
            filings = [
                {"ein": "111111111", "name": "MEMORIAL HOSPITAL", "tax_year": 2022},
                {
                    "ein": "222222222",
                    "name": "RIVER HOSPITAL",
                    "tax_year": 2022,
                    "total_community_benefit_net": 75_000_000,
                },
                {
                    "ein": "333333333",
                    "name": "RED CROSS LOCAL",
                    "tax_year": 2022,
                    "schedule_h": False,
                },
            ]
        path = tmp_path / zip_name
        with zipfile.ZipFile(path, "w") as zf:
            for f in filings:
                opts = {
                    "tax_period_begin": "2022-01-01",
                    "tax_period_end": "2022-12-31",
                    **f,
                }
                # ``member`` overrides the ZIP member name (the IRS uses
                # ``{BATCH}/{OBJECT_ID}_public.xml``); default is the EIN.
                member = opts.pop("member", f"{f['ein']}_public.xml")
                xml = _filing_xml(**opts)
                zf.writestr(member, xml)
        return path

    return build

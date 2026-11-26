"""Schedule H field map: XPath-to-variable extraction.

Each Part I line-7 group has the shape ``Form990SchHPartIGroup1Type`` with
child elements ``TotalCommunityBenefitExpnsAmt`` (gross),
``DirectOffsettingRevenueAmt``, ``NetCommunityBenefitExpnsAmt`` (net), and
``TotalExpensePct``. The headline number for cross-reference against HCRIS
Worksheet S-10 charity care is the NET amount on **line 7a**
(``FinancialAssistanceAtCostTyp``); line 7k
(``TotalCommunityBenefitsGrp``) is the broader Schedule H total community
benefit roll-up.
"""

from __future__ import annotations

from typing import Final

# Element name (under IRS990ScheduleH) → trove variable name.
# The bare variable name is the Net Community Benefit Expense (column (e) on the
# form). Columns (c) and (d) are extracted alongside it with the suffixes below,
# so line 7a yields ``financial_assistance_at_cost`` (e),
# ``financial_assistance_at_cost_gross`` (c) and
# ``financial_assistance_at_cost_offset_revenue`` (d). On the form (e) = (c) - (d).
PART_I_LINE_GROUPS: Final[dict[str, str]] = {
    "FinancialAssistanceAtCostTyp": "financial_assistance_at_cost",
    "UnreimbursedMedicaidGrp": "unreimbursed_medicaid",
    "UnreimbursedCostsGrp": "unreimbursed_other_means_tested",
    "TotalFinancialAssistanceTyp": "total_financial_assistance",
    "CommunityHealthServicesGrp": "community_health_services",
    "HealthProfessionsEducationGrp": "health_professions_education",
    "SubsidizedHealthServicesGrp": "subsidized_health_services",
    "ResearchGrp": "research",
    "CashAndInKindContributionsGrp": "cash_and_in_kind_contributions",
    "TotalOtherBenefitsGrp": "total_other_benefits",
    "TotalCommunityBenefitsGrp": "total_community_benefit",
}

# Suffix → child element, for Part I columns (c) and (d).
GROSS_SUFFIX: Final[str] = "_gross"
OFFSET_SUFFIX: Final[str] = "_offset_revenue"
PART_I_EXTRA_COLUMNS: Final[dict[str, str]] = {
    GROSS_SUFFIX: "TotalCommunityBenefitExpnsAmt",
    OFFSET_SUFFIX: "DirectOffsettingRevenueAmt",
}

# All output columns the parser produces, in the order they appear in the row dict.
OUTPUT_COLUMNS: Final[tuple[str, ...]] = (
    # Identity
    "ein",
    "organization_name",
    "tax_period_begin",
    "tax_period_end",
    "tax_year",
    "return_version",
    # Main 990 financials (Part VIII line 12, Part IX line 25)
    "total_revenue",
    "total_expenses",
    # Schedule H Part I line 7 net amounts
    *PART_I_LINE_GROUPS.values(),
    # Schedule H headline ratio
    "total_community_benefit_pct",
    # Schedule H Part III
    "bad_debt_expense",
    # Schedule H Part V Section A
    "hospital_facility_count",
    # Provenance: the IRS object id is the bulk ZIP member name
    # (``{object_id}_public.xml``) and the key for deep links to the filing.
    "object_id",
    "return_ts",
    "amended_return",
    # Filer address from the return header (the filing organization, which for a
    # multi-hospital system is the parent's office, not each facility).
    "filer_city",
    "filer_state",
    # Schedule H Part I line 7 columns (c) gross expense and (d) direct offsetting revenue
    *(f"{v}{GROSS_SUFFIX}" for v in PART_I_LINE_GROUPS.values()),
    *(f"{v}{OFFSET_SUFFIX}" for v in PART_I_LINE_GROUPS.values()),
)

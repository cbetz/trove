# The Charity Care Gap Index — TY2022

Every nonprofit U.S. hospital reports the cost of the free/discounted care it gave patients who couldn't pay to **two** federal regulators: to CMS on Worksheet S-10 of the Medicare Cost Report, and to the IRS on Schedule H (Part I, line 7a) of Form 990. The two numbers describe the same underlying activity. They are frequently far apart.

This is the **credibility-hardened** ranking derived from the full [gap dataset](community_benefit_gap_2022.csv) — the subset where the comparison is genuinely apples-to-apples, so the numbers survive scrutiny. Each hospital below is:

- a **single reporting facility** (one CCN under one EIN — no multi-hospital roll-up hiding behind one name);
- **period-aligned** (the two filings' fiscal periods end within 1 month of each other — they cover the same year);
- **material** (both the CMS and IRS charity-care figures are at least $1M); and
- reporting **the same-scale entity** (the two forms' total expenses agree within 5%).

**The comparison is net-to-net.** The IRS figure is Schedule H Part I line 7a column (e) — *net* community benefit expense for financial assistance (financial assistance at cost, less direct offsetting revenue). The CMS figure is Worksheet S-10 cost of charity care, net of partial patient payments. Comparing net to net pre-empts the obvious objection that a gross figure was set against a net one. The two "net" definitions still aren't identical — Schedule H's offsetting revenue can include items S-10 doesn't subtract — so a residual difference is expected even for a perfectly-reporting hospital. **% is the difference as a share of the larger of the two figures.**

**99 hospitals** clear that bar. Of them, **22** report charity-care numbers to the two regulators that differ by more than 50%.

> A gap is **not** an accusation. The two forms have genuinely different definitions, cost-to-charge handling, and category boundaries, and a difference can be entirely legitimate. What this index does is make a long-known measurement inconsistency *checkable per hospital*, with a link to both source filings so you can see for yourself.

| # | Hospital | Told the IRS (990 Sch. H) | Told CMS (S-10) | Difference | % | 990 on ProPublica |
|--:|----------|--------------------------:|----------------:|-----------:|--:|-------------------|
| 1 | Yale New Haven Hospital | $113.1M | $35.6M | −$77.5M | 69% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646652) |
| 2 | Tampa General Hospital | $51.0M | $102.4M | +$51.3M | 50% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/593458145) |
| 3 | Greenwich Hospital | $23.6M | $4.0M | −$19.6M | 83% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646659) |
| 4 | Baptist Medical Center | $34.8M | $52.6M | +$17.8M | 34% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/590747311) |
| 5 | Western Regional Medical Center | $1.1M | $18.1M | +$16.9M | 94% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/320197974) |
| 6 | Lawrence & Memorial Hospital | $21.1M | $4.8M | −$16.3M | 77% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646704) |
| 7 | Cook Childrens Medical Center | $11.3M | $26.8M | +$15.5M | 58% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/752051646) |
| 8 | Bayfront Health St. Petersburg | $4.4M | $17.6M | +$13.2M | 75% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/845074208) |
| 9 | Bridgeport Hospital | $32.7M | $19.5M | −$13.2M | 40% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646554) |
| 10 | Boston Medical Center | $99.5M | $111.5M | +$12.0M | 11% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/43314093) |
| 11 | Beth Israel Deaconess Medical Center | $23.8M | $12.4M | −$11.5M | 48% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103881) |
| 12 | Southeastern Regional Medical Center | $6.6M | $17.5M | +$10.9M | 62% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/264572436) |
| 13 | Sharp Memorial Hospital | $6.6M | $16.9M | +$10.3M | 61% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/953782169) |
| 14 | Boca Raton Regional Hospital | $14.4M | $4.3M | −$10.1M | 70% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/591006663) |
| 15 | Grossmont Hospital | $6.0M | $15.3M | +$9.3M | 61% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/330449527) |
| 16 | Hamilton Medical Center | $16.9M | $7.8M | −$9.1M | 54% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/581519911) |
| 17 | Oroville Hospital | $8.8M | $1.1M | −$7.7M | 87% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/941634554) |
| 18 | Carilion Medical Center | $15.7M | $8.5M | −$7.2M | 46% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/540506332) |
| 19 | Sharp Chula Vista Medical Center | $5.1M | $11.1M | +$5.9M | 53% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/952367304) |
| 20 | St Bernards Medical Center | $10.0M | $15.8M | +$5.8M | 37% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/710290019) |
| 21 | North Mississippi Medical Center | $32.5M | $27.0M | −$5.5M | 17% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640662976) |
| 22 | Concord Hospital  Inc. | $2.0M | $7.3M | +$5.3M | 73% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/222594672) |
| 23 | Coxhealth | $25.5M | $20.9M | −$4.5M | 18% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/440577118) |
| 24 | Baptist Mem Hospital Desoto | $14.0M | $18.4M | +$4.5M | 24% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640682111) |
| 25 | Orlando Health South Lake Hospital | $12.9M | $17.1M | +$4.3M | 25% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/593322533) |
| 26 | Deaconess Hospital | $14.1M | $18.3M | +$4.2M | 23% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/350593390) |
| 27 | Baystate Medical Center | $7.3M | $3.9M | −$3.5M | 47% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42790311) |
| 28 | Mount Auburn Hospital | $5.6M | $2.2M | −$3.4M | 61% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103606) |
| 29 | Jupiter Medical Center | $6.4M | $3.1M | −$3.3M | 51% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/591460239) |
| 30 | University Of Vermont Medical Center | $12.0M | $9.1M | −$3.0M | 25% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/30219309) |
| 31 | Baptist Medical Center-Beaches | $2.5M | $5.4M | +$2.9M | 54% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/592980620) |
| 32 | Silver Cross Hospital | $2.5M | $5.2M | +$2.7M | 51% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/362174832) |
| 33 | Conway Hospital | $11.2M | $8.9M | −$2.3M | 21% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/570314381) |
| 34 | Lahey Clinic Hospital  Inc. | $7.2M | $9.3M | +$2.2M | 23% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42704686) |
| 35 | Saint Francis Hospital | $3.9M | $5.9M | +$2.0M | 34% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646813) |
| 36 | The Miriam Hospital | $8.7M | $6.7M | −$2.0M | 23% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/50258905) |
| 37 | Baptist Medical Ctr-Nassau | $1.4M | $3.3M | +$1.9M | 59% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/593234721) |
| 38 | Midwestern Regional Medical Center | $1.9M | $3.8M | +$1.9M | 50% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/362510771) |
| 39 | Deaconess Henderson Hospital | $1.6M | $3.5M | +$1.9M | 54% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/610461753) |
| 40 | Baptist Mem Hospital Memphis | $40.6M | $38.9M | −$1.8M | 4% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/620123940) |
| 41 | Southcoast Hospitals Group  Inc | $6.5M | $8.2M | +$1.7M | 21% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/222592333) |
| 42 | Baptist Mem Hospital Union County | $7.1M | $5.3M | −$1.7M | 24% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/630997281) |
| 43 | Blessing Hospital | $5.4M | $7.1M | +$1.7M | 24% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/370661183) |
| 44 | Nea Baptist Memorial Hospital | $6.5M | $4.8M | −$1.7M | 26% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/261214372) |
| 45 | Mclaren Macomb | $2.7M | $4.3M | +$1.6M | 37% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/381218516) |
| 46 | Shannon Medical Center | $19.5M | $20.9M | +$1.4M | 7% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/752559845) |
| 47 | Women & Infants Hospital | $2.2M | $3.6M | +$1.4M | 39% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/50258937) |
| 48 | Naples Community Hospital | $27.7M | $26.4M | −$1.3M | 5% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/590694358) |
| 49 | Ottawa Regional Hospital & Healthcar | $1.3M | $2.5M | +$1.2M | 48% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/362604009) |
| 50 | Beverly Hospital | $2.6M | $1.5M | −$1.2M | 44% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42121317) |
| 51 | Lowell General Hospital | $3.1M | $2.0M | −$1.1M | 36% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103590) |
| 52 | Emerson Hospital | $3.6M | $2.6M | −$1.1M | 29% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103565) |
| 53 | Cox Medical Center Branson | $6.0M | $5.0M | −$1.0M | 17% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/440584290) |
| 54 | Lawrence General Hospital | $3.7M | $4.7M | +$994K | 21% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103586) |
| 55 | Baptist Mem Hospital North Miss | $9.5M | $10.3M | +$861K | 8% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640772726) |
| 56 | St. Vincents Medical Center | $12.0M | $11.1M | −$819K | 7% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/832550272) |
| 57 | Champlain Valley Physicians Hospital | $1.0M | $1.9M | +$811K | 44% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/141338471) |
| 58 | Milford Regional Medical Center  Inc | $2.8M | $2.0M | −$810K | 29% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42103602) |
| 59 | Harnett Health System | $8.2M | $7.4M | −$768K | 9% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/560603898) |
| 60 | Newport Hospital | $1.0M | $1.8M | +$757K | 43% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/50258914) |
| 61 | Valley Regional Hospital | $1.9M | $1.2M | −$676K | 36% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/20222118) |
| 62 | The Griffin Hospital | $2.2M | $1.6M | −$651K | 29% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60647014) |
| 63 | Marshall Hospital | $2.2M | $1.5M | −$644K | 30% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/941450151) |
| 64 | Winchester Hospital | $3.2M | $2.6M | −$634K | 20% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42104434) |
| 65 | Rhode Island Hospital | $20.3M | $20.9M | +$620K | 3% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/50258954) |
| 66 | St. Lukes Nampa Medical Center | $3.8M | $4.3M | +$506K | 12% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/821162805) |
| 67 | Vassar Brothers Medical Center | $7.4M | $6.9M | −$497K | 7% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/141338586) |
| 68 | Karmanos Cancer Hospital | $1.7M | $1.3M | −$462K | 27% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/201649466) |
| 69 | Ephraim Mcdowell Reg Med Ctr | $2.5M | $2.1M | −$421K | 17% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/610492356) |
| 70 | Singing River Gulfport | $1.6M | $1.2M | −$420K | 26% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/851538878) |
| 71 | Central Vermont Hospital | $1.5M | $1.9M | +$388K | 21% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/222547186) |
| 72 | Tufts Medical Center | $3.0M | $2.6M | −$373K | 12% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/270440772) |
| 73 | Catholic Medical Center | $5.8M | $6.2M | +$365K | 6% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/20315693) |
| 74 | Norwegian American Hospital | $3.1M | $2.7M | −$356K | 12% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/361564290) |
| 75 | Pontotoc Health Services | $1.9M | $2.2M | +$334K | 15% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640751410) |
| 76 | Pih Health Good Samaritan Hospital | $5.1M | $4.8M | −$314K | 6% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/951656366) |
| 77 | Ms Baptist Medical Center | $12.6M | $13.0M | +$310K | 2% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640881013) |
| 78 | Baptist Mem Hospital Tipton County | $5.5M | $5.2M | −$290K | 5% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/621113167) |
| 79 | Middlesex Hospital | $1.6M | $1.8M | +$272K | 15% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/60646718) |
| 80 | Baptist Mem Hospital Huntingdon | $1.5M | $1.2M | −$257K | 17% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/621166050) |
| 81 | Cox-Monett Hospital | $1.7M | $1.5M | −$252K | 15% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/431656689) |
| 82 | Northern Dutchess Hospital | $1.1M | $1.3M | +$241K | 18% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/141338467) |
| 83 | Marion Regional Medical Center | $1.1M | $1.3M | +$210K | 16% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640926753) |
| 84 | Putnam Hospital Center | $1.4M | $1.2M | −$204K | 15% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/146019179) |
| 85 | Mclaren Central Michigan | $1.1M | $1.3M | +$202K | 15% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/381420304) |
| 86 | South Shore Hospital | $4.0M | $3.8M | −$193K | 5% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/42769210) |
| 87 | Bmh-Crittenden | $2.1M | $1.9M | −$179K | 9% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/823844150) |
| 88 | Monroe Health Services  Inc. | $2.0M | $2.2M | +$175K | 8% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/320583236) |
| 89 | Baptist Medical Center - Yazoo | $1.6M | $1.5M | −$174K | 11% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640844470) |
| 90 | Brockton Hospital  Inc. | $4.1M | $4.0M | −$166K | 4% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/222472997) |
| 91 | Baptist Mem Hospital Union City | $1.7M | $1.9M | +$153K | 8% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/621138045) |
| 92 | Rutland Regional Medical Center | $2.8M | $2.6M | −$138K | 5% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/30183483) |
| 93 | Clay County Medical Corporation | $1.5M | $1.5M | +$73K | 5% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/640668465) |
| 94 | St. Lukes Wood River Medical Center | $1.9M | $1.9M | −$68K | 4% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/841421665) |
| 95 | Cape Canaveral Hospital Inc | $11.2M | $11.2M | +$42 | 0% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/592477479) |
| 96 | Viera Hospital Inc | $5.2M | $5.2M | +$22 | 0% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/264019868) |
| 97 | Gibson Area Hospital And Health Svcs | $1.6M | $1.6M | $0 | 0% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/370647938) |
| 98 | Macon County General Hospital | $1.2M | $1.2M | $0 | 0% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/620988604) |
| 99 | Medical Center Of Deltona | $2.7M | $2.7M | $0 | 0% | [990 ↗](https://projects.propublica.org/nonprofits/organizations/842569909) |

**Reading the sign:** a positive difference means the hospital reported *more* charity-care cost to CMS than to the IRS; negative means it reported more to the IRS than to CMS.

## Why the numbers legitimately differ

- **Definitions.** The two forms bound "financial assistance" / "charity care" differently — for example, how uninsured discounts are classified.
- **Cost-to-charge ratios.** S-10 applies a hospital-wide CCR; Schedule H permits different cost-step-down methods.
- **Category boundaries.** The same patient case can be booked as charity care, bad debt, or contractual allowance — moving cost between lines.
- **S-10 data quality.** The reliability and completeness of Worksheet S-10 charity-care reporting has been repeatedly flagged (e.g., by MedPAC), so either figure — often the S-10 side — can simply be mis- or under-reported. That's a leading reason to read the source filings rather than treat a gap as settled.
- **System-wide methodology.** Hospitals under the same parent tend to share a financial-assistance policy and a common Schedule H costing method, which can push all of a system's hospitals the same direction — a methodological signature, not a statement about any one hospital.

This is a well-documented reporting inconsistency, not a novel discovery: the Government Accountability Office has noted there is no standard definition of uncompensated care across federal programs (GAO-16-568) and has separately scrutinized Schedule H reporting (GAO-20-679); the Congressional Research Service laid out the differing Medicare and IRS charity-care definitions (2018); CMS itself benchmarked S-10 against Form 990 data (2016); and health-services researchers have compared the two sources (e.g., Zare et al., *Health Services Research*, 2022).

## Method & reproduction

Generated by [`scripts/build_gap_index.py`](../scripts/build_gap_index.py) from [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv). The full dataset (1,295 computable systems) and its caveats are documented in [`community_benefit_gap_2022_summary.md`](community_benefit_gap_2022_summary.md). HCRIS FY2023 × IRS 990 Schedule H TY2022. US-government-work source data, public domain.

```bash
uv run python scripts/build_gap_dataset.py   # builds the full gap CSV
uv run python scripts/build_gap_index.py     # builds this index
```

# hcris

Parser for CMS Medicare Cost Reports (HCRIS).

Raw HCRIS ships as three headerless CSVs per fiscal-year ZIP (`RPT`, `NMRC`, `ALPHA`) in a long-skinny `(rpt_rec_num, wksht_cd, line_num, clmn_num, value)` shape. Field semantics live in a PDF (CMS PRM Chapter 40). This package turns that into a tidy DataFrame with real column names.

**Status:** scaffold. No functionality yet. See milestone M1 (parser) and M2 (semantic dictionary).

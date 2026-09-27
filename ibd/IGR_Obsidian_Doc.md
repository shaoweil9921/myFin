---
created: 2026-09-27
issue_date: 2026-08-03
source_pdf: eIBD_080326.pdf
status: complete
tags: [IBD, industry-group-rankings, extraction, pipeline]
---

# IBD Industry Group Rankings (IGR) — Extraction Pipeline

## Overview

Extracted Industry Group Rankings from Enhanced IBD (eIBD) PDF magazine for the Aug 3, 2026 issue. The IGR table lists IBD's rankings of all 197 industry groups, tracking each group's rank, prior rank, composite rating, YTD performance, and 3-week performance.

## Data Extracted

| Metric | Value |
|--------|-------|
| Total entries | 142 |
| With full data | 138 |
| Missing rating | 4 (ranks 114, 116, 123, 124) |
| Ranks in PDF | 1–142 |
| Ranks not in PDF | 143–197 (55 groups) |

## Source PDF

- **File:** `eIBD_080326.pdf`
- **Path:** `C:\DolphinShare\IBD\2026\Raw\`
- **Page:** B11 (page index 24, 0-indexed)
- **Issue:** Aug 3, 2026

## Column Layout

The IGR table is a 3-column layout on page B11:

| Column | X range | Content |
|--------|---------|---------|
| Col 0 | 0–145px | Rank, PrevRank, GroupName, Rating, YTD% |
| Col 1 | 145–290px | Rank, PrevRank, GroupName, Rating, YTD%, WK3% |
| Col 2 | 290–435px | WK3% carryover (continuation from Col 1) |

**Key finding:** The WK3% value for each entry appears in the *next column*, not the same cell. For Col 0 entries, WK3% is at the start of Col 1. For Col 1 entries, WK3% is at the start of Col 2.

Row height: ~9px per rank band, starting at y=682px from top of page.

## Extraction Algorithm

### Two-Pass Approach

**Pass 1 — Block Regex (Primary)**
Scans full page text with regex pattern:
```
(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+(\d{1,3})\s+([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)
```
- Matches: rank, prev_rank, group_name, rating, ytd%, wk3%
- Captures ~138 entries including all ranks 1-26 (which appear *before* the "Industry Group Rankings" header in text order)

**Pass 2 — Secondary Regex (Fallback)**
For entries with corrupted/missing rating field:
```
(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+([+-]\d+\.?\d*)\s+([+-]?\d+\.?\d*)
```
- Captures: rank, prev_rank, group_name, ytd%, wk3% (no rating)
- Applied to: ranks 114, 116, 123, 124 in Aug 3 issue

## Database Schema

```sql
CREATE TABLE ibd_industry_group_rankings (
    id              SERIAL PRIMARY KEY,
    issue_date      DATE NOT NULL,
    rank            SMALLINT NOT NULL,
    prev_group_rank SMALLINT,
    group_name      VARCHAR(60) NOT NULL,
    composite_rating SMALLINT,          -- NULL for corrupted entries
    ytd_pct         DECIMAL(7,2),
    wk3_pct         DECIMAL(7,2),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (issue_date, rank)
);

CREATE INDEX idx_igr_group_name ON ibd_industry_group_rankings (group_name);
CREATE INDEX idx_igr_issue_date ON ibd_industry_group_rankings (issue_date);
```

## CSV Format

File: `ibd/igr_aug03.csv`

| Column | Type | Example |
|--------|------|---------|
| Rank | int | 1 |
| PrevGroup | int | 7 |
| GroupName | str | Oil&gas-refin/mktg |
| Rating | int or empty | 86 |
| YTD_pct | str | +76.0 |
| 3Wk_pct | str | 0.0 |

## Top 10 Groups (by Rank)

| Rank | Prev | Group | Rating | YTD% | 3WK% |
|------|------|-------|--------|------|------|
| 1 | 7 | Oil&gas-refin/mktg | 86 | +76.0 | 0.0 |
| 2 | 5 | Compsftwr-secur | 85 | +62.0 | +3.0 |
| 3 | 8 | Busines equipsupplies | 86 | +30.0 | +1.0 |
| 4 | 2 | Commsvc-staffng | 85 | +38.0 | -2.0 |
| 5 | 61 | Consum-electrncs | 87 | +40.0 | -1.0 |
| 6 | 1 | Compsftwr-netwrk | 92 | +56.0 | +3.0 |
| 7 | 15 | Hsehold/applianc | 89 | +27.0 | -1.0 |
| 8 | 18 | Medical-svcs | 84 | +20.0 | -1.0 |
| 9 | 10 | Retail-homfurn | 78 | +34.0 | -2.0 |
| 10 | 17 | Banks-s&ls | 96 | +28.0 | +1.0 |

## Top 5 YTD Gainers

| Rank | Group | Rating | YTD% |
|------|-------|--------|------|
| 15 | Compsftwr-hrdwr | 87 | +186.0 |
| 77 | Telecom-equip | 62 | +76.0 |
| 1 | Oil&gas-refin/mktg | 86 | +76.0 |
| 13 | Elec-sci/msrng | 80 | +69.0 |
| 23 | Elec-semiequip | 82 | +65.0 |

## Entries Missing Rating (PDF Artifacts)

These 4 ranks have no composite rating in the PDF due to rendering issues:

| Rank | Group | Prev | YTD% | 3WK% | Likely Rating |
|------|-------|------|------|------|---------------|
| 114 | Trnsport-logistcs | 57 | +3.0 | +1.0 | ~70 |
| 116 | Chemicals-plastics | 120 | +18.0 | +1.0 | ~65 |
| 123 | Cannabis | 119 | -16.0 | +1.0 | ~55 |
| 124 | Finance-comloan | 114 | -14.0 | -1.0 | ~60 |

## Files

| File | Description |
|------|-------------|
| `ibd/extract_groups.py` | Main extraction script (two-pass, parameterized) |
| `ibd/build_igr_csv.py` | Standalone CSV builder |
| `ibd/igr_aug03.csv` | Extracted data (142 rows) |

## Known Limitations

1. **Partial coverage:** This PDF only contains ranks 1–142. Ranks 143–197 are absent (not an extraction failure).
2. **4 missing ratings:** Ranks 114, 116, 123, 124 have no composite rating in the source PDF — these are PDF rendering artifacts, not extraction bugs.
3. **Single issue:** Script is parameterized but CSV is for Aug 3, 2026 issue only.

## Future Enhancements

- [ ] Extend to all IBD PDF issues (Aug 10, Aug 17, Aug 24, Aug 31, etc.)
- [ ] Build rank change tracking: compute `rank - prev_group_rank` per issue
- [ ] Cross-issue group name normalization (e.g., "Compsftwr-secur" → "Computer Software-Security")
- [ ] Yield strength calculation: correlation between rating and YTD% across groups
- [ ] Sector aggregation: map groups to IBD sectors for sector rotation analysis
- [ ] Fill missing ratings: use adjacent issue data or manual lookup for ranks 114, 116, 123, 124

## How to Re-Run

```bash
# Extract from a different PDF
python ibd/extract_groups.py "C:\DolphinShare\IBD\2026\Raw\eIBD_081026.pdf" "igr_aug10.csv"

# Load to database
# (see extract_groups.py header for psycopg2 snippet)
```

## Related

- [[IBD 50 Extraction Pipeline]] — Stock-level extraction from same PDFs
- [[Stock Research Pipeline]] — Downstream analysis
- [[ Schaeffer's Letter Tracking]] — Alternative IBD-derived signals

"""
IBD 50 Extractor
=================
Extracts the IBD 50 stock list from an IBD PDF (eIBD format).
Saves output as CSV to the user's Download folder.

Strategy (v26 — Sep 2026):
  - LEFT side table (x < 300): rank rail + company/price/description rows
    Parsed directly: rank markers at x~18-25, company rows at x~40-289
  - RIGHT side tiles (x >= 300): symbol + trading note
    Matched by y-position to LEFT rows to get symbols + short notes
  - Descs come from LEFT (complete), symbols/notes from RIGHT

Usage:
    python extract_ibd50.py <pdf_path> [output_name]

Requirements:
    pip install pymupdf
"""

import re
import sys
import os
from datetime import datetime
from collections import defaultdict

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COL_X = [380, 530]
TOLERANCE = 30
LEFT_COL_X_MAX = 300
LEFT_RANK_X_MAX = 50

SHORT_NOTE_KEYWORDS = [
    "extended from", "exits ", "hits ", "back above", "back below", "above ", "below ",
    "tries to", "building a", "trigger", "approaches", "retakes ",
    "flirting with", "extended after", "extended past", "reverses ",
    "bounces ", "bounce", "falls ", "slips ", "fails ", "fades ", "clears ",
    "tests ", "test ", "vault", "soars", "round-trips", "round-trip",
    "6-week", "six-week", "seven-week", "eight-week", "ten-week", "8-week", "10-week",
    "early-july", "early-june", "early-may",
    "rallies", "rally",
    "after support", "after test",
    "cup with handle", "handle entry",
    "buy zone", "buy point",
    "double-bottom", "double bottom",
    "near entry", "aggressive entry",
]

METRIC_PATTERNS = [
    r"Ann\. EPS", r"EPS Growth", r"Avg\. D\. Vol", r"Debt %",
    r"Last Qtr", r"Prior Qtr", r"Last Qtr Sales", r"Next Qtr",
    r"Qtrs EPS", r"ROE ", r"Comp\.? Rating", r"\bM Shares\b",
    r"Grp\d+", r"\$\d+[\.\d]*",
]

SKIP_STARTS = (
    "INVESTORS.COM", "SMARTSELECT", "COMPOSITE", "RATING",
    "Rel", "Annual", "Last", "Next", "Prior",
    "Acc/Dis", "Sup/Demand", "Due", "Avg", "Debt", "Qtrs",
    "EPS", "ROE", "PE ",
)

DESC_WORDS = [
    "testing firm", "provides ", "operates as", "engages in ",
    "invests in", "specializes in", "develops ", "leading ",
    "machine ", "online ", "shipping ", "owns and", "gold, copper",
    "healthcare", "biotechnology", "pharmaceutical",
]


def get_col(x: float) -> int:
    if x < COL_X[0]:
        return 0
    elif x < COL_X[1]:
        return 1
    return 2


def clean(s: str) -> str:
    return s.lstrip("}").strip()


# ---------------------------------------------------------------------------
# LEFT side table parser
# ---------------------------------------------------------------------------

def parse_left_table(blocks, words, rank_lo, rank_hi):
    """
    Parse LEFT side table (x < 300).

    Layout:
      - Rank rail: word-level at x~18-25, one number per rank (y=326,353,380...)
      - Company rows: block-level at x~40-289, one block per stock

    Block format (newline-separated):
      Line 0:  CompanyName
      Line 1:  Price RSrating
      Line 2+: EPS/metric numbers (dots, percents, counts)
      Last:    Description (free text with desc word)

    Returns: list of {rank, company, price, description, y}
    """
    # ── Step 1: Build rank -> y from word-level markers in left margin ────────
    rank_y = {}
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        text = text.strip()
        if not re.match(r'^\d{1,2}$', text):
            continue
        n = int(text)
        if not (rank_lo <= n <= rank_hi):
            continue
        if x0 > LEFT_RANK_X_MAX:
            continue
        if n not in rank_y:
            rank_y[n] = round(y0)

    if not rank_y:
        return []

    # ── Step 2: Collect ALL LEFT table row candidates ─────────────────────────
    # Criterion: x is in the body of the table (not rank rail at x<50), below header
    # We skip rank-rail blocks (x < 5 gives single-char words like '1') by requiring
    # x >= 35 (table body starts at ~x=40) or x1-x0 > 50 (wider than a single number)
    candidates = []
    for b in blocks:
        bx, by, bx1, by1, btext, *_ = b
        if not btext.strip() or bx >= LEFT_COL_X_MAX:
            continue
        if by < 310:
            continue
        # Skip the rank rail (x~18-36, very narrow block with just numbers)
        block_width = bx1 - bx
        if block_width < 50:
            continue
        candidates.append((by, btext.strip()))

    if not candidates:
        return []

    # ── Step 3: Match rows to ranks by y, parse each row ────────────────────
    # ── Step 3: Match each candidate to its nearest rank by y-proximity ──────────────────
    # For each row: find the closest unused rank marker within 40px below the row.
    # Then greedily assign in order of increasing row y, so lower rows (higher ranks)
    # fill first and don't steal from higher rows.
    rows = []
    used_ranks = set()

    # Sort candidates by y (top to bottom) — process from top of table down
    for row_y, btext in sorted(candidates, key=lambda x: x[0]):
        # Find the closest UNUSED rank that is at or just above this row
        # "At or above" means: row_y >= rank_y. Since row blocks are always slightly
        # below their rank marker (row at y=327, rank at y=326), this is always true.
        best_rank = None
        best_dist = float('inf')
        for rank, ry in sorted(rank_y.items(), key=lambda x: x[1]):
            if rank in used_ranks:
                continue
            dist = row_y - ry
            if dist >= 0 and dist < best_dist:
                best_dist = dist
                best_rank = rank

        if best_rank is None or best_dist > 40:
            continue

        # Parse the row
        lines = btext.split('\n')

        # Company: first line, strip leading } and trailing price/metrics
        raw_co = clean(lines[0])
        # Remove trailing price+metric artifacts like "CompanyName63.4799 82"
        company = re.sub(r'(\d+\.\d+\s+\d+)', '', raw_co).strip()
        # Fallback: if still looks numeric, take only leading alpha characters
        if not company or len(company) < 3:
            company = re.sub(r'\d.*$', '', raw_co).strip()
        if not company or len(company) < 3:
            continue

        # Price: second line, first number
        price = ""
        if len(lines) > 1:
            pm = re.search(r'\$(\d+\.?\d*)', lines[1])
            if not pm:
                pm = re.search(r'(\d+\.\d+)', lines[1])
            if pm:
                price = f"{float(pm.group(1)):.2f}"

        # Description: last non-metric line
        description = ""
        for i in range(len(lines) - 1, 0, -1):
            part = lines[i].strip()
            if not part:
                continue
            alpha = sum(1 for c in part if c.isalpha())
            total = len(part.replace(' ', ''))
            if total > 0 and alpha / total < 0.3:
                continue
            if re.match(r'^(\d+\.?\d*|[+-]\d+%?|\.\.)$', part):
                continue
            description = part
            break

        if not description:
            continue

        rows.append({
            'rank': best_rank,
            'company': company,
            'price': price,
            'description': description,
            'y': row_y,
        })
        used_ranks.add(best_rank)

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_short_note(s: str) -> bool:
    block = s.strip()
    if len(block) < 15:
        return False
    first_line = block.split('\n')[0]
    if re.match(r'^(Grp|PE |Avg |Debt |ROE |Last |Prior |Next |Qtrs |Acc/|Sup/|\d)', first_line):
        return False
    block_lower = block.lower()
    if not any(kw in block_lower for kw in SHORT_NOTE_KEYWORDS):
        return False
    first_lower = first_line.lower()
    has_desc_word = any(dw in first_lower for dw in DESC_WORDS)
    has_kw = any(kw in block_lower for kw in SHORT_NOTE_KEYWORDS)
    if has_desc_word and not has_kw:
        return False
    if '\n' in block:
        mc = sum(1 for p in METRIC_PATTERNS if re.search(p, block, re.I))
        if mc >= 3:
            return False
    return True


def is_metric_block(text: str) -> bool:
    mc = sum(1 for p in METRIC_PATTERNS if re.search(p, text, re.I))
    if mc >= 2:
        return True
    alpha = sum(1 for c in text if c.isalpha())
    total = len(text.replace(' ', '').replace('\n', ''))
    if total > 0 and alpha / total < 0.35:
        return True
    return False


def extract_description(block_text: str) -> str:
    lines = block_text.split('\n')
    desc_lines = []
    MP2 = [
        r"\d+\.?\d*\s*M\s*Shares", r"Comp\.?\s*Rating",
        r"\bEPS\b", r"\bRS\b", r"\bROE\b", r"Grp\d+", r"\$\d+[\.\d]*",
    ]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.search(r'.+\s+[A-Z]{2,6}\s*$', line):
            continue
        is_met = any(re.search(p, line, re.I) for p in MP2)
        alpha = sum(1 for c in line if c.isalpha())
        total = len(line.replace(' ', ''))
        if total > 0 and alpha / total < 0.35:
            is_met = True
        if re.match(r'^[+-]\d+%', line):
            is_met = True
        if re.match(r'^Due\s+\d+/\d+', line, re.I):
            is_met = True
        if re.match(r'^(ROE|Comp\.?\s*Rating)\b', line, re.I):
            is_met = True
        if not is_met:
            desc_lines.append(line)
    return ' '.join(desc_lines)


# ---------------------------------------------------------------------------
# Find B-pages
# ---------------------------------------------------------------------------

def find_b_pages(doc, skip_pages=14):
    b_pages = []
    for page_num in range(skip_pages, len(doc)):
        page = doc[page_num]
        text = page.get_text()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            continue
        for candidate in lines[:5] + [lines[-1]]:
            m = re.match(r'^(A|B|C)(\d+(?:\.\d+)?[A-Z]?)$', candidate, re.IGNORECASE)
            if m:
                b_pages.append((page_num, candidate.upper()))
                break
    return b_pages


# ---------------------------------------------------------------------------
# Process a single page  (v26: LEFT table primary)
# ---------------------------------------------------------------------------

def process_page(blocks, words, rank_lo=1, rank_hi=50):
    """
    v26:
      1. Parse LEFT table -> rank, company, price, description
      2. Match RIGHT tile headers by y -> symbol
      3. Match RIGHT short notes by y -> short_note
      4. Fall back to old tile logic if LEFT got < expected count
    """
    # ── Step 1: Parse LEFT table ───────────────────────────────────────────
    left_rows = parse_left_table(blocks, words, rank_lo, rank_hi)
    print(f"    LEFT table: {len(left_rows)} rows")

    # ── Step 2: Extract RIGHT tile headers, grouped by column ───────────────────
    # right_tiles_by_col[col] = sorted list of (y, symbol, company)
    right_tiles_by_col = {0: [], 1: [], 2: []}
    for b in blocks:
        bx, by, bx1, by1, btext, *_ = b
        btext = btext.strip()
        if not btext or bx < 300:
            continue
        header_line = None
        for line in btext.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(.+?)\s+([A-Z]{2,6})\s*$', line)
            if m:
                header_line = line
                break
        if not header_line:
            continue
        m = re.match(r'^(.+?)\s+([A-Z]{2,6})\s*$', header_line)
        company = clean(m.group(1))
        symbol = m.group(2).strip()
        if any(header_line.startswith(k) for k in SKIP_STARTS):
            continue
        if len(company) < 3 or company.lower() in ('group', 'sector', 'industry'):
            continue
        col = get_col(bx)
        if col in right_tiles_by_col:
            right_tiles_by_col[col].append((round(by), symbol, company))

    # Sort each column by y for nearest-match
    for col in right_tiles_by_col:
        right_tiles_by_col[col].sort(key=lambda x: x[0])

    total_tiles = sum(len(v) for v in right_tiles_by_col.values())
    c0 = len(right_tiles_by_col[0])
    c1 = len(right_tiles_by_col[1])
    c2 = len(right_tiles_by_col[2])
    print("    RIGHT tiles: {} headers (col0={} col1={} col2={})".format(total_tiles, c0, c1, c2))
    # ── Step 3: Collect RIGHT side short notes

    # ── Step 3: Collect RIGHT side short notes (x >= 300) ───────────────────
    short_notes_all = []
    for b in blocks:
        bx, by, bx1, by1, btext, *_ = b
        btext = btext.strip()
        if not btext or bx < 300:
            continue
        if re.search(r'\b[A-Z]{2,6}\s*$', btext, re.MULTILINE):
            continue
        if is_short_note(btext) and not is_metric_block(btext):
            short_notes_all.append((by, btext.strip()))

    # ── Step 4: Build results from LEFT rows ────────────────────────────────
    # LEFT rows are sorted by rank.
    # Column formula: (rank - rank_lo) % 3 — NOT i % 3.
    # This is correct even when LEFT skips some ranks.
    # Tile position within column: count of tiles for earlier ranks in same column.

    left_sorted = sorted(left_rows, key=lambda r: r['rank'])
    # Pre-count how many tiles exist per column so we can do positional index
    col_counts = {c: len(right_tiles_by_col.get(c, [])) for c in [0, 1, 2]}

    results = []
    for row in left_sorted:
        row_y = row['y']
        rank = row['rank']

        # Column from rank, NOT from list index
        expected_col = (rank - rank_lo) % 3

        # Tile position = how many tiles before this rank in the same column
        # Tiles in col are sorted by y (top=rank_lo, rank_lo+3, rank_lo+6, ...)
        tiles_in_col = right_tiles_by_col.get(expected_col, [])
        tile_pos = 0
        # Each tile in this column corresponds to ranks: rank_lo+2, rank_lo+5, rank_lo+8...
        # i.e., rank = rank_lo + 2 + 3*tile_index (since ranks 16,19,22,25,28 are in col 1 for B3)
        # General: rank = rank_lo + offset + 3*i where offset = col
        # So i = (rank - rank_lo - col) / 3
        tile_pos = (rank - rank_lo - expected_col) // 3

        symbol = ""
        if 0 <= tile_pos < len(tiles_in_col):
            symbol = tiles_in_col[tile_pos][1]

        # Short note: closest by y (any column)
        short_note = ""
        if short_notes_all:
            best_note = min(short_notes_all, key=lambda n: abs(n[0] - row_y), default=None)
            if best_note and abs(best_note[0] - row_y) < 250:
                short_note = best_note[1].strip().strip('"').strip('.').strip('"')

        results.append({
            'rank': row['rank'],
            'symbol': symbol,
            'company': row['company'],
            'price': row['price'],
            'description': row['description'],
            'short_note': short_note,
        })

    # ── Step 5: Fallback for missing ranks ─────────────────────────────────
    expected = rank_hi - rank_lo + 1
    if len(results) < expected:
        print(f"    LEFT got {len(results)}/{expected}, supplementing with RIGHT tiles...")
        tile_results = _process_page_tiles_fallback(blocks, words, rank_lo, rank_hi)
        left_ranks = {r['rank'] for r in results}
        for tr in tile_results:
            if tr['rank'] in left_ranks:
                continue
            results.append(tr)

    # Dedupe
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x['rank']):
        if r['rank'] not in seen and rank_lo <= r['rank'] <= rank_hi:
            seen.add(r['rank'])
            unique.append(r)

    return unique


def _process_page_tiles_fallback(blocks, words, rank_lo, rank_hi):
    """Fallback: old tile-based matching for ranks not covered by LEFT parsing."""
    markers_by_rank = defaultdict(list)
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        text = text.strip()
        if not re.match(r'^\d{1,2}$', text):
            continue
        n = int(text)
        if not (1 <= n <= 50):
            continue
        if x0 < 250:
            continue
        col = get_col(x0)
        if col not in (0, 1, 2):
            continue
        markers_by_rank[n].append(round(y0))

    tile_list = []
    for b in blocks:
        x0, y0, x1, y1, text, *_ = b
        text = text.strip()
        if not text or x0 < 300:
            continue
        header_line = None
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            m = re.match(r'^(.+?)\s+([A-Z]{2,6})\s*$', line)
            if m:
                header_line = line
                break
        if not header_line:
            continue
        m = re.match(r'^(.+?)\s+([A-Z]{2,6})\s*$', header_line)
        company = clean(m.group(1))
        symbol = m.group(2).strip()
        if any(header_line.startswith(k) for k in SKIP_STARTS):
            continue
        if len(company) < 3 or company.lower() in ('group', 'sector', 'industry'):
            continue
        tile_list.append((get_col(x0), round(y0), {'company': company, 'symbol': symbol, 'raw': text}))

    if not tile_list:
        return []

    rank_candidates = {}
    for rank in range(rank_lo, rank_hi + 1):
        expected_col = (rank - rank_lo) % 3
        marker_ys = markers_by_rank.get(rank, [])
        for idx, (col, y_key, header) in enumerate(tile_list):
            if col != expected_col or not marker_ys:
                continue
            md = min(abs(y_key - my) for my in marker_ys)
            if md <= TOLERANCE:
                rank_candidates.setdefault(rank, []).append((md, idx))

    for rank in rank_candidates:
        rank_candidates[rank].sort(key=lambda x: x[0])

    assigned = {}
    used_tiles = set()
    for rank in sorted(rank_candidates.keys(), key=lambda r: (len(rank_candidates[r]), r)):
        for diff, tile_idx in rank_candidates[rank]:
            if tile_idx not in used_tiles:
                assigned[rank] = tile_idx
                used_tiles.add(tile_idx)
                break

    for rank in range(rank_lo, rank_hi + 1):
        if rank in assigned:
            continue
        expected_col = (rank - rank_lo) % 3
        col_ranks = sorted(r for r in range(rank_lo, rank_hi + 1)
                          if (r - rank_lo) % 3 == expected_col and r < rank and r in assigned)
        if not col_ranks:
            continue
        prev_y = tile_list[assigned[col_ranks[-1]]][1]
        cands = sorted((y, idx) for idx, (c, y, h) in enumerate(tile_list)
                      if c == expected_col and y > prev_y and idx not in used_tiles)
        if cands:
            assigned[rank] = cands[0][1]
            used_tiles.add(cands[0][1])

    # Short notes
    all_notes_by_col = {0: [], 1: [], 2: []}
    for b in blocks:
        bx, by, bx1, by1, btext, *_ = b
        btext = btext.strip()
        if not btext or bx < 300:
            continue
        col = get_col(bx)
        if col not in (0, 1, 2):
            continue
        if re.search(r'\b[A-Z]{2,6}\s*$', btext, re.MULTILINE):
            continue
        if is_short_note(btext):
            is_met = is_metric_block(btext)
            all_notes_by_col[col].append((by, btext, is_met))

    first_tile_y = min((tile_list[idx][1] for _, idx in assigned.items()), default=None)
    first_note_y = min((ny for ny, _, _ in all_notes_by_col[0] + all_notes_by_col[1] + all_notes_by_col[2]), default=None)
    notes_above = (first_note_y is not None and first_tile_y is not None and first_note_y < first_tile_y)
    reverse_order = notes_above

    note_by_rank = {}
    used_note_ids = set()
    for rank, tile_idx in sorted(assigned.items(), key=lambda x: tile_list[x[1]][1], reverse=reverse_order):
        if rank < rank_lo or rank > rank_hi:
            continue
        col, y_key, header = tile_list[tile_idx]
        for note_y, note_text, is_met in all_notes_by_col[col]:
            if id(note_text) in used_note_ids or is_met:
                continue
            dist = abs(note_y - y_key)
            if dist < 250 and dist < min((abs(note_y - y_key) for note_y, _, _ in all_notes_by_col[col]
                                         if id(note_text) not in used_note_ids and not is_metric_block(note_text)), default=float('inf')):
                note_by_rank[rank] = note_text.strip().strip('"').strip('.').strip('"')
                used_note_ids.add(id(note_text))
                break

    results = []
    for rank, tile_idx in sorted(assigned.items()):
        if rank < rank_lo or rank > rank_hi:
            continue
        col, y_key, header = tile_list[tile_idx]
        group, price = "", ""
        gm = re.search(r'Grp(\d+)', header['raw'])
        if gm:
            group = f"Grp{gm.group(1)}"
        pm = re.search(r'\$(\d+\.?\d*)', header['raw'])
        if pm:
            price = f"{float(pm.group(1)):.2f}"
        if not group or not price:
            for b in blocks:
                bx, by, bx1, by1, btext, *_ = b
                btext = btext.strip()
                if not btext or bx < 300 or get_col(bx) != col:
                    continue
                if not (y_key - 200 <= by <= y_key + 2000):
                    continue
                if abs(by - y_key) < 5 and abs(bx - 380) < 5:
                    continue
                if not group:
                    gm2 = re.search(r'Grp(\d+)', btext)
                    if gm2:
                        group = f"Grp{gm2.group(1)}"
                if not price:
                    pm2 = re.search(r'\$(\d+\.?\d*)', btext)
                    if pm2:
                        price = f"{float(pm2.group(1)):.2f}"
                if group and price:
                    break
        results.append({
            'rank': rank,
            'symbol': header['symbol'],
            'company': header['company'],
            'group': group,
            'price': price,
            'short_note': note_by_rank.get(rank, ''),
            'description': extract_description(header['raw']),
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def extract_ibd50(pdf_path, output_name=None):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    print(f"[IBD50] Opened: {pdf_path}")
    print(f"[IBD50] Total pages: {len(doc)}")

    b_pages = find_b_pages(doc, skip_pages=14)
    print(f"[IBD50] B-pages: {[id_ for _, id_ in b_pages]}")

    rank_map = {'B1': (1, 15), 'B3': (16, 30), 'B4': (31, 50)}

    all_records = []
    for page_idx, page_id in b_pages:
        page = doc[page_idx]
        blocks = page.get_text("blocks")
        words = page.get_text("words")

        if page_id not in rank_map:
            print(f"[IBD50]   Page {page_idx+1} ({page_id}): skipped")
            continue

        rank_lo, rank_hi = rank_map[page_id]
        records = process_page(blocks, words, rank_lo=rank_lo, rank_hi=rank_hi)
        print(f"[IBD50]   Page {page_idx+1} ({page_id}): extracted {len(records)} records")
        all_records.extend(records)

    doc.close()

    if not all_records:
        raise ValueError("No data extracted.")

    seen = set()
    unique = []
    for r in sorted(all_records, key=lambda x: x['rank']):
        if r['rank'] not in seen and 1 <= r['rank'] <= 50:
            seen.add(r['rank'])
            unique.append(r)

    print(f"[IBD50] Total records: {len(unique)}")

    missing = [r for r in range(1, 51) if r not in seen]
    if missing:
        print(f"[IBD50] Missing ranks: {missing}")

    download_dir = os.path.join(os.environ["USERPROFILE"], "Downloads")
    if output_name is None:
        today = datetime.today().strftime("%Y%m%d")
        output_name = f"IBD50_{today}"
    out_path = os.path.join(download_dir, f"{output_name}.csv")

    def esc(s):
        s = str(s).replace('"', '""')
        return f'"{s}"' if (',' in s or '"' in s or '\n' in s) else s

    rows = ["Rank,Symbol,Price,Company,Group,Short Note,Description"]
    for r in unique:
        rows.append(','.join([
            str(r['rank']),
            esc(r.get('symbol', '')),
            esc(r.get('price', '')),
            esc(r.get('company', '')),
            esc(r.get('group', '')),
            esc(r.get('short_note', '')),
            esc(r.get('description', '')),
        ]))

    with open(out_path, "w", encoding="utf-8", errors="replace") as f:
        f.write('\n'.join(rows))

    print(f"[IBD50] Saved -> {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_ibd50.py <pdf_path> [output_name]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        out = extract_ibd50(pdf_path, output_name)
        print(f"\nDone! -> {out}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

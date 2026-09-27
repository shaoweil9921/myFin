"""
Save IBD 50 data from DB to Obsidian markdown files.

Usage:
    python save_to_obsidian.py [issue_date]
    python save_to_obsidian.py 2026-08-10
    python save_to_obsidian.py --all    # save all dates in DB

Output:
    C:\\Data\\Obsidian_root\\Obsidian_trading\\ibd\\<YYYY-MM-DD>_ibd_50.md
"""
import psycopg2
import os
import argparse
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OBSIDIAN_IBD_PATH = r"C:\Data\Obsidian_root\Obsidian_trading\ibd"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "fintech",
    "user": "postgres",
    "password": "asdfghjk1234%",
}

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

FRONTMATTER_TEMPLATE = """---
created: {date}
tags: [IBD50, IBD, weekly-pick]
type: IBD-50
week-of: {date}
---

# IBD 50 — Week of {date_display}, {year}

Source: [[IBD 50 Database]]

## IBD 50 List

| # | Symbol | Price | Group | Industry | Short Note |
|---|--------|-------|-------|----------|------------|
"""

ROW_TEMPLATE = "| {rank} | {symbol} | {price} | {group} | {company} | {short_note} |"

SUMMARY_TEMPLATE = """

## Summary Stats

- **Total Stocks:** {total}
- **Price Range:** {price_range}
- **Top Groups:** {top_groups}

## Stocks by Group

{group_table}

## Notes

- Extracted from eIBD PDF via automated pipeline
- Symbols and groups verified against user corrections
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_ibd50(conn, issue_date):
    """Fetch all 50 stocks for a given issue date, ordered by rank."""
    cur = conn.cursor()
    cur.execute("""
        SELECT rank, symbol, company, price, industry, short_note
        FROM ibd_50_new
        WHERE issue_date = %s
        ORDER BY rank
    """, (issue_date,))
    rows = cur.fetchall()
    cur.close()
    return rows


def format_price(price):
    """Format price as $XX.XX or '-'."""
    if price is None:
        return "-"
    return f"${price:.2f}"


def render_note(rows, issue_date):
    """Render a complete Obsidian markdown note."""
    date_obj = datetime.strptime(issue_date, "%Y-%m-%d")
    date_display = date_obj.strftime("%b %d").lstrip("0").replace(" 0", " ")
    year = date_obj.year

    # Build table rows
    table_lines = []
    for rank, symbol, company, price, industry, short_note in rows:
        table_lines.append(ROW_TEMPLATE.format(
            rank=rank,
            symbol=f"[[{symbol}]]" if symbol else "-",
            price=format_price(price),
            group=industry or "-",
            company=company or "-",
            short_note=(short_note or "-")[:60] + ("..." if short_note and len(short_note) > 60 else ""),
        ))

    # Summary stats
    prices = [r[3] for r in rows if r[3] is not None]
    price_range = f"${min(prices):.2f} – ${max(prices):.2f}" if prices else "N/A"

    # Group distribution
    from collections import Counter
    group_counter = Counter(r[4] for r in rows if r[4])
    top_groups = ", ".join(f"{g} ({c})" for g, c in group_counter.most_common(5))

    # Group table
    group_table_lines = []
    for grp, cnt in sorted(group_counter.items(), key=lambda x: int(x[0].replace('Grp',''))):
        symbols_in_group = [r[1] for r in rows if r[4] == grp]
        group_table_lines.append(f"| {grp} | {cnt} | {', '.join(symbols_in_group)} |")

    return (
        FRONTMATTER_TEMPLATE.format(date=issue_date, date_display=date_display, year=year)
        + "\n".join(table_lines)
        + SUMMARY_TEMPLATE.format(
            total=len(rows),
            price_range=price_range,
            top_groups=top_groups or "N/A",
            group_table="\n".join(
                ["| Group | Count | Symbols |"]
                + ["|-------|-------|---------|"]
                + group_table_lines
            ) if group_table_lines else "N/A",
        )
    )


def save_note(rows, issue_date):
    """Save one IBD 50 note to Obsidian."""
    os.makedirs(OBSIDIAN_IBD_PATH, exist_ok=True)
    filename = f"{issue_date}_ibd_50.md"
    filepath = os.path.join(OBSIDIAN_IBD_PATH, filename)

    content = render_note(rows, issue_date)

    if os.path.exists(filepath):
        print(f"  Overwriting: {filepath}")
    else:
        print(f"  Creating: {filepath}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Save IBD 50 to Obsidian")
    parser.add_argument("dates", nargs="*", help="Issue dates (YYYY-MM-DD), e.g. 2026-08-10")
    parser.add_argument("--all", action="store_true", help="Save all dates in DB")
    args = parser.parse_args()

    conn = get_connection()

    try:
        if args.all:
            # Get all unique dates
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT issue_date FROM ibd_50_new ORDER BY issue_date")
            dates = [str(r[0]) for r in cur.fetchall()]
            cur.close()
            print(f"Found {len(dates)} dates in DB: {', '.join(dates)}")
        elif args.dates:
            dates = args.dates
        else:
            # Default: most recent
            cur = conn.cursor()
            cur.execute("SELECT MAX(issue_date) FROM ibd_50_new")
            dates = [str(cur.fetchone()[0])]
            cur.close()
            print(f"No date specified, using most recent: {dates[0]}")

        for date in dates:
            rows = fetch_ibd50(conn, date)
            if not rows:
                print(f"No data found for {date}, skipping.")
                continue
            filepath = save_note(rows, date)
            print(f"  Saved {len(rows)} stocks -> {filepath}")

        print("\nDone.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

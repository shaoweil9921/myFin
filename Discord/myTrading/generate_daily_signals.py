"""
generate_daily_signals.py
Run after market close (11 PM ET, Mon-Fri) via cron.
Checks if any Discord messages exist for today.
If yes: generates Ashley_trading/YYYY-MM-DD-Daily-Signals.md
If no messages: exits silently, no file created.
"""
import os
import sys
import argparse
import psycopg2
from datetime import date, timedelta
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────────
DB_HOST = "127.0.0.1"
DB_PORT = 5432
DB_NAME = "fintech"
DB_USER = "postgres"
# Password resolved centrally (registry HKCU\Environment\DB_PW -> env fallback).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _db_pw import get_db_pw
DB_PW = get_db_pw()

VAULT_PATH = r"C:\Data\Obsidian_root\Obsidian_trading\Ashley_trading"
# ────────────────────────────────────────────────────────────────────────────

def get_today_et():
    """Return today's date in US Eastern time."""
    import datetime
    # UTC now -> Eastern
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    et_tz = datetime.timezone(datetime.timedelta(hours=-4))  # EDT (summer)
    et_now = utc_now.astimezone(et_tz)
    return et_now.date()

def parse_date(s):
    """Parse YYYY-MM-DD string into a date object."""
    from datetime import datetime
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {s!r}. Use YYYY-MM-DD.")

def main():
    parser = argparse.ArgumentParser(description="Generate daily Discord signals file for Obsidian.")
    parser.add_argument("--date", type=parse_date, default=None,
                        help="Date to generate file for, as YYYY-MM-DD. Defaults to today ET.")
    args = parser.parse_args()

    today = args.date if args.date is not None else get_today_et()
    today_str = today.strftime("%Y-%m-%d")

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PW
    )
    cur = conn.cursor()

    # Check for messages today (for reporting purposes)
    cur.execute("""
        SELECT COUNT(*)
        FROM discord_message
        WHERE DATE(created_at AT TIME ZONE 'America/New_York') = %s
    """, (today,))
    msg_count = cur.fetchone()[0]

    # Check for signals today (by signal_date, not insert time)
    cur.execute("""
        SELECT COUNT(*)
        FROM discord_trade_signal
        WHERE signal_date = %s
    """, (today,))
    sig_count = cur.fetchone()[0]

    if sig_count == 0:
        print(f"[INFO] No signals for {today_str} — no file generated.")
        cur.close()
        conn.close()
        return

    # Fetch all signals for today
    cur.execute("""
        SELECT s.signal_date, s.signal_id, s.asset_class, s.stock_ticker, s.trade_direction, s.option_type,
               s.entry_price, s.target_price, s.stop_loss, s.strike_price,
               s.premium_price, s.strategy_type, s.risk_reward_ratio, s.confidence,
               s.expiration_date, s.signal_status, m.author_username
        FROM discord_trade_signal s
        LEFT JOIN discord_message m ON m.id = s.message_id
        WHERE s.signal_date = %s
        ORDER BY s.created_at ASC
    """, (today,))
    signals = cur.fetchall()

    if not signals:
        print(f"[INFO] Query returned 0 rows for {today_str} — no file generated.")
        cur.close()
        conn.close()
        return

    cur.close()
    conn.close()

    print(f"[INFO] Found {len(signals)} signal(s) for {today_str} — generating daily file ...")

    # ── Build the file ─────────────────────────────────────────────────────
    month_name = today.strftime("%B")
    lines = []

    # YAML frontmatter with ticker tags (for Obsidian tag browser)
    all_tickers = sorted(set(r[3] for r in signals if r[3]))
    lines.append("---\n")
    lines.append(f"tags: [{', '.join(t for t in all_tickers)}]\n")
    lines.append(f"created: {today_str}\n")
    lines.append("---\n\n")

    lines.append(f"# Discord Trading Signals — {month_name} {today.day}, {today.year}\n")
    lines.append(f"## 📅 {today.strftime('%b %d, %Y')}")

    if signals:
        lines.append(f" — {len(signals)} Signal(s)\n\n")
    else:
        lines.append(" — No signals parsed from today's messages\n\n")
        lines.append("*Note: Messages exist but no structured signals were extracted.*\n\n")

    def fmt(v):
        if v is None: return None
        try: return f"{float(v):.2f}"
        except: return str(v)

    # ── Per-signal details ─────────────────────────────────────────────────
    for r in signals:
        ticker   = r[3]
        opt_type = r[5]
        strat    = r[11]
        exp      = r[14]
        status   = r[15]
        author   = r[16]
        entry    = r[6]
        target   = r[7]
        stop     = r[8]
        strike   = r[9]
        prem     = r[10]
        asset    = r[2]
        direction = r[4] or opt_type

        lines.append(f"### {ticker} #{ticker}\n")
        lines.append(f"- **Direction:** {direction}\n")
        if strat:
            lines.append(f"- **Strategy:** {strat}\n")
        if strike:
            lines.append(f"- **Strike:** ${fmt(strike)}\n")
        if exp:
            exp_str = exp.strftime('%m/%d/%Y') if hasattr(exp, 'strftime') else str(exp)
            if hasattr(exp, 'days'):
                days_to_exp = (exp - today).days
                warn = " ⚠️" if days_to_exp <= 2 else ""
            else:
                warn = ""
            lines.append(f"- **Expiration:** {exp_str}{warn}\n")
        if entry is not None:
            lines.append(f"- **Entry:** ${fmt(entry)}\n")
        if target is not None:
            lines.append(f"- **Target:** ${fmt(target)}\n")
        if stop is not None:
            lines.append(f"- **Stop:** ${fmt(stop)}\n")
        if prem is not None:
            lines.append(f"- **Premium:** ${fmt(prem)}\n")
        lines.append(f"- **Status:** {status}\n")
        lines.append(f"- **Author:** {author}\n")
        lines.append("\n")

    # ── Summary table ─────────────────────────────────────────────────────
    lines.append("---\n\n## 📊 Summary\n\n")
    lines.append("| Ticker | Strategy | Direction | Strike | Exp | Premium | Author |\n")
    lines.append("|--------|----------------|-----------|--------|-----|---------|----------------|\n")
    for r in signals:
        ticker    = r[3]
        strat     = r[11] or r[2]
        direction = r[4] or r[5]
        strike    = f"${fmt(r[9])}" if r[9] else "—"
        exp       = r[14].strftime('%m/%d/%y') if hasattr(r[14], 'strftime') and r[14] else str(r[14] or "—")
        prem      = f"${fmt(r[10])}" if r[10] is not None else "—"
        status    = r[15]
        author  = r[16]
        lines.append(f"| {ticker} | {strat} | {direction} | {strike} | {exp} | {prem} | {author} |\n")

    # ── Message count footer ────────────────────────────────────────────────
    lines.append(f"\n---\n")
    lines.append(f"**Messages:** {msg_count} | **Signals:** {len(signals)}\n")
    lines.append(f"**Source:** `fintech.discord_trade_signal` / `discord_message`\n")

    content = "".join(lines)
    fname = f"{today_str}-Daily-Signals.md"
    fpath = os.path.join(VAULT_PATH, fname)

    # Only write if vault path exists
    if os.path.isdir(VAULT_PATH):
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] Written: {fname}")
        print(f"[OK] Path: {fpath}")
    else:
        print(f"[ERROR] Vault path not found: {VAULT_PATH}")
        sys.exit(1)

    print("[DONE] Daily signals file generated.")

if __name__ == "__main__":
    main()

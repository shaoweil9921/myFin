"""
generate_daily_signals.py
Run after market close (11 PM ET, Mon-Fri) via cron.
Checks if any Discord messages exist for today.
If yes: generates Ashley_trading/YYYY-MM-DD-Daily-Signals.md
If no messages: exits silently, no file created.
"""
import os
import sys
import psycopg2
from datetime import date, timedelta
from collections import defaultdict

# ── Config ──────────────────────────────────────────────────────────────────
DB_HOST = "127.0.0.1"
DB_PORT = 5432
DB_NAME = "fintech"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

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

def main():
    today = get_today_et()
    today_str = today.strftime("%Y-%m-%d")

    print(f"[INFO] Checking messages for {today_str} ...")

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()

    # Check for messages today
    cur.execute("""
        SELECT COUNT(*)
        FROM discord_message
        WHERE DATE(created_at AT TIME ZONE 'America/New_York') = %s
    """, (today,))
    msg_count = cur.fetchone()[0]

    if msg_count == 0:
        print(f"[INFO] No messages for {today_str} — exiting silently, no file generated.")
        cur.close()
        conn.close()
        return

    print(f"[INFO] Found {msg_count} message(s) for {today_str} — generating daily file ...")

    # Fetch all signals for today
    cur.execute("""
        SELECT signal_date, signal_id, asset_class, stock_ticker, trade_direction, option_type,
               entry_price, target_price, stop_loss, strike_price,
               premium_price, strategy_type, risk_reward_ratio, confidence,
               expiration_date, signal_status, author_username
        FROM discord_trade_signal
        WHERE signal_date = %s
        ORDER BY created_at ASC
    """, (today,))
    signals = cur.fetchall()

    if not signals:
        print("[INFO] No signals parsed for today — generating file from messages only.")

    cur.close()
    conn.close()

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
        lines.append(f"- **Type:** {asset}\n")
        lines.append(f"- **Direction:** {direction}\n")
        if strat:
            lines.append(f"- **Strategy:** {strat}\n")
        if strike:
            lines.append(f"- **Strike:** ${strike}\n")
        if exp:
            exp_str = exp.strftime('%m/%d/%Y') if hasattr(exp, 'strftime') else str(exp)
            if hasattr(exp, 'days'):
                days_to_exp = (exp - today).days
                warn = " ⚠️" if days_to_exp <= 2 else ""
            else:
                warn = ""
            lines.append(f"- **Expiration:** {exp_str}{warn}\n")
        if entry is not None:
            lines.append(f"- **Entry:** ${entry}\n")
        if target is not None:
            lines.append(f"- **Target:** ${target}\n")
        if stop is not None:
            lines.append(f"- **Stop:** ${stop}\n")
        if prem is not None:
            lines.append(f"- **Premium:** ${prem}\n")
        lines.append(f"- **Status:** {status}\n")
        lines.append(f"- **Author:** {author}\n")
        lines.append("\n")

    # ── Summary table ─────────────────────────────────────────────────────
    lines.append("---\n\n## 📊 Summary\n\n")
    lines.append("| Ticker | Type | Direction | Strike | Exp | Premium | Status |\n")
    lines.append("|--------|------|-----------|--------|-----|---------|--------|\n")
    for r in signals:
        ticker    = r[3]
        asset     = r[2]
        direction = r[4] or r[5]
        strike    = f"${r[9]}" if r[9] else "—"
        exp       = r[14].strftime('%m/%d') if hasattr(r[14], 'strftime') else str(r[14] or "—")
        prem      = f"${r[10]}" if r[10] is not None else "—"
        status    = r[15]
        lines.append(f"| {ticker} | {asset} | {direction} | {strike} | {exp} | {prem} | {status} |\n")

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

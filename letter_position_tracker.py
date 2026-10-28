# -*- coding: utf-8 -*-
"""
letter_position_tracker.py
Daily EOD tracking for Schaeffer's letter positions.
Handles: entry fill, P&L update, profit target exit, expiration.
Table: subscription_letter_position (fintech DB)
"""
import os, sys, pathlib, psycopg2, yfinance as yf, requests
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent / "Discord" / "myTrading"))
from _db_pw import DB_CONFIG

DB = DB_CONFIG

def db():
    return psycopg2.connect(**DB)

def yf_opt(ticker, strike, exp, otype):
    try:
        exp_str = exp.strftime('%y%m%d')
        code = 'C' if otype == 'call' else 'P'
        sym = f"{ticker.upper()}{exp_str}{code}{int(float(strike)*1000):08d}"
        opt = yf.Ticker(sym)
        bid = float(opt.info.get('bid', 0) or 0)
        ask = float(opt.info.get('ask', 0) or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        h = opt.history(period='10d')
        return float(h['Close'].iloc[-1]) if not h.empty else None
    except:
        return None

def alpaca_opt(ticker, strike, exp, otype):
    try:
        key, secret = os.environ.get('ALPACA_API_KEY', ''), os.environ.get('ALPACA_API_SECRET', '')
        if not key: return None
        base = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        r = requests.get(f'{base}/v2/positions',
            headers={'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret}, timeout=10)
        if r.status_code != 200: return None
        prefix = f"{ticker.upper()}{exp.strftime('%y%m%d')}{'C' if otype=='call' else 'P'}{int(float(strike)*1000):08d}"
        for p in r.json():
            if p.get('symbol', '').startswith(prefix):
                curr = float(p.get('current_price', 0) or 0)
                return curr or None
        return None
    except:
        return None

def fill_pending(conn, today):
    cur = conn.cursor()
    cur.execute("""
        SELECT lp.position_id, lp.ticker, lp.option_type, lp.strike, lp.expiration,
               lp.ask_price, sl.letter_date
        FROM subscription_letter_position lp
        JOIN subscription_letter sl ON lp.letter_id = sl.letter_id
        WHERE lp.status = 'pending_entry'
    """)
    filled = 0
    for (pos_id, ticker, otype, strike, exp, ask_price, letter_date) in cur.fetchall():
        entry_date = letter_date + timedelta(days=1)
        if entry_date.weekday() >= 5:
            entry_date = letter_date + timedelta(days=(7 - letter_date.weekday()))
        if today < entry_date: continue
        ep = float(ask_price) if ask_price else 0.0
        cur.execute("""
            UPDATE subscription_letter_position
            SET entry_price=%s, entry_date=%s, current_price=%s, pnl_pct=0, status='open'
            WHERE position_id=%s
        """, (ep, entry_date, ep, pos_id))
        conn.commit()
        print(f"  FILLED: {ticker} {otype.upper()} @{entry_date} ${ep:.2f}")
        filled += 1
    cur.close()
    return filled

def update_open(conn, today):
    cur = conn.cursor()
    cur.execute("""
        SELECT position_id, ticker, option_type, strike, expiration, entry_price, profit_target_pct
        FROM subscription_letter_position WHERE status='open'
    """)
    rows = cur.fetchall()
    cur.close()
    result = {'updated': 0, 'closed': 0, 'expired': 0, 'alerts': []}
    for (pos_id, ticker, otype, strike, exp, entry_price, target_pct) in rows:
        if entry_price is None:
            # No entry price recorded — treat as expired if past expiration, else skip
            if today >= exp:
                cur = conn.cursor()
                cur.execute("UPDATE subscription_letter_position SET status='expired', exit_price=0, exit_date=%s WHERE position_id=%s",
                    (today, pos_id))
                conn.commit()
                cur.close()
                result['expired'] += 1
                result['alerts'].append(f"EXPIRED (no entry): {ticker} {otype.upper()} (exp {exp})")
            continue
        ep = float(entry_price)
        if ep <= 0: continue
        opt_price = alpaca_opt(ticker, float(strike), exp, otype) or yf_opt(ticker, float(strike), exp, otype)
        pnl = ((opt_price - ep) / ep * 100) if opt_price else 0.0
        hit = pnl >= float(target_pct)
        expired = today >= exp
        cur = conn.cursor()
        if expired:
            cur.execute("UPDATE subscription_letter_position SET current_price=%s, pnl_pct=%s, exit_price=0, exit_date=%s, status='expired' WHERE position_id=%s",
                (opt_price, pnl, today, pos_id))
            result['expired'] += 1
            result['alerts'].append(f"EXPIRED: {ticker} {otype.upper()} (exp {exp})")
        elif hit:
            cur.execute("UPDATE subscription_letter_position SET current_price=%s, pnl_pct=%s, exit_price=%s, exit_date=%s, status='closed' WHERE position_id=%s",
                (opt_price, pnl, opt_price or ep*(1+float(target_pct)/100), today, pos_id))
            result['closed'] += 1
            result['alerts'].append(f"TARGET HIT: {ticker} {otype.upper()} {pnl:+.0f}%")
        else:
            cur.execute("UPDATE subscription_letter_position SET current_price=%s, pnl_pct=%s WHERE position_id=%s",
                (opt_price, pnl, pos_id))
            result['updated'] += 1
        conn.commit()
        cur.close()
    return result

def get_all(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT position_id, ticker, option_type, strike, expiration, status,
               entry_price, current_price, pnl_pct, exit_date, profit_target_pct
        FROM subscription_letter_position
        ORDER BY letter_id DESC NULLS LAST, ticker
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def main():
    today = date.today()
    print(f"=== Letter Position Tracker --- {today} ===")
    conn = db()
    print("\n[1] Checking pending entries...")
    n = fill_pending(conn, today)
    print(f"  {n} filled")
    print("\n[2] Updating open positions...")
    result = update_open(conn, today)
    positions = get_all(conn)
    print("\nLetter Position Summary")
    print("=" * 40)
    for p in positions:
        ep = f"${p['entry_price']:.2f}" if p['entry_price'] else "n/a"
        cp = f"${p['current_price']:.2f}" if p['current_price'] else "n/a"
        pnl = p['pnl_pct'] or 0
        print(f"  {p['ticker']} {p['option_type'].upper()} ${p['strike']:.0f} "
              f"| Entry:{ep} Curr:{cp} [{pnl:+.0f}%] | Tgt:{p['profit_target_pct']}% | {p['status']} | {p['expiration']}")
    if result.get('alerts'):
        print("\n[ALERTS]:")
        for a in result['alerts']: print(f"  {a}")
    print(f"\nUpdated:{result['updated']} Closed:{result['closed']} Expired:{result['expired']}")
    print("\n[DONE]")
    conn.close()

if __name__ == '__main__':
    sys.exit(main())
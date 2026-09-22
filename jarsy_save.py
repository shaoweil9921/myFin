"""
Jarsy Save — reads jarsy_presale.json and jarsy_live.json, saves to DB.
"""
import json, os, psycopg2, sys

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%'
}

PRESALE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_presale.json"
LIVE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_live.json"

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def load_json(path):
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found — skipping")
        return []
    with open(path) as f:
        data = json.load(f)
    print(f"  Loaded {len(data)} tokens from {os.path.basename(path)}")
    return data

def save_presale(tokens, scan_id):
    if not tokens:
        print("  No presale tokens to save")
        return 0
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    for tok in tokens:
        symbol = tok.get("symbol", "").strip()
        name = tok.get("name", "").strip()
        price_str = tok.get("price", "")
        price = float(price_str) if price_str else None

        if not symbol or not name:
            continue

        cur.execute("""
            INSERT INTO jarsy_asset (extract_date, token_name, symbol, price, holding, action, scan_id)
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (extract_date, symbol) DO UPDATE SET
                token_name = EXCLUDED.token_name,
                price = EXCLUDED.price,
                holding = EXCLUDED.holding,
                action = EXCLUDED.action,
                updated_at = NOW()
        """, (name, symbol, price, tok.get("holding", "-"), "Buy", scan_id))
        saved += 1
    conn.commit()
    conn.close()
    print(f"  Saved {saved} presale tokens (scan_id={scan_id})")
    return saved

def save_live(tokens, scan_id):
    if not tokens:
        print("  No live tokens to save")
        return 0
    conn = get_conn()
    cur = conn.cursor()
    saved = 0
    for tok in tokens:
        symbol = tok.get("symbol", "").strip()
        name = tok.get("name", "").strip()
        price_str = tok.get("price", "")
        price = float(price_str) if price_str else None

        if not symbol or not name:
            continue

        cur.execute("""
            INSERT INTO jarsy_asset_live (extract_date, token_name, symbol, price, holding, action, scan_id)
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (extract_date, symbol) DO UPDATE SET
                token_name = EXCLUDED.token_name,
                price = EXCLUDED.price,
                holding = EXCLUDED.holding,
                action = EXCLUDED.action,
                updated_at = NOW()
        """, (name, symbol, price, tok.get("holding", "-"), "Buy", scan_id))
        saved += 1
    conn.commit()
    conn.close()
    print(f"  Saved {saved} live tokens (scan_id={scan_id})")
    return saved

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python jarsy_save.py <scan_id>")
        sys.exit(1)

    scan_id = int(sys.argv[1])

    print("Reading JSON files...")
    presale_tokens = load_json(PRESALE_FILE)
    live_tokens = load_json(LIVE_FILE)

    print("Saving to DB...")
    n_pre = save_presale(presale_tokens, scan_id)
    n_live = save_live(live_tokens, scan_id)

    print(f"DONE: {n_pre} presale, {n_live} live saved to scan_id={scan_id}")

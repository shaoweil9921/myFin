import psycopg2

conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password='asdfghjk1234%')
cur = conn.cursor()

scan_id = 72
live_tokens = [
    ('Crusoe Energy Holdings Inc.', 'JCRSO', 154.51, '-', 'Buy'),
    ('Polymarket (Blockratize Inc.)', 'JPOLY', 260.60, '-', 'Buy'),
    ('Harvey AI, Inc', 'JHVAI', 259.97, '-', 'Buy'),
    ('Mercury Technologies Inc.', 'JMERC', 18.41, '-', 'Buy'),
    ('Perplexity AI, Inc.', 'JPEPX', 779.92, '-', 'Buy'),
    ('Payward, Inc. (Kraken)', 'JKRAK', 37.57, '-', 'Buy'),
    ('X.AI Corp.', 'JXAI', 109.99, '-', 'Buy'),
    ('Anysphere Inc. (Cursor)', 'JANY', 1079.32, '-', 'Buy'),
    ('SpaceX Tech. Corp.', 'JSPAX', 943.91, '-', 'Buy'),
    ('Anthropic, PBC.', 'JANTH', 1038.82, '-', 'Buy'),
    ('Anduril Industries, Inc', 'JANDL', 125.68, '-', 'Buy'),
    ('SpaceX Tech. Corp. - Jarsy, II', 'JSPAX_2', 851.49, '-', 'Buy'),
    ('PsiQuantum Corp.', 'JPSIQ', 54.09, '-', 'Buy'),
    ('Vercel Inc.', 'JVRCL', 281.50, '-', 'Buy'),
    ('Agility Robotics Inc.', 'JAGIL', 74.98, '-', 'Buy'),
    ('Kalshi Inc.', 'JKALS', 619.21, '-', 'Buy'),
    ('Discord Inc.', 'JDISC', 318.55, '-', 'Buy'),
    ('Notion Labs Inc.', 'JNOTE', 82.65, '-', 'Buy'),
    ('Apptronik, Inc.', 'JAPTK', 43.99, '-', 'Buy'),
    ('Databricks Inc.', 'JDATA', 242.23, '-', 'Buy'),
    ('Stripe Inc.', 'JSTRP', 45.68, '-', 'Sell'),
    ('Ripple. Corp.', 'JRIPL', 167.66, '-', 'Buy'),
    ('Redwood Materials Inc.', 'JREDW', 71.01, '-', 'Buy'),
    ('Chaos Industries, Inc.', 'JCHAOS', 202.77, '-', 'Buy'),
    ('Figure AI, Inc.', 'JFIGR', 374.54, '-', 'Buy'),
    ('Shield AI, Inc.', 'JSHLD', 450.67, '-', 'Buy'),
]

for token_name, symbol, price, holding, action in live_tokens:
    cur.execute("""
        INSERT INTO jarsy_asset_live (extract_date, token_name, symbol, price, holding, action, scan_id)
        VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (extract_date, symbol) DO UPDATE SET
        token_name=EXCLUDED.token_name, price=EXCLUDED.price, holding=EXCLUDED.holding,
        action=EXCLUDED.action, updated_at=NOW()
    """, (token_name, symbol, price, holding, action, scan_id))

conn.commit()
print(f"Inserted {len(live_tokens)} live tokens")
conn.close()
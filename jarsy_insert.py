import psycopg2

conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password='asdfghjk1234%')
cur = conn.cursor()

scan_id = 72
tokens = [
    ('Neuralink Corp.', 'JNRLK', None, '-', 'Buy'),
    ('World Labs, Inc.', 'JWRLD', None, '-', 'Buy'),
    ('Waymo LLC', 'JWYMO', None, '-', 'Buy'),
    ('OpenAI Group PBC', 'JOPAI', None, '-', 'Buy'),
    ('Figure AI, Inc.', 'JFIGR', 170.00, '-', 'Buy'),
    ('X.AI Corp.', 'JXAI', 100.00, '-', 'Buy'),
    ('Perplexity AI Inc.', 'JPEPX', 818.53, '-', 'Buy'),
    ('Reflection AI Inc.', 'JRFLX', 100.00, '-', 'Buy'),
    ('Crusoe Energy Holdings Inc.', 'JCRSO', 145.00, '-', 'Buy'),
    ('Polymarket', 'JPOLY', 210.00, '-', 'Buy'),
    ('Cerebras Systems Inc.', 'JCBRS', 122.00, '-', 'Buy'),
    ('Kalshi Inc.', 'JKALS', 450.00, '-', 'Buy'),
    ('SpaceX Tech. Corp.', 'JSPAX', 770.00, '-', 'Buy'),
    ('PsiQuantum Corp.', 'JPSIQ', 44.00, '-', 'Buy'),
    ('Redwood Materials Inc.', 'JREDW', 55.00, '-', 'Buy'),
    ('Anthropic PBC', 'JANTH', 720.00, '-', 'Buy'),
    ('Apptronik, Inc.', 'JAPTK', None, '-', 'Buy'),
    ('Vercel Inc.', 'JVRCL', 234.72, '-', 'Buy'),
    ('Payward, Inc. Kraken', 'JKRAK', 52.00, '-', 'Buy'),
    ('Anduril Industries, Inc', 'JANDL', 160.00, '-', 'Buy'),
    ('Discord Inc.', 'JDISC', 280.00, '-', 'Buy'),
    ('Databricks Inc.', 'JDATA', 270.00, '-', 'Buy'),
    ('Notion Labs Inc.', 'JNOTE', 70.00, '-', 'Buy'),
    ('Stripe, Inc.', 'JSTRP', 84.00, '-', 'Buy'),
    ('Anysphere Inc. (Cursor)', 'JANY', None, '-', 'Buy'),
    ('Ripple Labs, Inc.', 'JRIPL', 151.00, '-', 'Buy'),
    ('Agility Robotics Inc.', 'JAGIL', 86.00, '-', 'Buy'),
    ('Sesame AI Inc.', 'JSESA', None, '-', 'Buy'),
]

for token_name, symbol, price, holding, action in tokens:
    price_val = price if price is not None else None
    holding_val = '-' if holding == '-' else holding
    cur.execute("""
        INSERT INTO jarsy_asset (extract_date, token_name, symbol, price, holding, action, scan_id)
        VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (extract_date, symbol) DO UPDATE SET
        token_name=EXCLUDED.token_name, price=EXCLUDED.price, holding=EXCLUDED.holding,
        action=EXCLUDED.action, updated_at=NOW()
    """, (token_name, symbol, price_val, holding_val, action, scan_id))

conn.commit()
print(f"Inserted {len(tokens)} presale tokens")
conn.close()
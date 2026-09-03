"""Save Jarsy token data extracted from browser to database."""
import psycopg2
from datetime import date

PRESALE_TOKENS = [
    ("JAXIO-PRE", "Axiom Space, Inc.", "Presale", None),
    ("JNRLK-PRE", "Neuralink Corp.", "Presale", None),
    ("JSRNC-PRE", "Saronic Technologies, Inc.", "Presale", None),
    ("JWRLD-PRE", "World Labs, Inc.", "Presale", None),
    ("JWYMO-PRE", "Waymo LLC", "Presale", None),
    ("JPOLY-PRE", "Polymarket - Jarsy", "Presale", 200.00),
    ("JCBRS-PRE", "Cerebras Systems Inc.", "Presale", 122.00),
    ("JKALS-PRE", "Kalshi Inc.", "Presale", 451.00),
    ("JFIGR-PRE", "Figure AI, Inc.", "Presale", 171.00),
    ("JOPAI-PRE", "OpenAI Group PBC", "Presale", 880.00),
    ("JPEPX-PRE", "Perplexity AI Inc.", "Presale", 818.53),
    ("JRFLX-PRE", "Reflection AI Inc.", "Presale", 100.00),
    ("JCRSO-PRE", "Crusoe Energy Holdings Inc.", "Presale", 145.00),
    ("JPSIQ-PRE", "PsiQuantum Corp.", "Presale", 45.00),
    ("JSHLD-PRE", "Shield AI, Inc.", "Presale", 235.00),
    ("JREDW-PRE", "Redwood Materials Inc.", "Presale", 55.00),
    ("JANTH-PRE", "Anthropic PBC", "Presale", 720.00),
    ("JAPTK-PRE", "Apptronik, Inc.", "Presale", None),
    ("JVRCL-PRE", "Vercel Inc.", "Presale", 234.72),
    ("JKRAK-PRE", "Payward, Inc. Kraken", "Presale", 52.00),
    ("JDATA-PRE", "Databricks Inc.", "Presale", 270.00),
    ("JANDL-PRE", "Anduril Industries, Inc", "Presale", 160.00),
    ("JDISC-PRE", "Discord Inc.", "Presale", 280.00),
    ("JNOTE-PRE", "Notion Labs Inc.", "Presale", 70.00),
    ("JSTRP-PRE", "Stripe, Inc.", "Presale", 84.00),
    ("JLAMB-PRE", "Lambda, Inc.", "Presale", None),
    ("JANY-PRE", "Anysphere Inc. (Cursor)", "Presale", None),
    ("JAGIL-PRE", "Agility Robotics Inc.", "Presale", 86.00),
    ("JHELN-PRE", "Helion Energy, Inc.", "Presale", None),
    ("JELVN-PRE", "ElevenLabs, Inc.", "Presale", None),
    ("JHUGF-PRE", "Hugging Face, Inc.", "Presale", None),
    ("JSESA-PRE", "Sesame AI Inc.", "Presale", None),
    ("JRIPL-PRE", "Ripple Labs, Inc.", "Presale", 151.00),
    ("JSAMB-PRE", "SambaNova Systems, Inc.", "Presale", None),
    ("JREPL-PRE", "Replit, Inc.", "Presale", 300.00),
]

LIVE_TOKENS = [
    ("JPOLY", "Polymarket (Blockratize Inc.)", "Live", 155.54),
    ("JCRSO", "Crusoe Energy Holdings Inc.", "Live", 187.43),
    ("JREPL", "Replit, Inc.", "Live", 310.00),
    ("JRFLX", "Reflection AI Inc.", "Live", 105.00),
    ("JCBRS", "Cerebras Systems Inc.", "Live", 180.00),
    ("JKRAK", "Payward, Inc. (Kraken)", "Live", 28.10),
    ("JHVAI", "Harvey AI, Inc", "Live", 270.36),
    ("JMERC", "Mercury Technologies Inc.", "Live", 19.00),
    ("JPEPX", "Perplexity AI, Inc.", "Live", 757.97),
    ("JXAI", "X.AI Corp.", "Live", 62.00),
    ("JSPAX", "SpaceX Tech. Corp.", "Live", 430.00),
    ("JANY", "Anysphere Inc. (Cursor)", "Live", 936.33),
    ("JKALS", "Kalshi Inc.", "Live", 725.93),
    ("JSPAX_2", "SpaceX Tech. Corp. II", "Live", 415.00),
    ("JPSIQ", "PsiQuantum Corp.", "Live", 43.16),
    ("JVRCL", "Vercel Inc.", "Live", 267.83),
    ("JAGIL", "Agility Robotics Inc.", "Live", 112.12),
    ("JANTH", "Anthropic, PBC.", "Live", 655.14),
    ("JANDL", "Anduril Industries, Inc", "Live", 164.55),
    ("JNOTE", "Notion Labs Inc.", "Live", 74.95),
    ("JDISC", "Discord Inc.", "Live", 201.18),
    ("JSTRP", "Stripe Inc.", "Live", 45.68),
    ("JDATA", "Databricks Inc.", "Live", 200.27),
    ("JAPTK", "Apptronik, Inc.", "Live", 47.93),
    ("JRIPL", "Ripple. Corp.", "Live", 177.09),
    ("JREDW", "Redwood Materials Inc.", "Live", 53.00),
    ("JSHLD", "Shield AI, Inc.", "Live", 314.32),
    ("JCHAOS", "Chaos Industries, Inc.", "Live", 162.86),
    ("JFIGR", "Figure AI, Inc.", "Live", 416.52),
]

conn = psycopg2.connect(
    host="127.0.0.1", port=5432, database="fintech",
    user="postgres", password="asdfghjk1234%"
)
cur = conn.cursor()

today = date.today()
scan_id = 293  # from the cron run

# Clear old data for today
cur.execute("DELETE FROM jarsy_asset WHERE extract_date = %s", (today,))
cur.execute("DELETE FROM jarsy_asset_live WHERE extract_date = %s", (today,))
print(f"Cleared {cur.rowcount} existing rows for {today}")

# Insert presale
for symbol, token_name, action, price in PRESALE_TOKENS:
    cur.execute("""
        INSERT INTO jarsy_asset (token_name, symbol, price, holding, action, extract_date, scan_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (token_name, symbol, price, None, action, today, scan_id))

# Insert live
for symbol, token_name, action, price in LIVE_TOKENS:
    cur.execute("""
        INSERT INTO jarsy_asset_live (token_name, symbol, price, holding, action, extract_date, scan_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (token_name, symbol, price, None, action, today, scan_id))

conn.commit()
print(f"Inserted {len(PRESALE_TOKENS)} presale + {len(LIVE_TOKENS)} live tokens (scan_id={scan_id})")
cur.close()
conn.close()

import psycopg2
import sys

def get_conn():
    return psycopg2.connect(
        host="127.0.0.1",
        port=5432,
        database="fintech",
        user="postgres",
        password="asdfghjk1234%"
    )

def run_query(sql, fetch=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql)
    if fetch:
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    else:
        conn.commit()
        cur.close()
        conn.close()
        return None

if len(sys.argv) < 2:
    print("Usage: python jarsy_db.py <sql>")
    sys.exit(1)

sql = sys.argv[1]
try:
    result = run_query(sql)
    if result is not None:
        for row in result:
            print("\t".join(str(x) for x in row))
    else:
        print("OK")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

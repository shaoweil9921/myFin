# -*- coding: utf-8 -*-
"""Inspect cron job state + run receipts directly in the OpenClaw sqlite store."""
import json
import sqlite3
import sys

DB = r"C:\Users\shaowei_l\.openclaw\state\openclaw.sqlite"
JOB_ID = sys.argv[1] if len(sys.argv) > 1 else "c125cd06-97d9-4685-9d41-4891c2fd6916"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

row = conn.execute("select job_json from cron_jobs where job_id=?", (JOB_ID,)).fetchone()
if row:
    job = json.loads(row["job_json"])
    print("=== job.state ===")
    print(json.dumps(job.get("state", {}), indent=2))
    print("=== status/target/payload ===")
    print(job.get("status"), "|", job.get("sessionTarget"), "|", job.get("payload", {}).get("kind"))
else:
    print("job not found:", JOB_ID)

print("=== receipts ===")
try:
    rows = conn.execute(
        "select * from cron_run_receipts where job_id=? order by rowid desc limit 3",
        (JOB_ID,),
    ).fetchall()
    for r in rows:
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 400:
                d[k] = v[:400] + "...<trunc>"
        print(json.dumps(d, indent=2, default=str))
except Exception as exc:  # pragma: no cover - diagnostic script
    print("receipt read failed:", exc)

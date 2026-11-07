## Heartbeat Checklist

When you receive a heartbeat poll, do the following in order:

### 1. OpenClaw Version Check (once per day, weekdays only)

Use `exec` to run this PowerShell command:

```powershell
npm show openclaw version 2>$null
```

Compare against the last known version in `_openclaw_version_state.json`.

**If a new version is found:**
- Update `_openclaw_version_state.json` with the new version and current timestamp
- Send a Telegram message to 7923250382: "OpenClaw updated to [new version] — DataCloneError fix may be available!"

**If same version or error:** Do nothing. Silent.

---

### 2. Discord Fetch

**Handled by cron job** — `discord-fetch-signals` runs every 15 min during market hours (Mon–Fri 8 AM–5 PM ET). No action needed here.

---

### 3. Health Checks (rotate through)

**Daily once:**
- Review NVDA daily summary from `stock_technical` DB for today's date
- Check NVDA covered call signal for today

**2-3 times per day:**
- Alpaca positions: Check via Alpaca API using `ALPACA_API_KEY` + `ALPACA_API_SECRET` (NOT `APCA_API_KEY_ID`/`APCA_API_SECRET_KEY`)
  - If it times out / returns 504 or 500, **check `https://status.alpaca.markets/api/v2/scheduled-maintenances/active.json` first** — Alpaca runs Paper/Sandbox maintenance Saturdays 07:00–09:00 ET. If a window is active, report "SKIP — Alpaca in maintenance" and move on; it is not a script bug.
- Email: Any urgent unread messages?
- Calendar: Anything coming up in the next 24h?

---

### 4. Track state

Update `memory/heartbeat-state.json` after each check:

```json
{
  "lastChecks": {
    "openclaw_version": 1790000000000,
    "discord": 1790000000000,
    "discord_signals_last": 1790000000000,
    "email": 1790000000000,
    "calendar": 1790000000000,
    "nvda_signal": 1790000000000
  }
}
```

---

### Notes

- **Silent when nothing to report** — just respond HEARTBEAT_OK
- **Reach out proactively** — urgent email, calendar event <2h, new trade signal
- **Respect quiet hours** — no proactive contact 23:00–07:00 ET unless urgent
- Version check only fires once per day (first heartbeat after 8 AM ET on weekdays)
- Discord fetch runs on **every** heartbeat

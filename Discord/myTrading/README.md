# myTrading Discord Bot

OpenClaw-integrated Discord bot for trading research and alerts.

## Overview

- **Bot Name:** myTrading
- **Platform:** Discord (OpenClaw Gateway)
- **Repo:** https://github.com/shaoweil9921/myTrading
- **Bot Token:** stored in Windows env var `DISCORD_BOT_TOKEN`
- **Server ID:** `1158828571687669800`
- **Bot User ID:** `MTU1MDg3NzM5MDkyNDgxMjM1OA.GLLA2Q...`

## OpenClaw Config

Added to `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": {
        "source": "env",
        "provider": "default",
        "id": "DISCORD_BOT_TOKEN"
      },
      "groupPolicy": "allowlist",
      "guilds": {
        "1158828571687669800": {
          "requireMention": false,
          "users": ["805480702890999859"]
        }
      }
    }
  }
}
```

## Environment Variables

| Variable | Value |
|----------|-------|
| `DISCORD_BOT_TOKEN` | Bot token from Discord Developer Portal |

## Setup Steps Completed

1. ✅ Discord application created (myTrading)
2. ✅ Bot token generated
3. ✅ Privileged intents enabled (Message Content, Server Members)
4. ✅ OpenClaw config updated
5. ✅ Gateway restarted

## Features
- [ ] Read trading signals from subscribed server
- [ ] Stock research commands
- [ ] Watchlist monitoring
- [ ] Schaeffer's letter tracking

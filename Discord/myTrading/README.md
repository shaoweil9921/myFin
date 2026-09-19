# myTrading Discord Bot

OpenClaw-integrated Discord bot for trading research and alerts.

## Overview

- **Bot Name:** myTrading
- **Platform:** Discord (OpenClaw Gateway)
- **Repo:** https://github.com/shaoweil9921/myTrading

## Setup

### Discord Developer Portal
1. Create app: https://discord.com/developers/applications
2. Bot name: `myTrading`
3. Enable: Message Content Intent, Server Members Intent
4. OAuth2: Add bot to server with `bot` + `applications.commands` scopes

### OpenClaw Config
```json5
{
  channels: {
    discord: {
      enabled: true,
      token: { source: "env", provider: "default", id: "DISCORD_BOT_TOKEN" },
      groupPolicy: "allowlist",
      guilds: {
        "YOUR_SERVER_ID": {
          requireMention: false,
          users: ["YOUR_USER_ID"]
        }
      }
    }
  }
}
```

## Environment Variables
```
DISCORD_BOT_TOKEN=your_bot_token_here
```

## Features
- [ ] Trading alerts
- [ ] Stock research commands
- [ ] Watchlist monitoring
- [ ] Schaeffer's letter tracking

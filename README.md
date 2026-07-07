# Eden
A modular Discord bot with role management, verification tickets, and message logging. Built with discord.py, PostgreSQL, and Docker Compose.

## Features

### Moderation & Logging
- **Message logging** — deleted and edited messages are sent to a configurable log channel
- **`/set_log_channel`** — set which channel receives log events (persisted to `.env`, no database needed)
- **Status updates** — bot posts a status embed (latency, uptime) to the log channel on startup and every 6 hours
- **Instance ID** — every embed footer includes a random 4-digit hex ID to identify which container sent it

### Verification Tickets
- **`/verification_panel`** — posts a panel with an "Open Verification Ticket" button
- Private ticket channels are created per user under a "Verification Tickets" category
- Staff can close tickets with a "Close Ticket" button; the channel is deleted automatically
- Persistent views survive bot restarts

### Role Management
- **`/roles_panel`** — posts a dropdown for members to self-assign roles
- Automatically lists all roles the bot can assign (below its highest role)

### Admin
- **`/restart`** — pulls latest code and restarts the bot (requires Manage Guild)
- **`/diagnostics`** — shows latency, database status, uptime, loaded cogs, and command count
- **`/backup`** — runs a PostgreSQL database backup immediately
- **`/restore`** — restores the database from a named or latest backup
- **`/listbackups`** — lists available backup files

### General
- **`/introduction`** — posts an introduction embed with the bot's avatar
- **Ping** — mention the bot and it replies with "pong 🏓"

## Stack
- [discord.py](https://discordpy.readthedocs.io/) — bot framework
- PostgreSQL — database
- Docker Compose — deployment (auto git-pulls latest code on start)
- python-dotenv — runtime config via `.env`

# Roblox Limited Deal Tracker

Discord bot that watches Rolimons' live sale feed and pings you when a
limited item you're tracking sells below its value/RAP. Runs locally on
your own PC; also fires a Windows toast for every match while it's running.

## Setup

1. Create a Discord application at https://discord.com/developers/applications,
   add a Bot user, and copy its token.
2. Under OAuth2 > URL Generator, check `bot` and `applications.commands`,
   then use the generated URL to invite it to a server (or just DM it —
   slash commands work in DMs once it's added to at least one shared server).
3. Copy `.env.example` to `.env` and paste in the bot token.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run it:

   ```bash
   python bot.py
   ```

## Commands

- `/watch <item> [min_percent]` — get notified when `item` sells at least
  `min_percent` below its value (default 5%). Item names autocomplete.
- `/unwatch <item>` — stop tracking it.
- `/list` — show your current watchlist.

## Notes

- `config.json` controls poll interval, item cache refresh interval,
  default threshold, and whether desktop toasts are shown.
- Watchlists are stored per Discord user in `watchlist.db` (SQLite).
- The item cache and dedupe watermark reset on restart, so the first
  poll after startup never fires notifications for old sales.

🏟️ Arena Stats Discord Bot (OPFW)
-
A lightweight Discord slash-command bot for fetching and displaying arena/PvP stats from a MySQL database.

⚠️ This bot is designed specifically for OPFW-based servers and depends on its database structure.

✨ Features

/arena → View player stats by Character ID

/arena_top → Top 10 leaderboard (kills, K/D, headshots, damage)

/arena_rank → Check player rank

Read-only MySQL integration (safe)

Channel restriction support

Clean Discord embeds
___________________________________________________________________________________________________________

⚙️ Setup
1. Install dependencies
pip install -r requirements.txt
2. Create .env

DISCORD_TOKEN=your_token

DB_HOST=127.0.0.1

DB_PORT=3306

DB_USER=your_user

DB_PASSWORD=your_password

DB_NAME=your_db

ALLOWED_CHANNEL_ID=123456789012345678


3. Run
python bot.py
🗄️ Requirements (OPFW)

This bot only works with OPFW database structure, including:

Tables:

characters

leaderboard_arena

Required fields:

character_id, 

first_name, 

last_name
kills, deaths, 

hits, hits_headshot, 

damage_dealt, 

damage_taken


🛡️ Notes
✔️ OPFW only (not compatible with ESX/QBCore by default)

✔️ Does NOT modify database

✔️ Slash commands auto-sync


📦 Dependencies

discord.py

aiomysql

python-dotenv


📜 License

Free to use and modify for OPFW servers.

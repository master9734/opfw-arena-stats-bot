import os
import discord
import aiomysql
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIG
# =========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID", "0"))

ARENA_TABLE = "leaderboard_arena"   # <-- CHANGE if your table name is different

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

db_pool = None

# =========================
# DATABASE
# =========================
async def create_db_pool():
    global db_pool
    db_pool = await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        autocommit=True,
        minsize=1,
        maxsize=5
    )
    print("✅ MySQL connected")

async def ensure_db():
    global db_pool
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
    except:
        print("⚠️ DB lost, reconnecting...")
        await create_db_pool()

# =========================
# HELPERS
# =========================
def fmt_num(n):
    try:
        return f"{int(n):,}"
    except:
        return "0"

def calc_kd(kills, deaths):
    if deaths == 0:
        return round(float(kills), 2)
    return round(kills / deaths, 2)

def calc_hs_percent(headshots, hits):
    if hits == 0:
        return 0.0
    return round((headshots / hits) * 100, 2)

def check_channel(interaction: discord.Interaction):
    if ALLOWED_CHANNEL_ID != 0 and interaction.channel_id != ALLOWED_CHANNEL_ID:
        return False
    return True

# =========================
# EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    await create_db_pool()

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")

# =========================
# /arena
# =========================
@bot.tree.command(name="arena", description="Check arena stats by Character ID")
@app_commands.describe(cid="Enter Character ID")
async def arena(interaction: discord.Interaction, cid: int):
    if not check_channel(interaction):
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{ALLOWED_CHANNEL_ID}>.",
            ephemeral=True
        )
        return

    await interaction.response.defer()
    await ensure_db()

    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:

                # Character info
                await cur.execute("""
                    SELECT character_id, first_name, last_name
                    FROM characters
                    WHERE character_id = %s
                    LIMIT 1
                """, (cid,))
                char = await cur.fetchone()

                if not char:
                    await interaction.followup.send(f"❌ No character found for ID `{cid}`.")
                    return

                name = f"{char.get('first_name', 'Unknown')} {char.get('last_name', '')}".strip()

                # Arena stats
                await cur.execute(f"""
                    SELECT kills, deaths, hits, hits_headshot, damage_dealt, damage_taken
                    FROM {ARENA_TABLE}
                    WHERE character_id = %s
                    LIMIT 1
                """, (cid,))
                stats = await cur.fetchone()

                if not stats:
                    await interaction.followup.send(f"❌ No arena stats found for **{name}** (`{cid}`).")
                    return

                kills = int(stats.get("kills", 0) or 0)
                deaths = int(stats.get("deaths", 0) or 0)
                hits = int(stats.get("hits", 0) or 0)
                hs = int(stats.get("hits_headshot", 0) or 0)
                dmg_dealt = int(stats.get("damage_dealt", 0) or 0)
                dmg_taken = int(stats.get("damage_taken", 0) or 0)

                kd = calc_kd(kills, deaths)
                hs_percent = calc_hs_percent(hs, hits)

                embed = discord.Embed(
                    title="🏟️ Arena Stats",
                    description=f"**{name}** (`CID: {cid}`)",
                    color=discord.Color.blurple()
                )

                embed.add_field(name="🔫 Kills", value=fmt_num(kills), inline=True)
                embed.add_field(name="💀 Deaths", value=fmt_num(deaths), inline=True)
                embed.add_field(name="📊 K/D", value=str(kd), inline=True)

                embed.add_field(name="🎯 Hits", value=fmt_num(hits), inline=True)
                embed.add_field(name="🧠 Headshots", value=fmt_num(hs), inline=True)
                embed.add_field(name="📈 HS%", value=f"{hs_percent}%", inline=True)

                embed.add_field(name="💥 Damage Dealt", value=fmt_num(dmg_dealt), inline=True)
                embed.add_field(name="🛡️ Damage Taken", value=fmt_num(dmg_taken), inline=True)
                embed.add_field(name="🆔 Character ID", value=str(cid), inline=True)

                embed.set_footer(text="Arena stats fetched from database")

                await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error:\n```{e}```")

# =========================
# /arena_top
# =========================
@bot.tree.command(name="arena_top", description="Show top 10 arena leaderboard")
@app_commands.describe(sort_by="Sort by kills, kd, headshots, damage")
@app_commands.choices(sort_by=[
    app_commands.Choice(name="Kills", value="kills"),
    app_commands.Choice(name="K/D", value="kd"),
    app_commands.Choice(name="Headshots", value="hits_headshot"),
    app_commands.Choice(name="Damage Dealt", value="damage_dealt")
])
async def arena_top(interaction: discord.Interaction, sort_by: app_commands.Choice[str]):
    if not check_channel(interaction):
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{ALLOWED_CHANNEL_ID}>.",
            ephemeral=True
        )
        return

    await interaction.response.defer()
    await ensure_db()

    try:
        sort_value = sort_by.value

        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:

                await cur.execute(f"""
                    SELECT 
                        a.character_id,
                        a.kills,
                        a.deaths,
                        a.hits_headshot,
                        a.damage_dealt,
                        c.first_name,
                        c.last_name
                    FROM {ARENA_TABLE} a
                    LEFT JOIN characters c ON a.character_id = c.character_id
                """)
                rows = await cur.fetchall()

                if not rows:
                    await interaction.followup.send("❌ No arena leaderboard data found.")
                    return

                leaderboard = []

                for row in rows:
                    kills = int(row.get("kills", 0) or 0)
                    deaths = int(row.get("deaths", 0) or 0)
                    hs = int(row.get("hits_headshot", 0) or 0)
                    damage = int(row.get("damage_dealt", 0) or 0)
                    kd = calc_kd(kills, deaths)

                    leaderboard.append({
                        "character_id": row["character_id"],
                        "name": f"{row.get('first_name', 'Unknown')} {row.get('last_name', '')}".strip(),
                        "kills": kills,
                        "deaths": deaths,
                        "hs": hs,
                        "damage": damage,
                        "kd": kd
                    })

                if sort_value == "kd":
                    leaderboard.sort(key=lambda x: x["kd"], reverse=True)
                elif sort_value == "hits_headshot":
                    leaderboard.sort(key=lambda x: x["hs"], reverse=True)
                elif sort_value == "damage_dealt":
                    leaderboard.sort(key=lambda x: x["damage"], reverse=True)
                else:
                    leaderboard.sort(key=lambda x: x["kills"], reverse=True)

                top10 = leaderboard[:10]

                embed = discord.Embed(
                    title="🏆 Arena Top 10 Leaderboard",
                    description=f"Sorted by **{sort_by.name}**",
                    color=discord.Color.gold()
                )

                lines = []
                medals = ["🥇", "🥈", "🥉"]

                for i, player in enumerate(top10, start=1):
                    medal = medals[i - 1] if i <= 3 else f"`#{i}`"
                    lines.append(
                        f"{medal} **{player['name']}** (`{player['character_id']}`)\n"
                        f"🔫 {player['kills']} | 💀 {player['deaths']} | 📊 KD {player['kd']} | 🧠 {player['hs']}"
                    )

                embed.description = "\n\n".join(lines)
                embed.set_footer(text="Top arena players")

                await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error:\n```{e}```")

# =========================
# /arena_rank
# =========================
@bot.tree.command(name="arena_rank", description="Check a player's arena rank")
@app_commands.describe(cid="Enter Character ID", sort_by="Rank type")
@app_commands.choices(sort_by=[
    app_commands.Choice(name="Kills", value="kills"),
    app_commands.Choice(name="K/D", value="kd"),
    app_commands.Choice(name="Headshots", value="hits_headshot"),
    app_commands.Choice(name="Damage Dealt", value="damage_dealt")
])
async def arena_rank(interaction: discord.Interaction, cid: int, sort_by: app_commands.Choice[str]):
    if not check_channel(interaction):
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{ALLOWED_CHANNEL_ID}>.",
            ephemeral=True
        )
        return

    await interaction.response.defer()
    await ensure_db()

    try:
        sort_value = sort_by.value

        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:

                await cur.execute(f"""
                    SELECT 
                        a.character_id,
                        a.kills,
                        a.deaths,
                        a.hits_headshot,
                        a.damage_dealt,
                        c.first_name,
                        c.last_name
                    FROM {ARENA_TABLE} a
                    LEFT JOIN characters c ON a.character_id = c.character_id
                """)
                rows = await cur.fetchall()

                if not rows:
                    await interaction.followup.send("❌ No arena data found.")
                    return

                leaderboard = []

                for row in rows:
                    kills = int(row.get("kills", 0) or 0)
                    deaths = int(row.get("deaths", 0) or 0)
                    hs = int(row.get("hits_headshot", 0) or 0)
                    damage = int(row.get("damage_dealt", 0) or 0)
                    kd = calc_kd(kills, deaths)

                    leaderboard.append({
                        "character_id": row["character_id"],
                        "name": f"{row.get('first_name', 'Unknown')} {row.get('last_name', '')}".strip(),
                        "kills": kills,
                        "deaths": deaths,
                        "hs": hs,
                        "damage": damage,
                        "kd": kd
                    })

                if sort_value == "kd":
                    leaderboard.sort(key=lambda x: x["kd"], reverse=True)
                elif sort_value == "hits_headshot":
                    leaderboard.sort(key=lambda x: x["hs"], reverse=True)
                elif sort_value == "damage_dealt":
                    leaderboard.sort(key=lambda x: x["damage"], reverse=True)
                else:
                    leaderboard.sort(key=lambda x: x["kills"], reverse=True)

                player = None
                rank = None

                for idx, p in enumerate(leaderboard, start=1):
                    if p["character_id"] == cid:
                        player = p
                        rank = idx
                        break

                if not player:
                    await interaction.followup.send(f"❌ No arena stats found for `{cid}`.")
                    return

                embed = discord.Embed(
                    title="📍 Arena Rank",
                    description=f"**{player['name']}** (`CID: {cid}`)",
                    color=discord.Color.green()
                )

                embed.add_field(name="🏅 Rank", value=f"#{rank}", inline=True)
                embed.add_field(name="📊 Ranked By", value=sort_by.name, inline=True)
                embed.add_field(name="🔫 Kills", value=str(player["kills"]), inline=True)

                embed.add_field(name="💀 Deaths", value=str(player["deaths"]), inline=True)
                embed.add_field(name="📈 K/D", value=str(player["kd"]), inline=True)
                embed.add_field(name="🧠 Headshots", value=str(player["hs"]), inline=True)

                embed.add_field(name="💥 Damage Dealt", value=str(player["damage"]), inline=True)

                await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error:\n```{e}```")

# =========================
# RUN
# =========================
bot.run(DISCORD_TOKEN)
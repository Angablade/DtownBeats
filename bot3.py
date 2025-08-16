import discord
# Confirm py-cord runtime
try:
    logging.info(f"Using discord library version: {discord.__version__}")
except Exception:
    pass

import os
import re
import sys
import json
import random
import tempfile
import requests
import yt_dlp
import asyncio
import aiohttp
import musicbrainzngs
import shutil
import subprocess
import time
import platform
import resource
import logging
import ffmpeg

from utils.voice_utils import start_listening, stop_listening
from utils.youtube_pl import grab_youtube_pl
from utils.lyrics import Lyrics
from utils.albumart import AlbumArtFetcher
from utils.metadata import MetadataManager


from sources.youtube_mp3 import get_audio_filename
from sources.bandcamp_mp3 import get_bandcamp_audio, get_bandcamp_title
from sources.soundcloud_mp3 import get_soundcloud_audio, get_soundcloud_title
from sources.spotify_mp3 import spotify_to_youtube, get_spotify_tracks_from_playlist, get_spotify_title
from sources.apple_music_mp3 import get_apple_music_audio

from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from io import BytesIO
from aiofiles import open as aopen
from discord.ext import commands
from discord.ui import View, Button
from discord import FFmpegPCMAudio, Embed
from discord.errors import ClientException
from fuzzywuzzy import fuzz

#ENVIRONMENT VARIABLES
MUSICBRAINZ_USERAGENT = os.getenv("MUSICBRAINZ_USERAGENT", "default_user")
MUSICBRAINZ_VERSION = os.getenv("MUSICBRAINZ_VERSION", "1.0")
MUSICBRAINZ_CONTACT = os.getenv("MUSICBRAINZ_CONTACT", "default@example.com")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
EXECUTOR_MAX_WORKERS = int(os.getenv("EXECUTOR_MAX_WORKERS", "10"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_default_token")
QUEUE_PAGE_SIZE = int(os.getenv("QUEUE_PAGE_SIZE","10"))
HISTORY_PAGE_SIZE = int(os.getenv("HISTORY_PAGE_SIZE","10"))
TIMEOUT_TIME = int(os.getenv("TIMEOUT_TIME", "60"))

#CONFIGS
LOG_FILE = "config/debug.log"
CONFIG_FILE = "config/server_config.json"
VOLUME_CONFIG_PATH = "config/volume.json"
QUEUE_BACKUP_DIR = "config/queuebackup/"
BANNED_USERS_PATH = "config/banned.json"
COMMANDS_FILE_PATH = "config/commands.txt"
STATS_CONFIG_PATH = "config/stats_config.json"
BLACKLIST_PATH = "config/blackwhitelist.json"
DEBUG_CONFIG_PATH = "config/debug_mode.json"
cookies_file_path = "config/cookies.txt"

#INITIALIZATION
musicbrainzngs.set_useragent(MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)
executor = ThreadPoolExecutor(max_workers=EXECUTOR_MAX_WORKERS)
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

os.makedirs(QUEUE_BACKUP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        f.write("{}")

if not os.path.exists(cookies_file_path):
    with open(cookies_file_path, "w") as f:
        f.write("\n")

def is_owner_or_server_owner(ctx):
    if ctx.author.id == BOT_OWNER_ID:
        return True
    if ctx.author.id == ctx.guild.owner_id:
        return True
        
    return False

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({}, f)

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_server_config(guild_id):
    config = load_config()
    return config.get(str(guild_id), {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False})

def update_server_config(guild_id, key, value):
    config = load_config()
    if str(guild_id) not in config:
        config[str(guild_id)] = {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}
    config[str(guild_id)][key] = value
    save_config(config)

async def get_prefix(bot, message):
    if message.guild:
        config = get_server_config(message.guild.id)
        return config.get("prefix", "!")
    return "!"

def load_volume_settings():
    if os.path.exists(VOLUME_CONFIG_PATH):
        with open(VOLUME_CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_volume_settings(volume_data):
    with open(VOLUME_CONFIG_PATH, "w") as f:
        json.dump(volume_data, f, indent=4)

def get_backup_path(guild_id=None):
    if guild_id:
        return os.path.join(QUEUE_BACKUP_DIR, f"{guild_id}.json")
    return os.path.join(QUEUE_BACKUP_DIR, "global_backup.json")

def save_queue_backup(guild_id=None):
    try:
        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
    except Exception as e:
        logging.error("No Queues initalized. Failed to save queue backup.")

    backup_path = get_backup_path(guild_id)
    backup_data = {}
    
    if guild_id:
        backup_data[guild_id] = list(server_queues.get(guild_id, asyncio.Queue())._queue)
    else:
        for gid, queue in server_queues.items():
            backup_data[gid] = list(queue._queue)
    
    with open(backup_path, "w") as f:
        json.dump(backup_data, f, indent=4)

def load_queue_backup(guild_id=None):
    try:
        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
    except Exception as e:
        logging.error("No Queues initalized. Failed to load queue backup.")

    backup_path = get_backup_path(guild_id)
    if os.path.exists(backup_path):
        with open(backup_path, "r") as f:
            return json.load(f)
    return {}

def load_banned_users():
    if os.path.exists(BANNED_USERS_PATH):
        with open(BANNED_USERS_PATH, "r") as f:
            return json.load(f)
    return {}

def save_banned_users(banned_data):
    with open(BANNED_USERS_PATH, "w") as f:
        json.dump(banned_data, f, indent=4)

def load_stats_config():
    if os.path.exists(STATS_CONFIG_PATH):
        with open(STATS_CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"show_stats": True}

def save_stats_config(config_data):
    with open(STATS_CONFIG_PATH, "w") as f:
        json.dump(config_data, f, indent=4)

def load_blacklist():
    if os.path.exists(BLACKLIST_PATH):
        with open(BLACKLIST_PATH, "r") as f:
            return json.load(f)
    return {"blacklist": [], "whitelist": []}

def save_blacklist(data):
    with open(BLACKLIST_PATH, "w") as f:
        json.dump(data, f, indent=4)

def load_debug_mode():
    if os.path.exists(DEBUG_CONFIG_PATH):
        with open(DEBUG_CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"debug": False}

def save_debug_mode(config_data):
    with open(DEBUG_CONFIG_PATH, "w") as f:
        json.dump(config_data, f, indent=4)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.guild_messages = True

start_time = time.time()
fetcher = AlbumArtFetcher()
bot = commands.Bot(command_prefix=get_prefix, intents=intents)
os.makedirs('static', exist_ok=True)

bot.intentional_disconnections = {}
bot.timeout_tasks = {}
server_queues = {}
current_tracks = {}
queue_paused = {}
track_history = {}
autoplay_enabled = {}
message_map = {}
last_active_channels = {} 
now_playing = {}
reconnect_cooldowns = {}  # keep single definition
FAILED_CONNECTS = {}  
preload_tasks = {}

guild_volumes = load_volume_settings()
banned_users = load_banned_users()
stats_config = load_stats_config()
blacklist_data = load_blacklist()
debug_config = load_debug_mode()
metadata_manager = MetadataManager("./metacache","./config/metadataeditors.json",MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)

def hydrate_autoplay_flags():
    """Populate autoplay_enabled dict from persisted server config."""
    try:
        cfg = load_config()
        for gid, data in cfg.items():
            autoplay_enabled[int(gid)] = data.get("autoplay", False)
    except Exception:
        logging.exception("Failed to hydrate autoplay flags")

hydrate_autoplay_flags()

@bot.event
async def on_message(message):
    if message.guild:
        last_active_channels[message.guild.id] = message.channel.id
    await bot.process_commands(message)

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Mode': 'navigate',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        return None

    guild_id = guild.id
    candidate_channels = []

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def download_audio(video_id):
    try:
        if asyncio.iscoroutinefunction(get_audio_filename):
            filenam = await get_audio_filename(video_id)
        else:
            loop = asyncio.get_running_loop()
            filenam = await loop.run_in_executor(executor, get_audio_filename, video_id)

        if not filenam or not os.path.exists(filenam):
            raise ValueError(f"Downloaded file is missing or invalid for {video_id}")
        
        logging.info(f"{filenam} is ready...")
        return filenam
    except Exception as e:
        logging.error(f"Failed to download audio for {video_id}: {e}")
        raise


async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def retry_download(video_id, retries=2):
    for attempt in range(retries):
        try:
            return await download_audio(video_id)
        except Exception as e:
            logging.warning(f"[{video_id}] Retry {attempt+1} failed: {e}")
            await asyncio.sleep(1)
    logging.error(f"[{video_id}] All retries failed.")
    return None

async def check_perms(ctx, guild_id):
    if ctx.author.id in banned_users:
        await messagesender(bot, ctx.channel.id, content="You are banned from using this bot.")
        return False

    config = get_server_config(guild_id)
    dj_role_id = config.get("dj_role")
    designated_channel_id = config.get("channel")

    if dj_role_id:
        dj_role = discord.utils.get(ctx.guild.roles, id=dj_role_id)
        if dj_role not in ctx.author.roles:
            await messagesender(bot, ctx.channel.id, content="You don't have the required DJ role to use this command.")
            return False

    if designated_channel_id and ctx.channel.id != designated_channel_id:
        designated_channel = discord.utils.get(ctx.guild.channels, id=designated_channel_id)
        return False

    return True

@bot.event
async def on_voice_state_update(member, before, after):
    # Fix: guild_id was referenced before assignment causing exceptions on every voice state update.
    if member == bot.user:
        guild = before.channel.guild if before and before.channel else (after.channel.guild if after and after.channel else None)
        if guild:
            guild_id = guild.id
            # If we successfully moved/connected to a channel, clear cooldown so next intentional connect works.
            if after and after.channel:
                reconnect_cooldowns[guild_id] = 0
            try:
                if guild_id in guild_volumes:
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
            except Exception:
                logging.exception("Error setting volume after voice state update")
            if guild_id in bot.timeout_tasks:
                bot.timeout_tasks[guild_id].cancel()

async def handle_resume_on_reconnect(guild, voice_channel):
    await asyncio.sleep(2)

    guild_id = guild.id

    now = asyncio.get_event_loop().time()
    cooldown = reconnect_cooldowns.get(guild.id, 0)
    if now < cooldown:
        logging.info(f"Skipping reconnect attempt due to cooldown for guild {guild.name}")
        return

    reconnect_cooldowns[guild.id] = now + 30

    try:
        if guild.voice_client:
            await guild.voice_client.disconnect(force=True)

        voice_client = await safe_voice_connect(bot, guild, voice_channel)
        if not voice_client or not voice_client.is_connected():
            logging.error(f"[{guild.name}] Voice resume failed, skipping playback.")
            return

        paused_position = current_tracks.get(guild_id, {}).get("paused_position") or 0
        audio_file = retrieve_audio_file_for_current_track(guild_id)

        if not audio_file:
            logging.error("No audio file found to resume playback.")
            return

        video_id, video_title = current_tracks.get(guild_id, {}).get("current_track", (None, "Unknown Title"))
        logging.error(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")



        ctx = await get_ctx_from_guild(guild)
        await play_audio_in_thread(
            voice_client, audio_file, ctx,
            video_title, video_id,
            start_offset=paused_position
        )
        current_tracks[guild_id]["paused_position"] = 0

    except Exception:
        logging.exception("Failed to resume on reconnect")

async def get_ctx_from_guild(guild: discord.Guild):
    """
    Safely gets a Context object for a guild using recent channels or fallback options.
    Will use last known active or bot-used channels if available, fall back to system/first text channel,
    and DM the server owner as a last resort.
    """

    if not guild:
        logging.error("get_ctx_from_guild: No guild object provided.")
        return None

    guild_id = guild.id
    candidate_channels = []

    # 1. Try last active user message channel
    if guild_id in last_active_channels:
        chan = bot.get_channel(last_active_channels[guild_id])
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 2. Try last bot message sent channel
    last_bot_msg = message_map.get(guild_id)
    if isinstance(last_bot_msg, list) and last_bot_msg:
        chan = last_bot_msg[0].channel
        if chan and chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)

    # 3. Try system channel
    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        candidate_channels.append(guild.system_channel)

    # 4. Try any text channel where the bot can speak
    for chan in guild.text_channels:
        if chan.permissions_for(guild.me).send_messages:
            candidate_channels.append(chan)
            break

    # Try each candidate
    for channel in candidate_channels:
        try:
            temp_msg = await channel.send("🔧 Resuming playback...")
            ctx = await bot.get_context(temp_msg)
            try:
                await temp_msg.delete()
            except discord.Forbidden:
                logging.warning(f"get_ctx_from_guild: Could not delete temp message in {channel.name}")
            logging.info(f"get_ctx_from_guild: Using channel {channel.name} ({channel.id}) in guild {guild.name}")
            return ctx
        except Exception as e:
            logging.warning(f"get_ctx_from_guild: Failed to send temp message in {channel.name} ({channel.id}): {e}")

    # Final fallback: DM the owner
    try:
        owner = guild.owner
        if owner:
            dm_channel = await owner.create_dm()
            temp_msg = await dm_channel.send(f"⚠️ The bot couldn't send messages in any text channels of **{guild.name}**.\nAttempting playback recovery here.")
            ctx = await bot.get_context(temp_msg)
            logging.warning(f"get_ctx_from_guild: Fallback to DMing guild owner {owner} in guild {guild.name}")
            return ctx
    except Exception as e:
        logging.exception(f"get_ctx_from_guild: Failed to DM guild owner of {guild.name}: {e}")

    logging.error(f"get_ctx_from_guild: All fallbacks failed for guild {guild.name} ({guild.id})")
    return None

@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    await download_guild_icon(guild)
    logging.error(f"Joined new guild: {guild.name}, initialized queue.")

async def download_guild_icon(guild):
    icon = guild.icon
    if icon:
        icon_url = icon.replace(format="png")
        async with aiohttp.ClientSession() as session:
            async with session.get(str(icon_url)) as resp:
                if resp.status == 200:
                    file_path = os.path.join(f"/app/static/{guild.id}.png")
                    with open(file_path, 'wb') as f:
                        f.write(await resp.read())
                    print(f"Downloaded {guild.name}'s icon to {file_path}")
                else:
                    print(f"Failed to download icon for {guild.name}")
    else:
        print(f"{guild.name} does not have an icon.")

async def get_related_video(video_id, guild_id, retry_count=3):
    url = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(retry_count):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                html_content = await response.text()
                related_video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)

                if not related_video_ids:
                    return None

                history = track_history.get(guild_id, [])

                def is_duplicate(video_id, video_title):
                    for hist_id, hist_title in history:
                        if video_id == hist_id or fuzz.ratio(video_title.lower(), hist_title.lower()) > 70:
                            return True
                    return False

                for related_id in related_video_ids:
                    video_title = await get_youtube_video_title(related_id)

                    if video_title and not is_duplicate(related_id, video_title):
                        return related_id

                logging.error(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.error("Failed to find a new related video after 3 attempts. Stopping playback.")
    return None


def is_banned_title(title):
    banned_keywords = [
        "drake",
        "30 for 30 freestyle",
        "forever (feat kanye west, lil wayne and eminem)",
        "demons (feat fivio foreign and sosa geek)",
        "ignant shit",
        "ice melts (feat young thug)",
        "take care (feat rihanna)",
        "controlla",
        "laugh now cry later",
        "hold on, we’re going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        api_url = f"https://api.song.link/v1-alpha.1/links?Country=US&songIfSingle=true&url={url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")
                data = await response.json()
                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")
                eid = youtube_data.get("entityUniqueId")
                entity = data.get("entitiesByUniqueId", {}).get(eid, {})
                title = entity.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                return title
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")
    # Fallback HTML parse
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                resp.raise_for_status()
                html = await resp.text()
        # naive title scrape
        match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
        if match:
            raw = match.group(1).strip()
            raw = raw.replace('&amp;', '&')
            cleaned = raw.removesuffix(' - YouTube')
            if cleaned and not is_banned_title(cleaned):
                return cleaned
    except Exception as e:
        logging.error(f"Fallback title parse failed for {video_id}: {e}")
    return None

async def play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id, start_offset: int = 0):
    guild_id = ctx.guild.id
    if is_banned_title(video_title):
        await messagesender(bot, ctx.channel.id, f"🚫 `{video_title}` is blocked and cannot be played.")
        raise ValueError("Out of bounds error: This content is not allowed.")
    logging.error(f"Playing: {video_title}")
    metadata = metadata_manager.load_metadata(video_id)
    if not metadata:
        metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
        metadata_manager.save_metadata(video_id, metadata)
    artist = metadata["artist"]
    title = metadata["title"]
    duration = metadata.get("duration", "Unknown")
    image_path = fetcher.get_album_art(video_title) or "/app/albumart/default.jpg"
    file = discord.File(image_path, filename="album_art.jpg")
    embed = discord.Embed(title="Now Playing", description=f"**{title}**", color=discord.Color.blue())
    embed.set_thumbnail(url="attachment://album_art.jpg")
    embed.add_field(name="Artist", value=artist, inline=True)
    try:
        embed.add_field(name="Duration", value=(f"{int(duration)//60}:{int(duration)%60:02d}" if duration != "Unknown" else "Unknown"), inline=True)
    except Exception:
        try:
            duration = int(metadata_manager.ffmpeg_get_track_length(audio_file))
            embed.add_field(name="Duration", value=f"{duration//60}:{duration%60:02d}", inline=True)
        except Exception:
            embed.add_field(name="Duration", value="Unknown", inline=True)
    embed.set_footer(text=f"ID: {video_id}", icon_url="https://cdn.discordapp.com/avatars/1216449470149955684/137c7c7d86c6d383ae010ca347396b47.webp?size=240")
    await messagesender(bot, ctx.channel.id, embed=embed, file=file)
    current_tracks.setdefault(guild_id, {})["current_track"] = [video_id, video_title]
    current_tracks[guild_id]["start_time"] = time.time() - start_offset
    current_tracks[guild_id]["audio_file"] = audio_file
    update_now_playing(guild_id, video_id, video_title, image_path)
    def playback():
        try:
            seek_option = f"-ss {start_offset}" if start_offset > 0 else "-ss 00:00:00"
            source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options=f"-bufsize 10m {seek_option}")
            volume_level = guild_volumes.get(guild_id, 100) / 100
            source = discord.PCMVolumeTransformer(source, volume=volume_level)
            voice_client.play(source, after=lambda e: logging.error(f"Playback finished: {e}") if e else None)
        except Exception as e:
            logging.error(f"Error during playback: {e}")
    if not audio_file or not os.path.exists(audio_file):
        await messagesender(bot, ctx.channel.id, content="❌ Failed to play the track. Skipping...")
        while voice_client and voice_client.is_connected() and voice_client.is_playing():
            await asyncio.sleep(2)
        await play_next(ctx, voice_client)
        return
    await asyncio.to_thread(playback)
    if guild_id in bot.timeout_tasks:
        bot.timeout_tasks[guild_id].cancel()
    bot.timeout_tasks[guild_id] = asyncio.create_task(timeout_handler(ctx))
    if not server_queues[guild_id].empty():
        try:
            for v_id, v_title in list(server_queues[guild_id]._queue):
                if v_id.startswith("|"): continue
                if v_id not in preload_tasks:
                    preload_tasks[v_id] = asyncio.create_task(download_audio(v_id))
        except Exception:
            logging.exception("Error pre-downloading tracks")
    while voice_client.is_playing():
        await asyncio.sleep(1)

async def timeout_handler(ctx):
    guild_id = ctx.guild.id
    try:
        await asyncio.sleep(TIMEOUT_TIME)
        vc = ctx.voice_client
        if not vc:
            return
        if vc.is_playing() or queue_paused.get(guild_id):
            return
        await vc.disconnect()
        await messagesender(bot, ctx.channel.id, "⏹ Idle timeout, disconnected.")
    except asyncio.CancelledError:
        pass
    except Exception:
        logging.exception("Error in timeout_handler")

@bot.command(name="pause", aliases=["hold"])
async def pause(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        vc = ctx.voice_client
        if vc and vc.is_playing():
            current_tracks.setdefault(guild_id, {})
            current_tracks[guild_id]["paused_position"] = get_current_elapsed_time(guild_id)
            vc.pause()
            queue_paused[guild_id] = True
            await messagesender(bot, ctx.channel.id, content="Paused the music")

@bot.command(name="resume", aliases=["continue"])
async def resume(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        vc = ctx.voice_client
        if vc and vc.is_paused():
            paused_pos = current_tracks.get(guild_id, {}).get("paused_position", 0)
            if guild_id in current_tracks and paused_pos:
                current_tracks[guild_id]["start_time"] = time.time() - paused_pos
            vc.resume()
            queue_paused[guild_id] = False
            current_tracks[guild_id]["paused_position"] = 0
            await messagesender(bot, ctx.channel.id, content="Resumed the music")

@bot.command(name="move")
async def move_song(ctx, from_pos: int, to_pos: int):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        if guild_id not in server_queues:
            await messagesender(bot, ctx.channel.id, content="Queue is empty.")
            return
        queue_list = server_queues[guild_id]._queue
        if not (1 <= from_pos <= len(queue_list) and 1 <= to_pos <= len(queue_list)):
            await messagesender(bot, ctx.channel.id, content="Invalid positions.")
            return
        if from_pos == to_pos:
            await messagesender(bot, ctx.channel.id, content="Positions are the same; nothing to move.")
            return
        item = queue_list.pop(from_pos - 1)
        queue_list.insert(to_pos - 1, item)
        await messagesender(bot, ctx.channel.id, content=f"Moved '{item[1]}' to position {to_pos}.")

@bot.command(name="fetchlogs", aliases=["logs"])
async def fetchlogs(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    if not os.path.exists(LOG_FILE):
        await messagesender(bot, ctx.channel.id, content="File not found.")
        return
    file_size = os.path.getsize(LOG_FILE)
    limit = 8 * 1024 * 1024
    try:
        # Helper to send file cleanly
        async def send_file(path, display_name=None):
            try:
                await ctx.author.send(file=discord.File(path, filename=display_name or os.path.basename(path)))
            except discord.Forbidden:
                await messagesender(bot, ctx.channel.id, content="Cannot DM logs (privacy settings).")
        if file_size > limit:
            zip_path = LOG_FILE + ".zip"
            shutil.make_archive(LOG_FILE, 'zip', root_dir=os.path.dirname(LOG_FILE), base_dir=os.path.basename(LOG_FILE))
            if os.path.getsize(zip_path) > limit:
                split_path = LOG_FILE + ".7z"
                cmd = f'7z a -t7z -v7m "{split_path}" "{LOG_FILE}"'
                subprocess.run(cmd, shell=True)
                for part in sorted(f for f in os.listdir(os.path.dirname(split_path) or '.') if f.startswith(os.path.basename(split_path))):
                    await send_file(os.path.join(os.path.dirname(split_path) or '.', part))
                    os.remove(os.path.join(os.path.dirname(split_path) or '.', part))
            else:
                await send_file(zip_path)
                os.remove(zip_path)
        else:
            await send_file(LOG_FILE)
            await messagesender(bot, ctx.channel.id, content="Sent debug logs via DM.")
    except Exception:
        logging.exception("Failed to fetch logs")
        await messagesender(bot, ctx.channel.id, content="Error sending logs.")

@bot.event
async def on_ready():
    try:
        from utils.web_app import start_web_server_in_background
        start_web_server_in_background(server_queues, now_playing, track_history)
        try:
            for vc in bot.voice_clients:
                await vc.disconnect(force=True)
        except Exception:
            pass
        logging.error(f"Bot is ready! Logged in as {bot.user}")
        for guild in bot.guilds:
            file_path = os.path.join('static', f"{guild.id}.png")
            if not os.path.exists(file_path):
                await download_guild_icon(guild)
        await update_bot_presence()  # presence refresh
    except Exception as e:
        logging.error(f"Error in on_ready: {e}")

async def update_bot_presence():
    try:
        if stats_config.get("show_stats", True):
            await bot.change_presence(activity=discord.Game(name=f"Music in {len(bot.guilds)} servers"))
        else:
            await bot.change_presence(activity=None)
    except Exception:
        logging.exception("Failed to update presence")

# Add STT listen/unlisten commands if sinks available
try:
    from utils.voice_utils import HAS_SINKS as _HAS_SINKS
except Exception:
    _HAS_SINKS = False

if _HAS_SINKS:
    @bot.command(name="listen")
    async def listen_cmd(ctx):
        await start_listening(ctx)

    @bot.command(name="unlisten")
    async def unlisten_cmd(ctx):
        await stop_listening(ctx)
else:
    @bot.command(name="listen")
    async def listen_cmd(ctx):
        await ctx.send("⚠️ Voice STT unavailable (sinks not detected).")
    @bot.command(name="unlisten")
    async def unlisten_cmd(ctx):
        await ctx.send("⚠️ Voice STT unavailable (sinks not detected).")

# Entry point
if __name__ == "__main__":
    try:
        bot.run(BOT_TOKEN)
    except Exception:
        logging.exception("Bot terminated unexpectedly")

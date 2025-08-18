import discord
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
from utils.albumart import AlbumArtFetcher
from utils.metadata import MetadataManager
from utils.common import load_config_from_file_or_env, messagesender, get_server_config, safe_voice_connect

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

# Load configuration from file or environment
app_config = load_config_from_file_or_env()

#ENVIRONMENT VARIABLES
MUSICBRAINZ_USERAGENT = app_config['MUSICBRAINZ_USERAGENT']
MUSICBRAINZ_VERSION = app_config['MUSICBRAINZ_VERSION']
MUSICBRAINZ_CONTACT = app_config['MUSICBRAINZ_CONTACT']
BOT_OWNER_ID = app_config['BOT_OWNER_ID']
EXECUTOR_MAX_WORKERS = app_config['EXECUTOR_MAX_WORKERS']
BOT_TOKEN = app_config['BOT_TOKEN']
QUEUE_PAGE_SIZE = app_config['QUEUE_PAGE_SIZE']
HISTORY_PAGE_SIZE = app_config['HISTORY_PAGE_SIZE']
TIMEOUT_TIME = app_config['TIMEOUT_TIME']

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

def load_cogs():
    """Load all cog files"""
    cogs = [
             'music',
            'config',
             'admin',
        'moderation',
              'info',
             'voice',
            'lyrics',
          'metadata',
            'events',
             'queue'
    ]
    
    for cog in cogs:
        try:
            bot.load_extension(f"cmds.{cog}")
            logging.info(f"Loaded cog: {cog}")
        except Exception as e:
            logging.error(f"Failed to load cog {cog}: {e}")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.guild_messages = True

start_time = time.time()
fetcher = AlbumArtFetcher()
bot = commands.Bot(command_prefix=get_prefix, intents=intents)
load_cogs()
os.makedirs('static', exist_ok=True)

# Attach shared state to bot instance for cogs to access
bot.intentional_disconnections = {}
bot.timeout_tasks = {}
bot.server_queues = {}
bot.current_tracks = {}
bot.queue_paused = {}
bot.track_history = {}
bot.autoplay_enabled = {}
bot.message_map = {}
bot.last_active_channels = {} 
bot.now_playing = {}
bot.reconnect_cooldowns = {}
bot.FAILED_CONNECTS = {}  
bot.preload_tasks = {}
bot.start_time = start_time
bot.executor = executor

# Initialize shared data
server_queues = bot.server_queues
current_tracks = bot.current_tracks
queue_paused = bot.queue_paused
track_history = bot.track_history
autoplay_enabled = bot.autoplay_enabled
message_map = bot.message_map
last_active_channels = bot.last_active_channels
now_playing = bot.now_playing
reconnect_cooldowns = bot.reconnect_cooldowns
FAILED_CONNECTS = bot.FAILED_CONNECTS
preload_tasks = bot.preload_tasks

bot.guild_volumes = load_volume_settings()
bot.banned_users = load_banned_users()
bot.stats_config = load_stats_config()
bot.blacklist_data = load_blacklist()
bot.debug_config = load_debug_mode()
bot.metadata_manager = MetadataManager("./metacache","./config/metadataeditors.json",MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)
bot.fetcher = fetcher

guild_volumes = bot.guild_volumes
banned_users = bot.banned_users
stats_config = bot.stats_config
blacklist_data = bot.blacklist_data
debug_config = bot.debug_config
metadata_manager = bot.metadata_manager

@bot.event
async def on_message(message):
    if message.guild:
        last_active_channels[message.guild.id] = message.channel.id
    await bot.process_commands(message)

# All the helper functions remain unchanged but commands have been moved to cogs
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

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and after.channel:
        reconnect_cooldowns[member.guild.id] = 0

    if member == bot.user:
        guild = before.channel.guild if before.channel else after.channel.guild
        guild_id = guild.id

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
        logging.info(f"Resuming track '{video_title}' from position {paused_position} seconds for guild {guild_id}.")

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
    logging.info(f"Joined new guild: {guild.name}, initialized queue.")

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

                logging.info(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    logging.warning("Failed to find a new related video after 3 attempts. Stopping playback.")
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
        "hold on, we're going home",
        "hotline bling",
        "Dark Lane Demo Tapes",
        "For All the Dogs",
        "Some Sexy Songs 4 U",
        "Certified Lover Boy"
    ]
    
    title = title.lower().strip()
    
    # Check both hardcoded and stored blacklist
    return any(keyword in title for keyword in banned_keywords) or title in blacklist_data["blacklist"]

async def run_blocking_in_executor(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args))

@bot.event
async def on_ready():
    try:
        from utils.web_app import start_web_server_in_background
        start_web_server_in_background(server_queues, now_playing, track_history)
        try:
            for vc in bot.voice_clients:
                await vc.disconnect(force=True)
        except Exception as e:
            logging.warning(f"No existing voice clients to disconnect: {e}")

        logging.info(f"Bot is ready! Logged in as {bot.user}")
        for guild in bot.guilds:
                file_path = os.path.join('static', f"{guild.id}.png")
                if not os.path.exists(file_path):
                    await download_guild_icon(guild)
    except Exception as e:
        logging.error(f"Error in on_ready: {e}")


def update_now_playing(guild_id, track_id, title, album_art_url):
    now_playing[guild_id] = (track_id, title, album_art_url)

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
            'Sec-Fetch-Mode': 'navigate'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status != 200:
                    raise ValueError(f"API request failed with status {response.status}")

                data = await response.json()

                youtube_data = data.get("linksByPlatform", {}).get("youtube")
                if not youtube_data:
                    raise ValueError("YouTube data not found in API response.")

                EID = youtube_data.get("entityUniqueId")
                if not EID:
                    raise ValueError("Entity ID missing from API response.")

                entity_data = data.get("entitiesByUniqueId", {}).get(EID)
                if not entity_data:
                    raise ValueError("Entity data missing from API response.")

                title = entity_data.get("title")
                if not title:
                    raise ValueError("Title missing from API response.")

                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")

                return title

    except (aiohttp.ClientError, ValueError, KeyError) as e:
        logging.error(f"API request failed: {e}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html_content = await response.text()

                soup = BeautifulSoup(html_content, "html.parser")
                title = soup.title.string.strip().removesuffix(" - YouTube").replace("&amp;", "&")

                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")

                return title

    except (aiohttp.ClientError, AttributeError) as e:
        logging.error(f"Error fetching video title from YouTube page: {e}")
        return None

async def get_youtube_playlist_title(playlist_id):
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html_content = await response.text()
                
                match = re.search(r'var ytInitialData = ({.*?});</script>', html_content, re.DOTALL)
                if not match:
                    logging.error(f"Error: Could not find JSON metadata for {playlist_id}")
                    return "Unknown Playlist"
                
                json_data = json.loads(match.group(1))
                
                title = json_data.get("header", {}).get("playlistHeaderRenderer", {}).get("title")
                
                if not title:
                    logging.error(f"Error: Playlist title not found in metadata for {playlist_id}")
                    return "Unknown Playlist"
                
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                    
                return title
        except (aiohttp.ClientError, json.JSONDecodeError, IndexError, KeyError) as e:
            logging.error(f"Error fetching playlist title: {e}")
            return "Unknown Playlist"

async def inactivity_timeout_handler(ctx):
    """Handles inactivity timeout - disconnect after 30 seconds of inactivity"""
    await asyncio.sleep(30) 

    guild_id = ctx.guild.id
    if ctx.voice_client and ctx.voice_client.is_connected():
        # Check if autoplay is enabled and skip timeout
        if autoplay_enabled.get(guild_id, False):
            logging.info(f"Autoplay enabled in {ctx.guild.name}, skipping timeout")
            return
            
        # Check if channel has other members
        if len(ctx.voice_client.channel.members) <= 1:
            logging.info(f"Disconnecting from {ctx.guild.name} due to inactivity")
            await ctx.voice_client.disconnect()
        else:
            logging.info(f"Other members present in {ctx.guild.name}, not disconnecting")

async def update_bot_presence():
    """ Updates the bot's presence based on the stats setting. """
    if stats_config["show_stats"]:
        guild_count = len(bot.guilds)
        await bot.change_presence(activity=discord.Game(name=f"Serving {guild_count} servers"))
    else:
        await bot.change_presence(activity=None)

def get_current_elapsed_time(guild_id: int) -> int:
    """
    Returns the elapsed playback time (in seconds) for the current track in the guild.
    """
    track_state = current_tracks.get(guild_id, {})
    start_time = track_state.get("start_time")
    if start_time is None:
        return 0
    return int(time.time() - start_time)

def retrieve_audio_file_for_current_track(guild_id: int) -> str:
    """
    Returns the stored audio file path for the current track in the guild.
    """
    track_state = current_tracks.get(guild_id, {})
    return track_state.get("audio_file", None)

async def queue_and_play_next(ctx, guild_id: int, video_id: str, title=None):
    logging.info(f"Queueing video: {video_id} - {title}")
    try:
        if title is None:
            video_title = await get_youtube_video_title(video_id)
            if not video_title:
                await messagesender(bot, ctx.channel.id, content="Failed to retrieve video title.")
                return

            metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
            metadata_manager.save_metadata(video_id, metadata)
        else:
            video_title = title
            metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
            metadata_manager.save_metadata(video_id, metadata)
            video_id = f"|{video_id}"

        await server_queues[guild_id].put([video_id, video_title])
        await messagesender(bot, ctx.channel.id, f"Queued: `{video_title}`")

        if not ctx.voice_client:
            if ctx.author.voice and ctx.author.voice.channel:
                voice_client = await safe_voice_connect(bot, ctx.guild, ctx.author.voice.channel)
                if not voice_client:
                    await messagesender(bot, ctx.channel.id, content="Failed to connect to voice channel!")
                    return
            else:
                await messagesender(bot, ctx.channel.id, content="You need to be in a voice channel for me to join!")
                return

        if not ctx.voice_client.is_playing():
            asyncio.create_task(play_next(ctx, ctx.voice_client))

    except Exception as e:
        await messagesender(bot, ctx.channel.id, f"Error adding to queue: {e}")

def add_track_to_history(guild_id, video_id, video_title):
    if guild_id not in track_history:
        track_history[guild_id] = []
    track_history[guild_id].append((video_id, video_title))
    if len(track_history[guild_id]) > 20:
        track_history[guild_id].pop(0) 

async def check_empty_channel(ctx):
    """Check if voice channel is empty after 30 seconds"""
    await asyncio.sleep(30)
    guild_id = ctx.guild.id
    
    if ctx.voice_client and ctx.voice_client.is_connected():
        # Don't disconnect if autoplay is enabled
        if autoplay_enabled.get(guild_id, False):
            return
            
        # Disconnect if only the bot is in the channel
        if len(ctx.voice_client.channel.members) <= 1:
            logging.info(f"Disconnecting from empty channel in {ctx.guild.name}")
            await ctx.voice_client.disconnect()

async def fetch_playlist_videos(ctx, playlist_id: str, playlist_url: str):
    startermessage = f"Fetching playlist: ({playlist_id})\n"
    progress_message = await ctx.send(startermessage)
    bar_length = 20
    update_interval = 10

    async def update_progress(phase: str, progress: float):
        filled_length = int(bar_length * progress)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        await progress_message.edit(content=f"{startermessage}{phase}: [{bar}] {progress * 100:.1f}%")

    async with aiohttp.ClientSession() as session:
        async with session.get(playlist_url) as response:
            total_size = response.content_length or 1
            downloaded = 0
            html_content = ""

            chunk_size = max(1, total_size // update_interval)

            async for chunk in response.content.iter_any():
                html_content += chunk.decode()
                downloaded += len(chunk)

                progress = min(0.5 * (downloaded / total_size), 0.5)
                if downloaded % chunk_size == 0:
                    await update_progress("Downloading", progress)

    await update_progress("Extracting", 0.5)

    video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)
    total_videos = len(video_ids)

    if total_videos == 0:
        await progress_message.edit(content="No videos found in the playlist.")
        return video_ids

    for i, _ in enumerate(video_ids, 1):
        progress = 0.5 + (i / total_videos) * 0.5
        if i % max(1, total_videos // update_interval) == 0 or i == total_videos:
            await update_progress("Extracting", progress)

    await progress_message.edit(content=f"✅ Playlist processing complete! Found {total_videos} ID`s.")

async def play_next(ctx, voice_client):
    """Improved play_next with better error handling and simplified logic"""
    guild_id = ctx.guild.id
    
    # Don't proceed if intentionally disconnected
    if bot.intentional_disconnections.get(guild_id, False):
        logging.info(f"Skipping play_next - intentional disconnection for guild {guild_id}")
        return

    logging.info(f"Playing next track for guild {guild_id}...")
    
    try:
        while not queue_paused.get(guild_id, False):
            # Check if queue is empty
            if server_queues[guild_id].empty():
                # Try autoplay if enabled
                if autoplay_enabled.get(guild_id, False):
                    last_track_id = None
                    if track_history.get(guild_id):
                        last_track_id = track_history[guild_id][-1][0]
                    
                    if last_track_id: 
                        logging.info("Attempting autoplay...")
                        next_video = await get_related_video(last_track_id, guild_id)
                        if next_video:
                            logging.info(f"Autoplaying: {next_video}")
                            await queue_and_play_next(ctx, guild_id, next_video)
                            return
                        else:
                            await messagesender(bot, ctx.channel.id, "Autoplay stopped: No new related videos found.")
                
                # Queue is empty and no autoplay
                await messagesender(bot, ctx.channel.id, "The queue is empty.")
                await check_empty_channel(ctx)
                break

            # Get next track from queue
            try:
                videoinfo = await server_queues[guild_id].get()
                video_id, video_title = videoinfo[0], videoinfo[1]
            except Exception as e:
                logging.error(f"Error getting track from queue: {e}")
                break

            # Handle different audio sources
            if video_id.startswith("|"):
                audio_file = video_id[1:]  # Direct file path
            else:
                # Try preloaded audio first
                if video_id in preload_tasks:
                    try:
                        audio_file = await preload_tasks.pop(video_id)
                        if not audio_file:
                            raise ValueError("Preloaded file is None")
                    except Exception as e:
                        logging.warning(f"Preload task for {video_id} failed: {e}")
                        audio_file = await retry_download(video_id)
                else:
                    audio_file = await retry_download(video_id)

                if not audio_file:
                    await messagesender(bot, ctx.channel.id, f"Failed to download `{video_title}`. Skipping...")
                    continue 

            # Add to history and play
            add_track_to_history(guild_id, video_id, video_title)
            await play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id)
            break
            
    except Exception as e:
        logging.error(f"Error in play_next: {e}")
    finally:
        bot.intentional_disconnections[guild_id] = False

async def play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id, start_offset: int = 0):
    guild_id = ctx.guild.id

    # Check if content is banned
    if is_banned_title(video_title):
        await messagesender(bot, ctx.channel.id, f"🚫 `{video_title}` is blocked and cannot be played.")
        raise ValueError("Out of bounds error: This content is not allowed.")

    logging.info(f"Playing: {video_title}")
    
    # Get or fetch metadata
    metadata = metadata_manager.load_metadata(video_id)
    if not metadata:
        metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
        metadata_manager.save_metadata(video_id, metadata)

    artist = metadata.get("artist", "Unknown Artist")
    title = metadata.get("title", video_title)
    duration = metadata.get("duration", "Unknown")

    # Get album art
    image_path = fetcher.get_album_art(video_title) or "/app/albumart/default.jpg"

    # Create embed with track info
    embed = discord.Embed(
        title="Now Playing",
        description=f"**{title}**",
        color=discord.Color.blue()
    )
    
    try:
        file = discord.File(image_path, filename="album_art.jpg")
        embed.set_thumbnail(url="attachment://album_art.jpg")
    except Exception as e:
        logging.warning(f"Could not attach album art: {e}")
        file = None
        
    embed.add_field(name="Artist", value=artist, inline=True)
    
    # Format duration
    try:
        if duration != "Unknown" and duration:
            duration_int = int(float(duration))
            duration_str = f"{duration_int // 60}:{duration_int % 60:02d}"
        else:
            duration_str = "Unknown"
    except (ValueError, TypeError):
        duration_str = "Unknown"
        
    embed.add_field(name="Duration", value=duration_str, inline=True)
    embed.set_footer(text=f"ID: {video_id}", icon_url="https://cdn.discordapp.com/avatars/1216449470149955684/137c7c7d86c6d383ae010ca347396b47.webp?size=240")

    # Send now playing message
    if file:
        await messagesender(bot, ctx.channel.id, embed=embed, file=file)
    else:
        await messagesender(bot, ctx.channel.id, embed=embed)

    # Update tracking data
    current_tracks.setdefault(guild_id, {})["current_track"] = [video_id, video_title]
    current_tracks[guild_id]["start_time"] = time.time() - start_offset
    current_tracks[guild_id]["audio_file"] = audio_file
    update_now_playing(guild_id, video_id, video_title, image_path)

    # Verify audio file exists
    if not audio_file or not os.path.exists(audio_file):
        logging.error(f"Audio file not found: {audio_file}")
        await messagesender(bot, ctx.channel.id, content="❌ Failed to play the track. Skipping...")
        await play_next(ctx, voice_client)
        return

    # Start playback
    try:
        seek_option = f"-ss {start_offset}" if start_offset > 0 else ""
        options = f"-bufsize 10m {seek_option}".strip()
        
        source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options=options)
        volume_level = guild_volumes.get(guild_id, 100) / 100
        source = discord.PCMVolumeTransformer(source, volume=volume_level)
        
        voice_client.play(source, after=lambda e: logging.error(f"Playback error: {e}") if e else logging.info("Playback finished"))
        
        logging.info(f"Started playback: {title} by {artist}")
        
    except Exception as e:
        logging.error(f"Error starting playback: {e}")
        await messagesender(bot, ctx.channel.id, content="❌ Failed to start playback. Skipping...")
        await play_next(ctx, voice_client)
        return

    # Cancel existing timeout and set new one
    if guild_id in bot.timeout_tasks:
        bot.timeout_tasks[guild_id].cancel()

    bot.timeout_tasks[guild_id] = asyncio.create_task(inactivity_timeout_handler(ctx))

    # Pre-download next tracks
    if not server_queues[guild_id].empty():
        try:
            temp_queue = list(server_queues[guild_id]._queue)
            for next_video_id, next_video_title in temp_queue[:2]:  # Pre-download next 2 tracks
                if next_video_id.startswith("|"):
                    continue
                if next_video_id not in preload_tasks:
                    logging.info(f"Pre-downloading: {next_video_title}")
                    preload_tasks[next_video_id] = asyncio.create_task(download_audio(next_video_id))
        except Exception as e:
            logging.error(f"Error pre-downloading tracks: {e}")

    # Wait for playback to finish
    while voice_client and voice_client.is_playing():
        await asyncio.sleep(1)
    
    # Auto-play next track
    if voice_client and voice_client.is_connected() and not bot.intentional_disconnections.get(guild_id, False):
        await play_next(ctx, voice_client)

bot.run(BOT_TOKEN)


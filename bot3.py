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

#INITIALIZATION
musicbrainzngs.set_useragent(MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)
executor = ThreadPoolExecutor(max_workers=EXECUTOR_MAX_WORKERS)
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

os.makedirs(QUEUE_BACKUP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        f.write("{}")

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
    return config.get(str(guild_id), {"prefix": "!", "dj_role": None, "channel": None})

def update_server_config(guild_id, key, value):
    config = load_config()
    if str(guild_id) not in config:
        config[str(guild_id)] = {"prefix": "!", "dj_role": None, "channel": None}
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
    except:
        print("No Queues initalized. Failed to save queue backup.")

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
    except:
        print("No Queues initalized. Failed to load queue backup.")

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

bot.intentional_disconnections = {}
bot.timeout_tasks = {}
server_queues = {}
current_tracks = {}
queue_paused = {}
track_history = {}
autoplay_enabled = {}
message_map = {}
last_active_channels = {} 

guild_volumes = load_volume_settings()
banned_users = load_banned_users()
stats_config = load_stats_config()
blacklist_data = load_blacklist()
debug_config = load_debug_mode()
metadata_manager = MetadataManager("metacache","config/metadataeditors.json",MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)

@bot.event
async def on_message(message):
    if message.guild:
        last_active_channels[message.guild.id] = message.channel.id
    await bot.process_commands(message)

async def download_audio(video_id):
    try: 
         filenam = await get_audio_filename(video_id)
         print(f"{filenam} is playing...")
         return filenam
    except Exception as e:
        print(f"Failed to download audio: {e}")
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
    if member == bot.user:

        if before.channel is None:
            return

        guild_id = before.channel.guild.id
        try:
            if guild_id in guild_volumes:
                if before.channel.guild.voice_client:
                    before.channel.guild.voice_client.source = discord.PCMVolumeTransformer(before.channel.guild.voice_client.source)
                    before.channel.guild.voice_client.source.volume = guild_volumes[guild_id] / 100
        except:
            pass

        if guild_id in bot.timeout_tasks:
            bot.timeout_tasks[guild_id].cancel()
        
        if before.channel is None and after.channel is not None:
            bot.timeout_tasks[guild_id] = asyncio.create_task(timeout_handler(after.channel.guild))

        if before.channel is not None and after.channel is None:
            if guild_id in bot.intentional_disconnections:
                intentional_disconnection = bot.intentional_disconnections[guild_id]
            else:
                intentional_disconnection = False

            if not intentional_disconnection:
                print("Bot got disconnected from voice channel. Attempting to reconnect...")
                await asyncio.sleep(5)
                guild = before.channel.guild
                voice_channel = discord.utils.get(guild.voice_channels, id=before.channel.id)
                if voice_channel:
                    try:
                        await voice_channel.connect()
                        print("Reconnected to voice channel successfully.")
                    except Exception as e:
                        print(f"Failed to reconnect: {e}")
            else:
                bot.intentional_disconnections[guild_id] = False
    await asyncio.sleep(1)


@bot.event
async def on_guild_join(guild):
    if guild.id not in server_queues:
        server_queues[guild.id] = asyncio.Queue()
    print(f"Joined new guild: {guild.name}, initialized queue.")

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

                print(f"Retry {attempt + 1}/{retry_count}: No new videos found. Reloading page...")
                await asyncio.sleep(2)

    print("Failed to find a new related video after 3 attempts. Stopping playback.")
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

async def messagesender(bot, channel_id, content=None, embed=None, command_message=None, file=None):
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"[Error] Channel with ID {channel_id} not found.")
        return
    
    messages = []
    
    # Ensure file is a discord.File instance if provided
    if file and isinstance(file, str):
        try:
            file = discord.File(file)
        except Exception as e:
            print(f"[Error] Failed to create discord.File: {e}")
            return

    async with channel.typing():
        try:
            # All possible combinations of content, embed, and file
            if content and embed and file:
                messages.append(await channel.send(content=content, embed=embed, file=file))
            elif content and embed:
                messages.append(await channel.send(content=content, embed=embed))
            elif content and file:
                messages.append(await channel.send(content=content, file=file))
            elif embed and file:
                messages.append(await channel.send(embed=embed, file=file))
            elif content:
                # Ensure content is a string before attempting to split
                if not isinstance(content, str):
                    print("[Error] Content must be a string.")
                    return

                while content:
                    if len(content) <= 2000:
                        chunk = content
                        content = ""
                    else:
                        split_index = content.rfind(" ", 0, 2000)
                        if split_index == -1:
                            chunk = content[:2000]
                            content = content[2000:]
                        else:
                            chunk = content[:split_index]
                            content = content[split_index + 1:]
                    messages.append(await channel.send(chunk))
            elif embed:
                messages.append(await channel.send(embed=embed))
            elif file:
                messages.append(await channel.send(file=file))
            else:
                print("[Error] Either 'content', 'embed', or 'file' must be provided.")
                return
        except discord.HTTPException as e:
            print(f"[Error] Failed to send message: {e}")
            return

    if command_message:
        message_map[command_message.id] = messages



def add_track_to_history(guild_id, video_id, video_title):
    if guild_id not in track_history:
        track_history[guild_id] = []
    track_history[guild_id].append((video_id, video_title))
    if len(track_history[guild_id]) > 20:
        track_history[guild_id].pop(0) 

async def check_empty_channel(ctx):
    await asyncio.sleep(60)
    if ctx.voice_client and len(ctx.voice_client.channel.members) == 1:
        guild_id = ctx.guild.id
        if bot.intentional_disconnections.get(guild_id, False):
            return
        await ctx.voice_client.disconnect()

async def ffmpeg_get_track_length(path):
    try:
        metadata = ffmpeg.probe(path)
        duration = float(metadata['format']['duration'])
        return duration
    except ffmpeg.Error as e:
        return None

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

    await progress_message.edit(content=f"✅ Playlist processing complete! Found {total_videos} IDs.")
    return video_ids
        
async def play_next(ctx, voice_client):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if autoplay_enabled.get(guild_id, False) and bot.intentional_disconnections.get(guild_id, False):
            print("Autoplay enabled. Skipping to next")
            return

        print("Playing next track...")
        while not queue_paused.get(guild_id, False):
            if server_queues[guild_id].empty():
                if autoplay_enabled.get(guild_id, False):
                    last_track = track_history.get(guild_id, [])[-1][0] if track_history.get(guild_id) else None
                    if last_track: 
                        print("Autoplaying next track...")
                        next_video = await get_related_video(last_track, guild_id)
                        if next_video:
                            print(f"Autoplaying: {next_video}")
                            await queue_and_play_next(ctx, guild_id, next_video)
                        else:
                            await messagesender(bot, ctx.channel.id, "Autoplay stopped: No new related videos found.")
                await messagesender(bot, ctx.channel.id, "The queue is empty.")
                await check_empty_channel(ctx)
                break


            videoinfo = await server_queues[guild_id].get()
            video_id, video_title = videoinfo[0], videoinfo[1]

            if video_id[:1] == "|":
                audio_file = video_id[1:]
            else:
                audio_file = await download_audio(video_id)
                if not audio_file:
                    await messagesender(bot, ctx.channel.id, "Failed to download the track. Skipping...")
                    continue 

            add_track_to_history(guild_id, video_id, video_title)
            await play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id)

        bot.intentional_disconnections[guild_id] = False

async def play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id):
    guild_id = ctx.guild.id
    if is_banned_title(video_title):
        await messagesender(bot, ctx.channel.id, f"🚫 `{video_title}` is blocked and cannot be played.")
        raise ValueError("Out of bounds error: This content is not allowed.")

    print(f"Playing: {video_title}")
    metadata = metadata_manager.load_metadata(video_id)
    if not metadata:
        metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
        metadata_manager.save_metadata(video_id, metadata)

    artist = metadata["artist"]
    title = metadata["title"]
    duration = metadata.get("duration", "Unknown")

    image_path = fetcher.get_album_art(video_title) or "/app/albumart/default.jpg"

    file = discord.File(image_path, filename="album_art.jpg")

    print(f"Playing: {title} by {artist}")
    embed = discord.Embed(
        title="Now Playing",
        description=f"**{title}**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url="attachment://album_art.jpg")
    embed.add_field(name="Artist", value=artist, inline=True)
    embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02d}" if duration != "Unknown" else "Unknown", inline=True)

    await messagesender(bot, ctx.channel.id, embed=embed, file=file)

    current_tracks.setdefault(guild_id, {})["current_track"] = [video_id, video_title]

    def playback():
        try:
            print(f"Playing: {title} by {artist} in thread")
            source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options="-bufsize 10m -ss 00:00:00")
            volume_level = guild_volumes.get(guild_id, 100) / 100
            source = discord.PCMVolumeTransformer(source, volume=volume_level)
            voice_client.play(source, after=lambda e: print(f"Playback finished: {e}") if e else None)
        except Exception as e:
            print(f"Error during playback: {e}")

    await asyncio.to_thread(playback)

    if guild_id in bot.timeout_tasks:
        bot.timeout_tasks[guild_id].cancel()

    bot.timeout_tasks[guild_id] = asyncio.create_task(timeout_handler(ctx))

    if not server_queues[guild_id].empty():
        try:
            temp_queue = list(server_queues[guild_id].queue)
            if temp_queue:
                next_video_id, next_video_title = temp_queue[0]
                print(f"Pre-downloading next track: {next_video_title}")
                asyncio.create_task(download_audio(next_video_id))
        except Exception as e:
            print(f"Error pre-downloading the next track: {e}")

    while voice_client.is_playing():
        await asyncio.sleep(1)

@bot.event
async def on_ready():
    try:
        print(f"Bot is ready! Logged in as {bot.user}")
        await update_bot_presence()
    except Exception as e:
        print(f"Error in on_ready: {e}")

@bot.command(name="setprefix", aliases=["prefix"])
async def setprefix(ctx, prefix: str):
    if not is_owner_or_server_owner(ctx):
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    update_server_config(ctx.guild.id, "prefix", prefix)
    await messagesender(bot, ctx.channel.id, f"Prefix updated to: `{prefix}`")

@bot.command(name="setdjrole", aliases=["setrole"])
async def setdjrole(ctx, role: discord.Role):
    if not is_owner_or_server_owner(ctx):
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    update_server_config(ctx.guild.id, "dj_role", role.id)
    await messagesender(bot, ctx.channel.id, f"DJ role updated to: `{role.name}`")

@bot.command(name="setchannel")
async def setchannel(ctx, channel: discord.TextChannel):
    if not is_owner_or_server_owner(ctx):
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    update_server_config(ctx.guild.id, "channel", channel.id)
    await messagesender(bot, ctx.channel.id, f"Designated channel updated to: `{channel.name}`")

@bot.command(name="grablist", aliases=["grabplaylist"])
async def playlister(ctx, *, search: str = None):
    async with ctx.typing():
        guild_id = ctx.guild.id

        if not await check_perms(ctx, guild_id):
            return
    
        if guild_id not in server_queues:
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        if search:
            playlists_json = await grab_youtube_pl(search)
            playlists = json.loads(playlists_json) 

            if not playlists:
                await messagesender(bot, ctx.channel.id, "No playlists found for query.")
                return

            index = 0
            playlist_id = playlists[index]
            playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
            playlist_title = await get_youtube_playlist_title(playlist_id)

            while "podcast" in playlist_title.lower():
                index += 1
                if index >= len(playlists):
                    await messagesender(bot, ctx.channel.id, "No suitable playlists found (all contained 'podcast').")
                    return
                playlist_id = playlists[index]
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                playlist_title = await get_youtube_playlist_title(playlist_id)

            video_ids = await fetch_playlist_videos(ctx, playlist_id, playlist_url)
            vidscnt = len(video_ids)
            vidscrn = 0
            vidsadd = 0

            current_ids = set()
            scanning_message = await ctx.send("Scanning playlist")
            for video_id in video_ids:
                await scanning_message.edit(content=f"Scanning: {video_id} - ({vidscrn}/{vidsadd}/{vidscnt})")
                vidscrn += 1
                if video_id not in current_ids:
                    current_ids.add(video_id)
                    vidsadd += 1
                    await server_queues[guild_id].put([video_id, await get_youtube_video_title(video_id)])
                    await scanning_message.edit(content=f"Scanning: {video_id} - ({vidscrn}/{vidsadd}/{vidscnt})\nAdded: {video_id}!")

            queue_size = server_queues[guild_id].qsize()
            await scanning_message.edit(content=f"Added {queue_size} tracks from the playlist to the queue.")

            if ctx.voice_client is None:
                channel = ctx.author.voice.channel if ctx.author.voice else None
                if channel:
                    await channel.connect()
                else:
                    await scanning_message.edit(content=f"You are not in a voice channel.")
                    return

            if not ctx.voice_client.is_playing():
                await play_next(ctx, ctx.voice_client)
        else:
            await messagesender(bot, ctx.channel.id, "No search query entered!")

@bot.command(name="play")
async def play(ctx, *, srch: str):
    async with ctx.typing():
        guild_id = ctx.guild.id

        if not await check_perms(ctx, guild_id):
            return

        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        await handle_voice_connection(ctx)

        patterns = {
            "bandcamp": r"https?://.*bandcamp\.com/.*",
            "soundcloud": r"https?://.*soundcloud\.com/.*",
            "spotify": r"https?://.*spotify\.com/.*",
            "applemusic": r"https?://.*music\.apple\.com/.*",
            "youtube": r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.*"
        }

        if re.match(patterns["bandcamp"], srch):
            await bandcamp(ctx, srch)
        elif re.match(patterns["soundcloud"], srch):
            await soundcloud(ctx, srch)
        elif re.match(patterns["spotify"], srch):
            await spotify(ctx, srch)
        elif re.match(patterns["applemusic"], srch):
            await applemusic(ctx, srch)
        else:
            await youtube(ctx, search=srch)

@bot.command(name="youtube", aliases=["yt"])
async def youtube(ctx, *, search: str = None):
    async with ctx.typing():
        guild_id = ctx.guild.id
    
        if not await check_perms(ctx, guild_id):
            return

        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        await handle_voice_connection(ctx)
    
        if search:
            if "playlist" in search and "list=" in search:
                playlist_id = search.split("list=")[-1]
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                video_ids = await fetch_playlist_videos(ctx, playlist_id, playlist_url)
                current_ids = set() 

                scanning_message = await ctx.send(f"Scanning playlist")
                for video_id in video_ids:
                    await scanning_message.edit(content=f"Scanned: {video_id}")
                    if video_id not in current_ids:
                        current_ids.add(video_id)
                        await server_queues[guild_id].put([video_id, await get_youtube_video_title(video_id)])
                        await scanning_message.edit(content=f"added: {video_id}!")

                await messagesender(bot, ctx.channel.id, f"Added {server_queues[guild_id].qsize()} tracks from the playlist to the queue.")
                if not ctx.voice_client.is_playing():
                    await play_next(ctx, ctx.voice_client)
            else:
                video_id = await fetch_video_id(ctx, search)
                if video_id:
                    await queue_and_play_next(ctx, guild_id, video_id)
                else:
                    await messagesender(bot, ctx.channel.id, content="Failed to find the song.")

async def handle_voice_connection(ctx):
    guild_id = ctx.guild.id
    voice_channel = ctx.author.voice.channel
    if not ctx.voice_client:
        bot.intentional_disconnections[guild_id] = False
        await voice_channel.connect()

async def fetch_video_id(ctx, search: str) -> str:
    if is_banned_title(search):
        raise ValueError("Out of bounds error: This content is not allowed.")
        
    youtube_id_match = re.match(
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/|music\.youtube\.com/watch\?v=)?([\w-]{11})', 
        search
    )
    direct_file_match = re.match(r'(https?://\S+\.(mp3|wav|aac|flac))', search)

    if youtube_id_match:
        return youtube_id_match.group(1)
    elif direct_file_match:
        await messagesender(bot, ctx.channel.id, f"Queued direct file: {search}")
        return search
    else:
        return await fetch_video_id_from_ytsearch(search, ctx)

async def fetch_video_id_from_ytsearch(search: str, ctx):
    loop = asyncio.get_running_loop()
    
    def run_yt_dlp(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                if "entries" not in info or not info["entries"]:
                    return None
                return info["entries"][0]["id"]
            except Exception:
                return None
    
    ydl_opts_music = {
        "default_search": "ytsearch1",
        "quiet": True,
        "no_warnings": True,
        "youtube_include_dash_manifest": False,
        "extract_flat": True,
        "source_address": "0.0.0.0",
        "geo_bypass": True,
        "noplaylist": True,
        "force_generic_extractor": True,
        "format": "bestaudio",
        "cookiesfrombrowser": ("chrome",),
        "youtube_include_hls_manifest": False,
        "force_url": "https://music.youtube.com/"
    }
    
    result = await loop.run_in_executor(None, lambda: run_yt_dlp(ydl_opts_music))
    
    if not result:
        ydl_opts_regular = {
            "default_search": "ytsearch1",
            "quiet": True,
            "no_warnings": True,
        }
        result = await loop.run_in_executor(None, lambda: run_yt_dlp(ydl_opts_regular))
    
    if not result:
        await messagesender(bot, ctx.channel.id, f"Failed to find a song for: `{search}`")
        return None
    
    return result

async def queue_and_play_next(ctx, guild_id: int, video_id: str, title=None):
    try:
        if title is None:
            video_title = await get_youtube_video_title(video_id)
            if not video_title:
                await messagesender(bot, ctx.channel.id, content="Failed to retrieve video title.")
                return
        else:
            video_title = title
            video_id = f"|{video_id}"

        # Fetch and cache metadata
        metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
        metadata_manager.save_metadata(video_id, metadata)

        await server_queues[guild_id].put([video_id, video_title])
        await messagesender(bot, ctx.channel.id, f"Queued: `{video_title}`")

        if not ctx.voice_client:
            if ctx.author.voice and ctx.author.voice.channel:
                await ctx.author.voice.channel.connect()
            else:
                await messagesender(bot, ctx.channel.id, content="You need to be in a voice channel for me to join!")
                return

        if not ctx.voice_client.is_playing():
            asyncio.create_task(play_next(ctx, ctx.voice_client))

    except Exception as e:
        await messagesender(bot, ctx.channel.id, f"Error adding to queue: {e}")


@bot.command(name="skip", aliases=["next"])
async def skip(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await messagesender(bot, ctx.channel.id, content="Skipped the current track.")

@bot.command(name="stop")
async def stop(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if ctx.voice_client:
            bot.intentional_disconnections[guild_id] = True
            await ctx.voice_client.disconnect()
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}
            await messagesender(bot, ctx.channel.id, content="Stopped the bot and left the voice channel.")

@bot.command(name="pause", aliases=["hold"])
async def pause(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            queue_paused[guild_id] = True
            await messagesender(bot, ctx.channel.id, content="Paused the music")

@bot.command(name="resume", aliases=["continue"])
async def resume(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            queue_paused[guild_id] = False
            await messagesender(bot, ctx.channel.id, content="Resumed the music")

@bot.command(name="queue", aliases=["list"])
async def show_queue(ctx, page: int = 1):
    async with ctx.typing():
        guild_id = ctx.guild.id

        if not server_queues.get(guild_id) or server_queues[guild_id].empty():
            await messagesender(bot, ctx.channel.id, content="The queue is empty.")
            return

        queue = list(server_queues[guild_id]._queue)
    
        items_per_page = QUEUE_PAGE_SIZE
        total_pages = (len(queue) + items_per_page - 1) // items_per_page
    
        if page < 1 or page > total_pages:
            await messagesender(bot, ctx.channel.id, f"Invalid page number. Please enter a number between 1 and {total_pages}.")
            return

        start_index = (page - 1) * items_per_page
        end_index = min(start_index + items_per_page, len(queue))
    
        queue_slice = queue[start_index:end_index]
        embed = discord.Embed(title=f"Music Queue (Page {page} of {total_pages})", color=discord.Color.blue())
    
        for index, item in enumerate(queue_slice, start=start_index + 1):
            try:
                video_id = ''.join(item[:1]) 
                video_title = ''.join(item[1:])  
                embed.add_field(name=f"{index}. {video_id}", value=video_title, inline=False)
            except:
                print("Something was borked.")
        await messagesender(bot, ctx.channel.id, embed=embed)

@bot.command(name="search", aliases=["find"])
async def search(ctx, *, query: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
    
        ydl_opts = {"default_search": "ytsearch10", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                results = info['entries']
            
                if not results:
                    await messagesender(bot, ctx.channel.id, content="No search results found.")
                    return
            
                embed = discord.Embed(title=f"Search Results: {query}", color=discord.Color.green())
                for entry in results[:10]:
                    video_id = entry['id']
                    video_title = entry['title']
                
                    embed.add_field(name=video_title, value=f"```{ctx.prefix}yt {video_id}```", inline=False)
                await messagesender(bot, ctx.channel.id, embed=embed)
        
            except Exception as e:
                await messagesender(bot, ctx.channel.id, f"Failed to search: {e}")

@bot.command(name="clear")
async def clear(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if server_queues.get(guild_id):
            server_queues[guild_id]._queue.clear()
        await messagesender(bot, ctx.channel.id, content="Cleared the queue.")

@bot.command(name="remove")
async def remove(ctx, index: int):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        try:
            removed = server_queues[guild_id]._queue.pop(index - 1)
            await messagesender(bot, ctx.channel.id, f"Removed track {removed} from the queue.")
        except IndexError:
            await messagesender(bot, ctx.channel.id, content="Invalid index.")

@bot.command(name="loop", aliases=["repeat"])
async def loop(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        current_tracks[guild_id]["is_looping"] = not current_tracks[guild_id].get("is_looping", False)
        await messagesender(bot, ctx.channel.id, content="Looping " + ("enabled." if current_tracks[guild_id]["is_looping"] else "disabled."))

@bot.command(name="nowplaying", aliases=["current", "np"])
async def nowplaying(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return

        current_track = current_tracks.get(guild_id, {}).get("current_track")
        if not current_track:
            await messagesender(bot, ctx.channel.id, content="No track is currently playing.")
            return

        video_id = current_track[0]
        metadata = metadata_manager.load_metadata(video_id)
        if not metadata:
            video_title = current_track[1]
            metadata = metadata_manager.get_or_fetch_metadata(video_id, video_title)
            metadata_manager.save_metadata(video_id, metadata)

        artist = metadata["artist"]
        title = metadata["title"]
        duration = metadata.get("duration", "Unknown")

        image_path = fetcher.get_album_art(title)
        if not image_path:
            image_path = "/app/albumart/default.jpg"

        file = discord.File(image_path, filename="album_art.jpg")

        embed = discord.Embed(
            title="Now Playing",
            description=f"**{title}**",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url="attachment://album_art.jpg")
        embed.add_field(name="Artist", value=artist, inline=True)
        embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02d}" if duration != "Unknown" else "Unknown", inline=True)

        await messagesender(bot, ctx.channel.id, embed=embed, file=file)


@bot.command(name="shutdown", aliases=["die"])
async def shutdown(ctx):
    print(f"Requesting ID: {ctx.author.id}\nOwner ID:{BOT_OWNER_ID}")
    if ctx.author.id == BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="Shutting down.")
        await bot.close()
    else:
        await messagesender(bot, ctx.channel.id, content="You do not have permission to shut down the bot.")

@bot.command(name="reboot", aliases=["restart"])
async def reboot(ctx):
    print(f"Requesting ID: {ctx.author.id}\nOwner ID:{BOT_OWNER_ID}")
    if ctx.author.id == BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="Restarting the bot...")
        os.execv(sys.executable, ['python'] + sys.argv)
    else:
        await messagesender(bot, ctx.channel.id, content="You do not have permission to restart the bot.")

@bot.command(name="dockboot", aliases=["dockerrestart"])
async def dockboot(ctx):
    print(f"Requesting ID: {ctx.author.id}\nOwner ID: {BOT_OWNER_ID}")
    if ctx.author.id == BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="Shutting down and restarting")
        subprocess.Popen(["/bin/bash", "init.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os._exit(0)  
    else:
        await messagesender(bot, ctx.channel.id, content="You do not have permission to restart the bot.")

@bot.command(name="seek")
async def seek(ctx, position: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
    
        if not await check_perms(ctx, guild_id):
            return
        
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await messagesender(bot, ctx.channel.id, content="There's no audio currently playing.")
            return

        current_track = current_tracks.get(guild_id, {}).get("current_track")
        if not current_track:
            await messagesender(bot, ctx.channel.id, content="There's no track information available to seek.")
            return
    
        video_id = current_track[0]
        audio_file = f"music/{video_id}.mp3"
        if not os.path.exists(audio_file):
            await messagesender(bot, ctx.channel.id, content="Audio file not found for seeking.")
            return
        def get_audio_duration(file_path):
            try:
                result = subprocess.run(
                    ["ffmpeg", "-i", file_path, "-f", "null", "-"],
                    stderr=subprocess.PIPE,
                    text=True
                )
                duration_line = [line for line in result.stderr.split("\n") if "Duration" in line]
                if duration_line:
                    time_str = duration_line[0].split(",")[0].split("Duration:")[1].strip()
                    h, m, s = map(float, time_str.split(":"))
                    return int(h * 3600 + m * 60 + s)
            except Exception as e:
                print(f"Error getting duration: {e}")
            return None

        duration = get_audio_duration(audio_file)
        if not duration:
            await messagesender(bot, ctx.channel.id, content="Could not determine audio duration.")
            return

        try:
            if position.endswith("%"):
                percent = int(position.strip("%"))
                if not (0 <= percent <= 100):
                    raise ValueError("Percentage must be between 0 and 100.")
                seconds = int(duration * (percent / 100))
            elif ":" in position:
                minutes, seconds = map(int, position.split(":"))
                seconds = minutes * 60 + seconds
            else:
                seconds = int(position)
        
            if seconds < 0 or seconds > duration:
                raise ValueError(f"Position must be between 0 and {duration} seconds.")

            ctx.voice_client.stop()
            ffmpeg_options = f"-ss {seconds} -bufsize 10m"
            source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options=ffmpeg_options)
            ctx.voice_client.play(source, after=lambda _: asyncio.run_coroutine_threadsafe(play_next(ctx, ctx.voice_client), bot.loop))

            await messagesender(bot, ctx.channel.id, f"⏩ Seeking to `{seconds}` seconds.")
    
        except Exception as e:
            await messagesender(bot, ctx.channel.id, f"An error occurred while seeking: {e}")

@bot.command(name="setnick", aliases=["nickname"])
async def setnick(ctx, *, nickname: str = None):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return

    try:
        await ctx.guild.me.edit(nick=nickname)
        await messagesender(bot, ctx.channel.id, content=f"Bot nickname changed to `{nickname}`")
    except Exception as e:
        await messagesender(bot, ctx.channel.id, content=f"Failed to change nickname: {e}")

@bot.command(name="cmds", aliases=["commands"])
async def help_command(ctx):
    async with ctx.typing():
        commands_text = """Available Commands:
        
        🎵 **Music Commands**
        Command           | Aliases        | Description
        ------------------|----------------|---------------------------------
        play <query>      | None           | Play a song
        pause             | hold           | Pause the music
        resume            | continue       | Resume the music
        stop              | None           | Stop the bot
        queue             | list           | Show the current queue
        skip              | next           | Skip the current song
        seek <time/%>     | None           | Seek to a timestamp or percentage
        volume <0-200>    | vol            | Adjust playback volume
        autoplay <on/off> | autodj         | Toggle autoplay mode
        
        ⌚ **Queue Commands**
        Command           | Aliases        | Description
        ------------------|----------------|---------------------------------
        clear             | None           | Clear the queue
        remove <#>        | None           | Remove a song from the queue
        loop              | repeat         | Toggle looping
        shuffle           | None           | Shuffle the queue
        move <#> <#>      | None           | Move a song in the queue
        history           | played         | Show recently played tracks
        
        ⚙️ **Configuration**
        Command            | Aliases        | Description
        -------------------|----------------|--------------------------------
        setprefix <p>      | prefix         | Change the bot prefix
        setdjrole <r>      | setrole        | Assign DJ role
        setchannel <c>     | None           | Restrict bot to a channel
        debugmode          | None           | Toggle debug logging
        showstats          | None           | Toggle bot stats in profile
        
        🛠️ **Admin Commands**
        Command           | Aliases        | Description
        ------------------|----------------|---------------------------------
        shutdown          | die            | Shut down the bot
        reboot            | restart        | Restart the bot
        backupqueue       | None           | Backup current queue
        restorequeue      | None           | Restore a queue
        banuser @user     | None           | Ban a user from bot
        unbanuser @user   | None           | Unban a user
        bannedlist        | None           | Show banned users
        purgequeues       | None           | Clear queues across all servers
        
        📜 **Other Commands**
        Command           | Aliases        | Description
        ------------------|----------------|---------------------------------
        version           | ver            | Show bot version
        stats             | None           | Show bot statistics
        invite            | link           | Get bot invite link
        sendplox          | None           | Send current track as a file
        sendglobalmsg     | None           | Send a message to all servers
        blacklist <song>  | None           | Block a specific song
        whitelist <song>  | None           | Remove a song from the blacklist
        """
        
        with open(COMMANDS_FILE_PATH, "w") as f:
            f.write(commands_text)
     
        try:
            await ctx.author.send(file=discord.File(COMMANDS_FILE_PATH))
            await ctx.send(f"{ctx.author.mention}, I've sent you the command list as a file.")
        except discord.Forbidden:
            await ctx.send(f"{ctx.author.mention}, I couldn't send you a DM. Please check your privacy settings.")

@bot.command(name="mute", aliases=["quiet"])
async def toggle_mute(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        voice_client = ctx.voice_client

        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            if voice_client.is_paused():
                voice_client.resume()
                await messagesender(bot, ctx.channel.id, content="Unmuted the bot. 🔊")
            else:
                voice_client.pause()
                await messagesender(bot, ctx.channel.id, content="Muted the bot. 🔇")
        else:
            await messagesender(bot, ctx.channel.id, content="I'm not playing anything to mute or unmute.")

@bot.command(name="lyrics", aliases=["lyr"])
async def lyrics(ctx, *, song: str = None):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        queue = list(server_queues.get(guild_id, asyncio.Queue())._queue)   
        lyrics_fetcher = Lyrics(ctx, queue)

        try:
            if not song:
                current_track = current_tracks.get(guild_id, {}).get("current_track")
                if not current_track:
                    await messagesender(bot, ctx.channel.id, content="No song is currently playing.")
                    return
                video_title = ''.join(current_track[1:])
            else:
                video_id = await fetch_video_id_from_ytsearch(song, ctx)
                if not video_id:
                    return 
                video_title = await get_youtube_video_title(video_id)

            result = musicbrainzngs.search_recordings(query=video_title, limit=1)
            if not result["recording-list"]:
                await messagesender(bot, ctx.channel.id, f"No matching song found on MusicBrainz for: {song}")
                return

            recording = result["recording-list"][0]
            artist_name = recording["artist-credit"][0]["artist"]["name"]
            track_title = recording["title"]

            lyrics = lyrics_fetcher.get_lyrics(track_title, artist_name)
            if lyrics:
                embed = Embed(
                    title=f"Lyrics: {track_title} by {artist_name}",
                    description=lyrics[:2048],
                    color=discord.Color.purple()
                )
                await messagesender(bot, ctx.channel.id, embed=embed)
            else:
                await messagesender(bot, ctx.channel.id, f"Lyrics not found for: {track_title} by {artist_name}")

        except Exception as e:
            await messagesender(bot, ctx.channel.id, f"An error occurred: {e}")

@bot.command(name="volume", aliases=["vol"])
async def volume(ctx, volume: int):
    async with ctx.typing():
        guild_id = ctx.guild.id
        
        if not await check_perms(ctx, guild_id):
            return
        
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await messagesender(bot, ctx.channel.id, content="There's no audio currently playing.")
            return
        
        if 0 <= volume <= 200:
            ctx.voice_client.source = discord.PCMVolumeTransformer(ctx.voice_client.source)
            ctx.voice_client.source.volume = volume / 100
            guild_volumes[guild_id] = volume
            save_volume_settings(guild_volumes)
            await messagesender(bot, ctx.channel.id, f"Volume set to {volume}% and saved.")
        else:
            await messagesender(bot, ctx.channel.id, content="Volume must be between 0 and 200.")

@bot.command(name="shuffle")
async def shuffle_queue(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if server_queues.get(guild_id) and len(server_queues[guild_id]._queue) > 1:
            random.shuffle(server_queues[guild_id]._queue)
            await messagesender(bot, ctx.channel.id, content="The queue has been shuffled! 🔀")
        else:
            await messagesender(bot, ctx.channel.id, content="The queue is too short to shuffle.")

@bot.command(name="invite", aliases=["link"])
async def invite(ctx):
    bot_id = bot.user.id 
    permissions = 277025515584
    scopes = "bot"
    invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions={permissions}&scope={scopes}"
    await ctx.author.send(f"<:afoyawn:1330375212302336030> Invite me to your server using this link: {invite_url}")

@bot.command(name="move")
async def move_song(ctx, from_pos: int, to_pos: int):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        queue = server_queues.get(guild_id)._queue if server_queues.get(guild_id) else None

        if queue and 1 <= from_pos <= len(queue) and 1 <= to_pos <= len(queue):
            from_pos -= 1
            to_pos -= 1
            track = queue[from_pos]
            del queue[from_pos]
            queue.insert(to_pos, track)

            await messagesender(bot, ctx.channel.id, f"Moved **{''.join(track[1:])}** from position {from_pos + 1} to {to_pos + 1}.")
        else:
            await messagesender(bot, ctx.channel.id, content="Invalid positions. Please provide valid track numbers from the queue.")

@bot.command(name="join", aliases=["come"])
async def join_channel(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
    
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            bot.intentional_disconnections[guild_id] = False
            await channel.connect()
            await messagesender(bot, ctx.channel.id, f"Joined **{channel.name}** voice channel. 🎤")
        else:
            await messagesender(bot, ctx.channel.id, content="You need to be in a voice channel for me to join!")

@bot.command(name="leave", aliases=["go"])
async def leave_channel(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return
        
        if ctx.voice_client:
            bot.intentional_disconnections[guild_id] = True
            await ctx.voice_client.disconnect()
            await messagesender(bot, ctx.channel.id, content="Disconnected from the voice channel. 👋")
        else:
            await messagesender(bot, ctx.channel.id, content="I'm not in a voice channel to leave.")

@bot.command(name="forceplay", aliases=["fplay"])
async def forceplay(ctx, *, query: str):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return

    guild_id = ctx.guild.id
    await messagesender(bot, ctx.channel.id, content=f"Forcing playback for: {query}")
    await play(ctx, srch=query)
    await asyncio.sleep(1) 

    if ctx.voice_client and ctx.voice_client.is_playing():
        print("Having to move things.")
        queue = server_queues.get(guild_id)._queue if server_queues.get(guild_id) else None

        if queue and len(queue) > 1: 
            from_pos = len(queue) - 1
            to_pos = 1
            try:
                from_pos -= 1
                to_pos -= 1
                track = queue[from_pos]
                del queue[from_pos]
                queue.insert(to_pos, track)
            except IndexError:
                print("Error moving track in fplay: Invalid index")

        ctx.voice_client.stop()


@bot.command(name="backupqueue")
async def backup_queue(ctx, scope: str = "guild"):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if scope == "global":
        save_queue_backup()
        await messagesender(bot, ctx.channel.id, content="Global queue backup saved.")
    else:
        save_queue_backup(ctx.guild.id)
        await messagesender(bot, ctx.channel.id, content=f"Queue backup saved for {ctx.guild.name}.")

@bot.command(name="restorequeue")
async def restore_queue(ctx, scope: str = "guild"):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if scope == "global":
        backup_data = load_queue_backup()
        for gid, queue_data in backup_data.items():
            if gid not in server_queues:
                server_queues[gid] = asyncio.Queue()
            for item in queue_data:
                await server_queues[gid].put(item)
        await messagesender(bot, ctx.channel.id, content="Global queue restored.")
    else:
        backup_data = load_queue_backup(ctx.guild.id)
        if ctx.guild.id not in server_queues:
            server_queues[ctx.guild.id] = asyncio.Queue()
        for item in backup_data.get(str(ctx.guild.id), []):
            await server_queues[ctx.guild.id].put(item)
        await messagesender(bot, ctx.channel.id, content=f"Queue restored for {ctx.guild.name}.")

@bot.command(name="banuser")
async def banuser(ctx, user: discord.User):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    banned_users[user.id] = user.name
    save_banned_users(banned_users)
    await messagesender(bot, ctx.channel.id, content=f"{user.name} has been banned from using the bot.")

@bot.command(name="unbanuser")
async def unbanuser(ctx, user: discord.User):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if user.id in banned_users:
        del banned_users[user.id]
        save_banned_users(banned_users)
        await messagesender(bot, ctx.channel.id, content=f"{user.name} has been unbanned from using the bot.")
    else:
        await messagesender(bot, ctx.channel.id, content=f"{user.name} is not banned.")

@bot.command(name="bannedlist")
async def bannedlist(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if not banned_users:
        await messagesender(bot, ctx.channel.id, content="No users are currently banned.")
    else:
        banned_list = "\n".join([f"{uid}: {name}" for uid, name in banned_users.items()])
        await messagesender(bot, ctx.channel.id, content=f"Banned Users:\n{banned_list}")

@bot.command(name="fetchlogs", aliases=["logs"])
async def fetchlogs(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return

    if not os.path.exists(LOG_FILE):
        await messagesender(bot, ctx.channel.id, content="File not found.")
        return

    file_size = os.path.getsize(LOG_FILE)
    if file_size > 8 * 1024 * 1024:
        zip_path = LOG_FILE + ".zip"
        shutil.make_archive(LOG_FILE, 'zip', root_dir=os.path.dirname(LOG_FILE), base_dir=os.path.basename(LOG_FILE))
        zip_size = os.path.getsize(zip_path)
        if zip_size > 8 * 1024 * 1024:
            split_path = LOG_FILE + ".7z"
            split_command = f'7z a -t7z -v7m "{split_path}" "{LOG_FILE}"'
            subprocess.run(split_command, shell=True)
            split_parts = [f for f in os.listdir(os.path.dirname(LOG_FILE)) if f.startswith(os.path.basename(split_path))]
            for part in sorted(split_parts):
                part_path = os.path.join(os.path.dirname(LOG_FILE), part)
                await ctx.author.send(file=discord.File(part_path))
                os.remove(part_path)
        else:
            with open(zip_path, 'rb') as file:
                await ctx.author.typing()
                await ctx.author.send(file=discord.File(file, filename=os.path.basename(zip_path)))
            os.remove(zip_path) 
    else:
        with open(LOG_FILE, 'rb') as file:
            await ctx.author.typing()
            await ctx.author.send(file=discord.File(file, filename=os.path.basename(LOG_FILE)))
            await messagesender(bot, ctx.channel.id, content="Sent debug logs via DM.")

@bot.command(name="version", aliases=["ver"])
async def version(ctx):
    async with ctx.typing():
                                            #[HHMMSS-DDMMYYYY]
        embed = discord.Embed(
            title=f"DtownBeats - Version 0.4E [173344-08032025]",
            description="🎵 Bringing beats to your server with style!",
            color=discord.Color.dark_blue()
        )

        embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/1216449470149955684/137c7c7d86c6d383ae010ca347396b47.webp?size=240")
    
        embed.add_field(name="", value=(""), inline=False)

        embed.add_field(
            name="📜 Source Code",
            value="[GitHub Repository](https://github.com/Angablade/DtownBeats)",
            inline=False
        )

        embed.add_field(name="", value=(""), inline=False)

        embed.add_field(
            name="🐳 Docker Image",
            value="```\ndocker pull angablade/dtownbeats:latest```",
            inline=False
        )
    
        embed.add_field(name="", value=(""), inline=False)

        embed.set_footer(
            text=f"Created by Angablade",
            icon_url="https://img.angablade.com/ab-w.png"
        )

        try:
            await ctx.author.send(embed=embed)
            await messagesender(bot, ctx.channel.id, content="I've sent you a DM with the bot version. 📬")
        except discord.Forbidden:
            await messagesender(bot, ctx.channel.id, content="I couldn't send you a DM. Please check your privacy settings.")

import os
import shutil
import subprocess
import discord

@bot.command(name="sendplox", aliases=["dlfile"])
async def sendmp3(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return

        dir_path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/")
        current_track = current_tracks.get(guild_id, {}).get("current_track")
        
        if not current_track:
            await messagesender(bot, ctx.channel.id, content="No current track found.")
            return
        
        base_filename, _ = os.path.splitext(current_track)
        
        possible_extensions = [".mp3", ".opus"]
        
        file_path = None
        for ext in possible_extensions:
            path = f"music/{base_filename}{ext}"
            if os.path.exists(path):
                file_path = path
                break
        
        if not file_path:
            await messagesender(bot, ctx.channel.id, content="File not found.")
            return

        file_size = os.path.getsize(file_path)
        if file_size > 8 * 1024 * 1024:
            zip_path = file_path + ".zip"
            shutil.make_archive(file_path, 'zip', root_dir=os.path.dirname(file_path), base_dir=os.path.basename(file_path))
            zip_size = os.path.getsize(zip_path)
            if zip_size > 8 * 1024 * 1024:
                split_path = file_path + ".7z"
                split_command = f'7z a -t7z -v7m "{split_path}" "{file_path}"'
                subprocess.run(split_command, shell=True)
                split_parts = [f for f in os.listdir(os.path.dirname(file_path)) if f.startswith(os.path.basename(split_path))]
                for part in sorted(split_parts):
                    part_path = os.path.join(os.path.dirname(file_path), part)
                    await ctx.author.send(file=discord.File(part_path))
                    os.remove(part_path)
            else:
                with open(zip_path, 'rb') as file:
                    await ctx.author.typing()
                    await ctx.author.send(file=discord.File(file, filename=os.path.basename(zip_path)))
                os.remove(zip_path) 
        else:
            with open(file_path, 'rb') as file:
                await ctx.author.typing()
                await ctx.author.send(file=discord.File(file, filename=os.path.basename(file_path)))


@bot.command(name="blacklist")
async def blacklist(ctx, *, song: str):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if song.lower() not in blacklist_data["blacklist"]:
        blacklist_data["blacklist"].append(song.lower())
        save_blacklist(blacklist_data)
        await messagesender(bot, ctx.channel.id, content=f"`{song}` has been blacklisted.")
    else:
        await messagesender(bot, ctx.channel.id, content=f"`{song}` is already blacklisted.")

@bot.command(name="whitelist")
async def whitelist(ctx, *, song: str):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    if song.lower() in blacklist_data["blacklist"]:
        blacklist_data["blacklist"].remove(song.lower())
        save_blacklist(blacklist_data)
        await messagesender(bot, ctx.channel.id, content=f"`{song}` has been removed from the blacklist.")
    else:
        await messagesender(bot, ctx.channel.id, content=f"`{song}` is not in the blacklist.")

@bot.command(name="blacklistcheck")
async def blacklist_check(ctx, *, song: str):
    if is_banned_title(song):
        await messagesender(bot, ctx.channel.id, content=f"`{song}` is blacklisted.")
    else:
        await messagesender(bot, ctx.channel.id, content=f"`{song}` is not blacklisted.")

@bot.command(name="debugmode")
async def toggle_debug(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    debug_config["debug"] = not debug_config["debug"]
    save_debug_mode(debug_config)
    state = "enabled" if debug_config["debug"] else "disabled"
    await messagesender(bot, ctx.channel.id, content=f"Debug mode has been {state}.")

@bot.command(name="bandcamp", aliases=["bc"])
async def bandcamp(ctx, url: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
    
        if not await check_perms(ctx, guild_id):
            return

        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        await handle_voice_connection(ctx)
    
        await messagesender(bot, ctx.channel.id, f"Processing Bandcamp link: <{url}>")
        file_path = await get_bandcamp_audio(url)
        if file_path:
            trackdata = await get_bandcamp_title(url)
            await queue_and_play_next(ctx, ctx.guild.id, file_path, trackdata)
        else:
            await messagesender(bot, ctx.channel.id, "Failed to process Bandcamp track.")

@bot.command(name="soundcloud", aliases=["sc"])
async def soundcloud(ctx, url: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
    
        if not await check_perms(ctx, guild_id):
            return

        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        await handle_voice_connection(ctx)
    
        await messagesender(bot, ctx.channel.id, f"Processing SoundCloud link: <{url}>")
        file_path = await get_soundcloud_audio(url)
        soundcloud_title = await get_soundcloud_title(url)
        if file_path:
            await queue_and_play_next(ctx, ctx.guild.id, file_path, soundcloud_title)
        else:
            await messagesender(bot, ctx.channel.id, f"Failed to process SoundCloud track. ({file_path})")

@bot.command(name="spotify", aliases=["sp"])
async def spotify(ctx, url: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
        
        if not await check_perms(ctx, guild_id):
            return
        
        if guild_id not in server_queues:
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}
        
        await handle_voice_connection(ctx)
        
        track_urls = [url]
                

        if "playlist" in url:
            await messagesender(bot, ctx.channel.id, f"Fetching Spotify playlist: <{url}>")
            try:
                track_urls = await get_spotify_tracks_from_playlist(url)
                if not track_urls:
                    await messagesender(bot, ctx.channel.id, "❌ Failed to retrieve tracks from Spotify playlist.")
                    return
            except Exception as e:
                await messagesender(bot, ctx.channel.id, f"⚠️ Error processing Spotify: {e}")
                return

        total_tracks = len(track_urls)
        if total_tracks == 0:
            await messagesender(bot, ctx.channel.id, "❌ No tracks found")
            return

        progress_message = await ctx.send(f"🔄 Processing {total_tracks} track(s) from Spotify")

        async def update_progress(current):
            bar_length = 20
            progress = current / total_tracks
            filled_length = int(bar_length * progress)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            await progress_message.edit(content=f"🔄 Processing Spotify\n[{bar}] {current}/{total_tracks}")

        async def process_track(track_url):
            try:
                print(f"🔍 Converting track: {track_url}")
                youtube_link = await spotify_to_youtube(track_url)
                if not youtube_link:
                    print(f"❌ Failed to convert {track_url}")
                    await progress_message.edit(content=f"🔄 Processing Spotify\n[{bar}] {current}/{total_tracks}")
                    return None

                file_path = await download_audio(youtube_link)
                spotify_title = await get_spotify_title(track_url)
                return youtube_link, spotify_title

            except Exception as e:
                print(f"⚠️ Error processing track {track_url}: {e}")
                return None
        
        async def download_audio(youtube_link):
            output_path = f"music/{youtube_link}.mp3"
            ydl_opts = {
                'format': 'bestaudio[acodec^=opus]/bestaudio',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'outtmpl': f'music/%(id)s',
            }
        
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _download_sync, ydl_opts, youtube_link)
                return output_path
            except Exception as e:
                print(f"Error downloading {codec} format from {youtube_link}: {e}")
                return False
        
        def _download_sync(ydl_opts, url):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info("https://music.youtube.com/watch?v=" + url, download=True)
        
        tasks = [process_track(url) for url in track_urls]
        results = await asyncio.gather(*tasks)
        
        queue_count = 0
        for idx, result in enumerate(results, start=1):
            await update_progress(idx)
            if result:
                file_path, spotify_title = result
                await server_queues[guild_id].put([file_path, spotify_title])
                queue_count += 1

        if queue_count == 0:
            await progress_message.edit(content="❌ No tracks were added to the queue.")
        else:
            await progress_message.edit(content=f"✅ Added {queue_count}/{total_tracks} tracks to the queue.")
        
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await play_next(ctx, ctx.voice_client)

@bot.command(name="applemusic", aliases=["ap"])
async def applemusic(ctx, url: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
    
        if not await check_perms(ctx, guild_id):
            return

        if not server_queues.get(guild_id):
            server_queues[guild_id] = asyncio.Queue()
            current_tracks[guild_id] = {"current_track": None, "is_looping": False}

        await handle_voice_connection(ctx)
    
        await messagesender(bot, ctx.channel.id, f"Processing Apple Music link: <{url}>")
        youtube_link = await get_apple_music_audio(ctx, url)
        if youtube_link:
            file_path = await get_audio_filename(youtube_link)
            if file_path:
                await queue_and_play_next(ctx, ctx.guild.id, file_path, "-{AppleMusic Link}-")
            else:
                await messagesender(bot, ctx.channel.id, "Failed to download Apple Music track.")
        else:
            await messagesender(bot, ctx.channel.id, "Failed to process Apple Music track.")

@bot.command(name="history", aliases=["played"])
async def history(ctx):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return

        history_list = track_history.get(guild_id, [])

        if not history_list:
            await messagesender(bot, ctx.channel.id, "No recent tracks available.")
            return
    
        embed = discord.Embed(title="\U0001F3B5 Recently Played Songs", color=discord.Color.blue())
        for index, track in enumerate(history_list[-HISTORY_PAGE_SIZE:], start=1):
            embed.add_field(name=f"{index}. {track[1]}", value=f"ID: {track[0]}", inline=False)
        await messagesender(bot, ctx.channel.id, embed=embed)

@bot.command(name="autoplay", aliases=["autodj"])
async def autoplay(ctx, mode: str):
    async with ctx.typing():
        guild_id = ctx.guild.id
        if not await check_perms(ctx, guild_id):
            return

        if mode.lower() not in ["on", "off"]:
            await messagesender(bot, ctx.channel.id, "Use `!autoplay on` or `!autoplay off`.")
            return

        autoplay_enabled[guild_id] = mode.lower() == "on"
        bot.intentional_disconnections[guild_id] = False 

        status = "enabled" if autoplay_enabled[guild_id] else "disabled"
        await messagesender(bot, ctx.channel.id, f"Autoplay is now {status} for this server.")

@bot.command(name="stats")
async def stats(ctx):
    uptime = time.time() - start_time
    server_count = len(bot.guilds)

    if platform.system() == "Windows":
        process = os.popen('wmic process where "ProcessId=%d" get WorkingSetSize' % os.getpid())
        memory_usage = int(process.read().strip().split("\n")[-1]) / (1024 * 1024)
        process.close()
    else:
        memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    embed = discord.Embed(title="📊 Bot Stats", color=discord.Color.green())
    embed.add_field(name="⏳ Uptime", value=f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s", inline=False)
    embed.add_field(name="💾 Memory Usage", value=f"{memory_usage:.2f} MB", inline=False)
    embed.add_field(name="🏠 Servers", value=f"{server_count} servers", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="showstats")
async def toggle_stats(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    stats_config["show_stats"] = not stats_config["show_stats"]
    save_stats_config(stats_config)
    
    await update_bot_presence()
    
    state = "enabled" if stats_config["show_stats"] else "disabled"
    await messagesender(bot, ctx.channel.id, content=f"Bot stats display has been {state}.")

@bot.command(name="purgequeues")
async def purge_queues(ctx):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    global server_queues
    cleared_count = 0
    
    for guild_id in list(server_queues.keys()):
        if isinstance(server_queues[guild_id], asyncio.Queue):
            server_queues[guild_id] = asyncio.Queue()
            cleared_count += 1
    
    await messagesender(bot, ctx.channel.id, content=f"Cleared queues for {cleared_count} servers.")

@bot.command(name="sendglobalmsg")
async def send_global_message(ctx, *, message: str):
    if ctx.author.id != BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="You don't have permission to use this command.")
        return
    
    success_count = 0
    failure_count = 0
    
    for guild in bot.guilds:
        target_channel = None
        
        # Check last active channel first
        if guild.id in last_active_channels:
            target_channel = bot.get_channel(last_active_channels[guild.id])
        
        # If no active channel, try #general or #voice
        if not target_channel:
            for channel in guild.text_channels:
                if channel.name in ["general", "voice"] and channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break
        
        # If still no target, find the first text channel the bot can send messages in
        if not target_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break
        
        if target_channel:
            try:
                await target_channel.send(message)
                success_count += 1
            except Exception:
                failure_count += 1
        else:
            failure_count += 1
    
    await messagesender(bot, ctx.channel.id, content=f"Message sent to {success_count} servers. Failed in {failure_count}.")

async def get_youtube_video_title(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                html_content = await response.text()
                
                soup = BeautifulSoup(html_content, "html.parser")
                title_element = soup.find_all(name="title")[0]
                title = str(title_element)
                title = title.replace("<title>", "").replace("</title>", "").removesuffix(" - YouTube").replace("&amp;","&")
                
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                    
                return title
        except (aiohttp.ClientError, IndexError) as e:
            print(f"Error fetching video title: {e}")
            return None

@bot.event
async def on_message_delete(message):
    if message.id in message_map:
        try:
            await message_map[message.id].delete()
        except discord.NotFound:
            pass
        del message_map[message.id]

async def get_youtube_playlist_title(playlist_id):
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                response.raise_for_status()
                html_content = await response.text()
                
                match = re.search(r'var ytInitialData = ({.*?});</script>', html_content, re.DOTALL)
                if not match:
                    print(f"Error: Could not find JSON metadata for {playlist_id}")
                    return "Unknown Playlist"
                
                json_data = json.loads(match.group(1))
                
                title = json_data.get("header", {}).get("playlistHeaderRenderer", {}).get("title")
                
                if not title:
                    print(f"Error: Playlist title not found in metadata for {playlist_id}")
                    return "Unknown Playlist"
                
                if is_banned_title(title):
                    raise ValueError("Out of bounds error: This content is not allowed.")
                    
                return title
        except (aiohttp.ClientError, json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"Error fetching playlist title: {e}")
            return "Unknown Playlist"


async def timeout_handler(ctx):
    await asyncio.sleep(TIMEOUT_TIME) 

    if ctx.guild.id in bot.voice_clients and ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        print(f"Disconnected from voice channel due to inactivity in guild: {ctx.guild.name}")

async def update_bot_presence():
    """ Updates the bot's presence based on the stats setting. """
    if stats_config["show_stats"]:
        guild_count = len(bot.guilds)
        await bot.change_presence(activity=discord.Game(name=f"Serving {guild_count} servers"))
    else:
        await bot.change_presence(activity=None)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to do that.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: {error.param.name}")
    else:
        await ctx.send(f"An error occurred: {error}")
        raise error

@bot.command(name="listen")
async def listen_command(ctx):
    await start_listening(ctx)

@bot.command(name="unlisten")
async def unlisten_command(ctx):
    await stop_listening(ctx)

@bot.command(name="getmetadata")
async def get_metadata(ctx, filename: str):
    metadata = metadata_manager.load_metadata(filename)
    if metadata:
        await ctx.send(f"Metadata for {filename}:\n```json\n{json.dumps(metadata, indent=4)}```")
    else:
        await ctx.send("No metadata found.")

@bot.command(name="fetchmetadata")
async def fetch_metadata(ctx, filename: str, title: str, artist: str = None):
    metadata = metadata_manager.get_or_fetch_metadata(filename, title, artist)
    await ctx.send(f"Fetched metadata:\n```json\n{json.dumps(metadata, indent=4)}```")

@bot.command(name="setmetadata")
async def set_metadata(ctx, filename: str, key: str, value: str):
    if ctx.author.id not in metadata_manager.editor_ids:
        await ctx.send("You do not have permission to edit metadata.")
        return
    metadata_manager.update_metadata(filename, key, value)
    await ctx.send(f"Updated {key} in {filename}.")

@bot.command(name="addeditor")
async def add_editor(ctx, user: discord.User):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("You do not have permission to modify editors.")
        return
    metadata_manager.add_editor(user.id)
    await ctx.send(f"Added {user.mention} as a metadata editor.")

@bot.command(name="removeeditor")
async def remove_editor(ctx, user: discord.User):
    if ctx.author.id != BOT_OWNER_ID:
        await ctx.send("You do not have permission to modify editors.")
        return
    metadata_manager.remove_editor(user.id)
    await ctx.send(f"Removed {user.mention} from metadata editors.")


bot.run(BOT_TOKEN)

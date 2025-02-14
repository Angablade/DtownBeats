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

from voice_utils import start_listening, stop_listening
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from io import BytesIO
from aiofiles import open as aopen
from youtube_mp3 import get_mp3_filename
from youtube_pl import grab_youtube_pl
from lyrics import Lyrics
from discord.ext import commands
from discord.ui import View, Button
from discord import FFmpegPCMAudio, Embed
from fuzzywuzzy import fuzz

MUSICBRAINZ_USERAGENT = os.getenv("MUSICBRAINZ_USERAGENT", "default_user")
MUSICBRAINZ_VERSION = os.getenv("MUSICBRAINZ_VERSION", "1.0")
MUSICBRAINZ_CONTACT = os.getenv("MUSICBRAINZ_CONTACT", "default@example.com")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
EXECUTOR_MAX_WORKERS = int(os.getenv("EXECUTOR_MAX_WORKERS", "10"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_default_token")
QUEUE_PAGE_SIZE = int(os.getenv("QUEUE_PAGE_SIZE","10"))
HISTORY_PAGE_SIZE = int(os.getenv("HISTORY_PAGE_SIZE","10"))
TIMEOUT_TIME = int(os.getenv("TIMEOUT_TIME", "60"))

musicbrainzngs.set_useragent(MUSICBRAINZ_USERAGENT, MUSICBRAINZ_VERSION, MUSICBRAINZ_CONTACT)
executor = ThreadPoolExecutor(max_workers=EXECUTOR_MAX_WORKERS)

CONFIG_FILE = "config/server_config.json"
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

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
intents.guild_messages = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents)

bot.intentional_disconnections = {}
bot.timeout_tasks = {}
server_queues = {}
current_tracks = {}
queue_paused = {}
track_history = {}
autoplay_enabled = {}
message_map = {}

async def download_audio(video_id):
    try: 
         filenam = await get_mp3_filename(video_id)
         print(f"{filenam} is playing...")
         return filenam
    except Exception as e:
        print(f"Failed to download audio: {e}")
        return None

async def check_perms(ctx, guild_id):
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
    return any(keyword in title for keyword in banned_keywords)

async def messagesender(bot, channel_id, content=None, embed=None, command_message=None):
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    
    messages = []
    async with channel.typing():
        if embed and content:
            messages.append(await channel.send(content=content, embed=embed))
        elif embed:
            messages.append(await channel.send(embed=embed))
        elif content:
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
        else:
            raise ValueError("Either 'content' or 'embed' must be provided")
    
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if autoplay_enabled.get(guild_id, False) and bot.intentional_disconnections.get(guild_id, False):
        return

    while not queue_paused.get(guild_id, False):
        if server_queues[guild_id].empty():
            if autoplay_enabled.get(guild_id, False):
                last_track = track_history.get(guild_id, [])[-1][0] if track_history.get(guild_id) else None
                if last_track:
                    next_video = await get_related_video(last_track, guild_id)
                    if next_video:
                        await queue_and_play_next(ctx, guild_id, next_video)
                    else:
                        await messagesender(bot, ctx.channel.id, "Autoplay stopped: No new related videos found.")
            await messagesender(bot, ctx.channel.id, "The queue is empty.")
            await check_empty_channel(ctx)
            break

        videoinfo = await server_queues[guild_id].get()
        video_id, video_title = videoinfo[0], videoinfo[1]

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
        return

    await messagesender(bot, ctx.channel.id, f"Now playing: `{video_title}`")

    current_tracks[guild_id]["current_track"] = [video_id, video_title]

    def playback():
        source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options="-bufsize 10m -ss 00:00:00")
        voice_client.play(source, after=lambda e: print(f"Playback finished: {e}") if e else None)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, playback)

    if guild_id in bot.timeout_tasks:
        bot.timeout_tasks[guild_id].cancel()

    bot.timeout_tasks[guild_id] = asyncio.create_task(timeout_handler(ctx))

    if not server_queues[guild_id].empty():
        temp_queue = list(server_queues[guild_id]._queue)

        if temp_queue:
            next_videoinfo = temp_queue[0] 
            next_video_id, next_video_title = next_videoinfo 

            print(f"Pre-downloading next track: {next_video_title}")
            asyncio.create_task(download_audio(next_video_id))

    while voice_client.is_playing():
        await asyncio.sleep(1)

@bot.event
async def on_ready():
    try:
        print(f"Bot is ready! Logged in as {bot.user}")
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
    await ctx.typing()
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
async def play(ctx, *, search: str = None):
    await ctx.typing()
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
    ydl_opts = {
        "default_search": "ytsearch1",
        "quiet": True,
        "no_warnings": True 
    }

    def run_yt_dlp():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                if "entries" not in info or not info["entries"]: 
                    return None
                return info["entries"][0]["id"]
            except Exception as e:
                return None 

    result = await loop.run_in_executor(executor, run_yt_dlp)

    if not result:
        await messagesender(bot, ctx.channel.id, f"Failed to find a song for: `{search}`")
        return None

    return result


async def queue_and_play_next(ctx, guild_id: int, video_id: str):
    try:
        video_title = await get_youtube_video_title(video_id)
        if not video_title:
            await messagesender(bot, ctx.channel.id, content="Failed to retrieve video title.")
            return
        
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await messagesender(bot, ctx.channel.id, content="Skipped the current track.")

@bot.command(name="stop")
async def stop(ctx):
    await ctx.typing()
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        queue_paused[guild_id] = True
        await messagesender(bot, ctx.channel.id, content="Paused the music")

@bot.command(name="resume", aliases=["continue"])
async def resume(ctx):
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        queue_paused[guild_id] = False
        await messagesender(bot, ctx.channel.id, content="Resumed the music")

@bot.command(name="queue", aliases=["list"])
async def show_queue(ctx, page: int = 1):
    await ctx.typing()
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
    
    ydl_opts = {"default_search": "ytsearch5", "quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            results = info['entries']
            
            if not results:
                await messagesender(bot, ctx.channel.id, content="No search results found.")
                return
            
            embed = discord.Embed(title=f"Search Results: {query}", color=discord.Color.green())
            for entry in results[:5]:
                video_id = entry['id']
                video_title = entry['title']
                
                embed.add_field(name=video_title, value=f"```{ctx.prefix}play {video_id}```", inline=False)
            await messagesender(bot, ctx.channel.id, embed=embed)
        
        except Exception as e:
            await messagesender(bot, ctx.channel.id, f"Failed to search: {e}")

@bot.command(name="clear")
async def clear(ctx):
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if server_queues.get(guild_id):
        server_queues[guild_id]._queue.clear()
    await messagesender(bot, ctx.channel.id, content="Cleared the queue.")

@bot.command(name="remove")
async def remove(ctx, index: int):
    await ctx.typing()
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    current_tracks[guild_id]["is_looping"] = not current_tracks[guild_id].get("is_looping", False)
    await messagesender(bot, ctx.channel.id, content="Looping " + ("enabled." if current_tracks[guild_id]["is_looping"] else "disabled."))

@bot.command(name="nowplaying", aliases=["current","currentsong","playing"])
async def nowplaying(ctx):
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    current_track = current_tracks.get(guild_id, {}).get("current_track")
    if current_track:
        await messagesender(bot, ctx.channel.id, f"Currently playing: {''.join(current_track[1:])}")
    else:
        await messagesender(bot, ctx.channel.id, content="No track is currently playing.")

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


@bot.command(name="version", aliases=["ver"])
async def version(ctx):
                                        #[HHMMSS-MMDDYYYY]
    embed = discord.Embed(
        title=f"DtownBeats - Version 0.3 [044945-14022025]",
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

@bot.command(name="cmds", aliases=["commands"])
async def help_command(ctx):
    """Sends a list of commands in a direct message with a table layout."""
    embed = Embed(title="📜 Bot Commands", description="Here is a list of all available commands:", color=discord.Color.blue())

    # 🎵 Music Commands
    embed.add_field(name="🎵 **Music Commands**", value="""
    **Command**       | **Aliases**       | **Description**
    ------------------|-------------------|------------------------------------------------
    play <query>      | None              | Play a song or add it to the queue.
    stop              | None              | Stop the bot and leave the voice channel.
    pause             | hold              | Pause the currently playing track.
    resume            | continue          | Resume the paused track.
    search <query>    | find              | Show up to 5 YouTube search results.
    nowplaying        | np, current       | Show details of the current song.
    seek <time/%>     | None              | Seek to a timestamp or percentage.
    volume <0-200>    | vol               | Adjust playback volume (0-200%).
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # ⌚ Queue Commands
    embed.add_field(name="⌚ **Queue Commands**", value="""
    **Command**   | **Aliases**  | **Description**
    --------------|--------------|----------------------------------------
    queue         | list         | Display the current queue.
    skip          | next         | Skip the currently playing song.
    clear         | None         | Clear the queue.
    remove <#>    | None         | Remove a song from the queue.
    loop          | repeat       | Toggle looping.
    shuffle       | None         | Shuffle the queue.
    move <#> <#>  | None         | Move a song in the queue.
    grablist <q>  | grabplaylist | Grab a user-generated playlist.
    history       | played       | Show recently played tracks.
    autoplay      | autodj       | Toggle autoplay mode.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # 🔇 Control Commands
    embed.add_field(name="🔇 **Control Commands**", value="""
    **Command**  | **Aliases** | **Description**
    ----------|-----------|--------------------------------
    mute      | quiet     | Toggle mute/unmute.
    join      | come      | Make the bot join your voice channel.
    leave     | go        | Disconnect the bot from voice.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # 🎤 Voice Commands
    embed.add_field(name="🎤 **Voice Control Commands**", value="""
    **Command**       | **Voice Trigger**      | **Description**
    ------------------|------------------------|----------------------------
    listen            | Music bot listen       | Enable voice command mode.
    unlisten          | Music bot unlisten     | Disable voice command mode.
    play <query>      | Music bot play <q>     | Play a song via voice command.
    pause             | Music bot pause        | Pause playback.
    resume            | Music bot resume       | Resume playback.
    stop              | Music bot stop         | Stop and leave voice.
    skip              | Music bot skip         | Skip the current song.
    volume up         | Music bot volume up    | Increase volume.
    volume down       | Music bot volume down  | Decrease volume.
    shuffle           | Music bot shuffle      | Shuffle the queue.
    clear queue       | Music bot clear queue  | Clear the queue.
    loop              | Music bot loop         | Toggle looping.
    autoplay on       | Music bot autoplay on  | Enable autoplay mode.
    autoplay off      | Music bot autoplay off | Disable autoplay mode.
    leave             | Music bot leave        | Disconnect from voice.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # 📜 Lyrics Commands
    embed.add_field(name="📜 **Lyrics Commands**", value="""
    **Command** | **Aliases** | **Description**
    ------------|-------------|-------------------------------------------
    lyrics <song> | None    | Fetch lyrics for the specified/current song.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # ⚙️ Configuration Commands
    embed.add_field(name="⚙️ **Configuration Commands**", value="""
    **Command**       | **Aliases**  | **Description**
    ------------------|--------------|------------------------------------
    setprefix <p>     | prefix       | Change the bot's prefix.
    setdjrole <r>     | setrole      | Assign a DJ role.
    setchannel <c>    | None         | Restrict commands to a channel.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # 📇 Other Commands
    embed.add_field(name="📇 **Other Commands**", value="""
    **Command** | **Aliases** | **Description**
    ------------|-------------|-------------------------------------------
    version     | ver         | DM the bot version info.
    sendplox    | None        | DM the current track as a file.
    commands    | cmds        | DM this command list.
    """, inline=False)

    embed.add_field(name="", value="", inline=False)  # Empty space

    # 🛠️ Admin Commands
    embed.add_field(name="🛠️ **Admin Commands**", value="""
    **Command**  | **Aliases**        | **Description**
    ----------|--------------|--------------------------------------
    shutdown  | die          | Shut down the bot (owner only).
    reboot    | restart      | Restart the bot (owner only).
    dockboot  | dockerrestart| Restart Docker container (owner only).
    """, inline=False)

    try:
        await ctx.author.send(embed=embed)
        await messagesender(bot, ctx.channel.id, content="I've sent you a DM with the list of commands. 📬")
    except discord.Forbidden:
        await messagesender(bot, ctx.channel.id, content="I couldn't send you a DM. Please check your privacy settings.")



@bot.command(name="seek")
async def seek(ctx, position: str):
    await ctx.typing()
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


@bot.command(name="mute", aliases=["quiet"])
async def toggle_mute(ctx):
    await ctx.typing()
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

@bot.command(name="lyrics")
async def lyrics(ctx, *, song: str = None):
    await ctx.typing()
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await messagesender(bot, ctx.channel.id, content="There's no audio currently playing.")
        return

    if 0 <= volume <= 200:
        ctx.voice_client.source = discord.PCMVolumeTransformer(ctx.voice_client.source)
        ctx.voice_client.source.volume = volume / 100
        await messagesender(bot, ctx.channel.id, f"Volume set to {volume}%.")
    else:
        await messagesender(bot, ctx.channel.id, content="Volume must be between 0 and 200.")

@bot.command(name="shuffle")
async def shuffle_queue(ctx):
    await ctx.typing()
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
    await ctx.typing()
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
    await ctx.typing()
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
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if ctx.voice_client:
        bot.intentional_disconnections[guild_id] = True
        await ctx.voice_client.disconnect()
        await messagesender(bot, ctx.channel.id, content="Disconnected from the voice channel. 👋")
    else:
        await messagesender(bot, ctx.channel.id, content="I'm not in a voice channel to leave.")

@bot.command(name="sendplox")
async def sendmp3(ctx):
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return

    dir_path = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/")
    current_track = current_tracks.get(guild_id, {}).get("current_track")
    file_path = f"music/{''.join(current_track[:1])}.mp3"
    if not os.path.exists(file_path):
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

@bot.command(name="history", aliases=["played"])
async def history(ctx):
    await ctx.typing()
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
    await ctx.typing()
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

def search_musicbrainz(query):
    """Search MusicBrainz for refined track info."""
    try:
        result = musicbrainzngs.search_recordings(query, limit=5)
        if "recording-list" in result:
            recordings = result["recording-list"]
            refined_results = []
            for recording in recordings:
                artist = recording["artist-credit"][0]["artist"]["name"]
                title = recording["title"]
                duration = recording.get("length")
                refined_results.append({
                    "artist": artist,
                    "title": title,
                    "duration": duration
                })
            return refined_results
        return None
    except musicbrainzngs.ResponseError as e:
        print(f"MusicBrainz API error: {e}")
        return None

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


bot.run(BOT_TOKEN)

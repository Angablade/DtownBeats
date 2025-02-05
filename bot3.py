import discord
import os
import re
import json
import random
import tempfile
import requests
import yt_dlp
import asyncio
import aiohttp
import musicbrainzngs

from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from io import BytesIO
from aiofiles import open as aopen
from youtube_mp3 import get_mp3_filename
from lyrics import Lyrics
from discord.ext import commands
from discord.ui import View, Button
from discord import FFmpegPCMAudio, Embed

MUSICBRAINZ_USERAGENT = os.getenv("MUSICBRAINZ_USERAGENT", "default_user")
MUSICBRAINZ_VERSION = os.getenv("MUSICBRAINZ_VERSION", "1.0")
MUSICBRAINZ_CONTACT = os.getenv("MUSICBRAINZ_CONTACT", "default@example.com")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "123456789"))
EXECUTOR_MAX_WORKERS = int(os.getenv("EXECUTOR_MAX_WORKERS", "10"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_default_token")
QUEUE_PAGE_SIZE = os.getenv("QUEUE_PAGE_SIZE","10")
TIMEOUT_TIME = os.getenv("TIMEOUT_TIME", "60")

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

import discord

async def messagesender(bot, channel_id, content=None, embed=None):
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    
    async with channel.typing():
        if embed and content:
            await channel.send(content=content, embed=embed)
        elif embed:
            await channel.send(embed=embed)
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
                await channel.send(chunk)
        else:
            raise ValueError("Either 'content' or 'embed' must be provided")


async def fetch_playlist_videos(playlist_url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(playlist_url) as response:
            html_content = await response.text()
            video_ids = re.findall(r'"videoId":"([\w-]{11})"', html_content)
            return video_ids
        
async def play_next(ctx, voice_client):
    await ctx.typing() 
    guild_id = ctx.guild.id
    
    if queue_paused.get(guild_id, False):
        return
        
    if server_queues[guild_id].empty():
        await messagesender(bot, ctx.channel.id, content="The queue is empty.")
        return
    
    videoinfo = await server_queues[guild_id].get()
    video_id = ''.join(videoinfo[:1])
    video_title = ''.join(videoinfo[1:])
    
    audio_file_task = asyncio.create_task(download_audio(video_id))
    audio_file = await audio_file_task
    
    if not audio_file:
        await messagesender(bot, ctx.channel.id, content="Failed to download the track. Please try again.")
        return
    
    await play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id)

    await play_next(ctx, voice_client)

async def play_audio_in_thread(voice_client, audio_file, ctx, video_title, video_id):
    guild_id = ctx.guild.id
    if "drake" in video_title.lower():
        raise IndexError("Out of bounds error: 'drake' is not allowed.")
        return "Out of bounds error: 'drake' is not allowed."
        
    await messagesender(bot, ctx.channel.id, f"Now playing: `{video_title}`")

    current_tracks[guild_id]["current_track"] = [video_id, video_title]

    def playback():
        source = FFmpegPCMAudio(audio_file, executable="ffmpeg", options="-bufsize 10m")
        voice_client.play(source, after=lambda e: print(f"Playback finished: {e}") if e else None)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, playback)

    if guild_id in bot.timeout_tasks:
        bot.timeout_tasks[guild_id].cancel()

    bot.timeout_tasks[guild_id] = asyncio.create_task(timeout_handler(ctx))

    while voice_client.is_playing():
        await asyncio.sleep(1)

async def messagesender(bot, channel_id, message):
    channel = bot.get_channel(channel_id)
    if channel:
        async with channel.typing():
            if isinstance(message, discord.Embed):
                await channel.send(embed=message)
            else:
                while message:
                    if len(message) <= 2000:
                        chunk = message
                        message = ""
                    else:
                        split_index = message.rfind(" ", 0, 2000)
                        if split_index == -1:
                            chunk = message[:2000]
                            message = message[2000:]
                        else:
                            chunk = message[:split_index]
                            message = message[split_index + 1:]
                    await channel.send(chunk)

@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")

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
            await messagesender(bot, ctx.channel.id, f"Processing:  {playlist_id}")
            video_ids = await fetch_playlist_videos(playlist_url)
            current_ids = []
            for video_id in video_ids:
                if video_id not in current_ids:
                    current_ids.append(video_id)
                    await server_queues[guild_id].put([video_id, await get_youtube_video_title(video_id)])
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
    voice_channel = ctx.author.voice.channel
    if not ctx.voice_client:
        bot.intentional_disconnections[guild_id] = False
        await voice_channel.connect()

async def fetch_video_id(ctx, search: str) -> str:
    if "drake" in search.lower():
        raise IndexError("Out of bounds error: 'drake' is not allowed.")
        return "Out of bounds error: 'drake' is not allowed."
        
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
    ydl_opts = {"default_search": "ytsearch1", "quiet": True}

    def run_yt_dlp():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                return info['entries'][0]['id']
            except Exception as e:
                return e

    result = await loop.run_in_executor(executor, run_yt_dlp)
    if isinstance(result, Exception):
        await messagesender(bot, ctx.channel.id, f"Failed to find the song: {result}")
        return None
    return result

async def queue_and_play_next(ctx, guild_id: int, video_id: str):
    video_title = await get_youtube_video_title(video_id)
    
    if not server_queues[guild_id].empty():
        await messagesender(bot, ctx.channel.id, f"Queued: {video_title}")
    else:
        if ctx.voice_client.is_playing():
            await messagesender(bot, ctx.channel.id, f"Queued: {video_title}")
            
    await server_queues[guild_id].put([video_id, video_title])
    
    if not ctx.voice_client.is_playing():
        play_next_task = asyncio.create_task(play_next(ctx, ctx.voice_client))
        await play_next_task

@bot.command(name="skip")
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

@bot.command(name="pause")
async def pause(ctx):
    await ctx.typing()
    guild_id = ctx.guild.id
    if not await check_perms(ctx, guild_id):
        return
        
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        queue_paused[guild_id] = True
        await messagesender(bot, ctx.channel.id, content="Paused the music")

@bot.command(name="resume")
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

@bot.command(name="loop")
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
    if str(ctx.author.id) == BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="Shutting down.")
        await bot.close()
    else:
        await messagesender(bot, ctx.channel.id, content="You do not have permission to shut down the bot.")

@bot.command(name="reboot", aliases=["restart"])
async def reboot(ctx):
    if str(ctx.author.id) == BOT_OWNER_ID:
        await messagesender(bot, ctx.channel.id, content="Restarting the bot...")
        os.execv(sys.executable, ['python'] + sys.argv)
    else:
        await messagesender(bot, ctx.channel.id, content="You do not have permission to restart the bot.")

@bot.command(name="cmds", aliases=["commands"])
async def help_command(ctx):
    """Sends a list of commands in a direct message."""
    embed = Embed(title="Bot Commands", description="Here is a list of all available commands:", color=discord.Color.blue())

    embed.add_field(name="🎵 Music Commands", value=(
        f"`{ctx.prefix}play <query>` - Play a song or add it to the queue. Supports search, playlists, embeds, shorts, youtube music, and direct url.\n"
        f"`{ctx.prefix}stop` - Stop the bot and leave the voice channel.\n"
        f"`{ctx.prefix}pause` - Pause the music.\n"
        f"`{ctx.prefix}resume` - Resume the paused music.\n"
        f"`{ctx.prefix}search <query>` - Displays up to a list of 5 playable audio options from youtube.\n"
        f"`{ctx.prefix}nowplaying` - Show the currently playing song.\n"
        f"`{ctx.prefix}seek <time>/<percent>` - Seek to a specific time in the currently playing track.\n"
        f"`{ctx.prefix}volume <0-200>` - Adjust the playback volume (0-200%)."
    ), inline=False)
    
    embed.add_field(name="", value=(""), inline=False)
    
    embed.add_field(name="⌚ Queue Commands", value=(
        f"`{ctx.prefix}queue` - Show the current music queue.\n"
        f"`{ctx.prefix}skip` - Skip the currently playing song.\n"
        f"`{ctx.prefix}clear` - Clear the music queue.\n"
        f"`{ctx.prefix}remove <index>` - Remove a song from the queue by its position.\n"
        f"`{ctx.prefix}loop` - Toggle looping for the current song.\n"
        f"`{ctx.prefix}shuffle` - Shuffle the current music queue.\n"
        f"`{ctx.prefix}move <from> <to>` - Move a song in the queue from one position to another."
    ), inline=False)
    
    embed.add_field(name="", value=(""), inline=False)
    
    embed.add_field(name="🔇 Control Commands", value=(
        f"`{ctx.prefix}mute` - Toggle mute/unmute for the bot.\n"
        f"`{ctx.prefix}join` - Make the bot join your current voice channel.\n"
        f"`{ctx.prefix}leave` - Disconnect the bot from the voice channel."
    ), inline=False)

    embed.add_field(name="📜 Lyrics Commands", value=(
        f"`{ctx.prefix}lyrics <song>` - Get the lyrics for the specified song. If no song is provided, tries to get the lyrics for the currently playing track."
    ), inline=False)

    embed.add_field(name="", value=(""), inline=False)

    embed.add_field(name="⚙️ Configuration Commands", value=(
        f"`{ctx.prefix}setprefix <prefix>` - Set the bot's prefix.\n"
        f"`{ctx.prefix}setdjrole <role>` - Set the DJ role.\n"
        f"`{ctx.prefix}setchannel <channel>` - Set the designated command channel."
    ), inline=False)

    embed.add_field(name="", value=(""), inline=False)

    embed.add_field(name="🛠️ Admin Commands", value=(
        f"`{ctx.prefix}shutdown` - Shut down the bot (owner only).\n"
        f"`{ctx.prefix}reboot` - Restart the bot (owner only)."
    ), inline=False)

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

    await ctx.typing()
    guild_id = ctx.guild.id
    current_track = current_tracks.get(guild_id, {}).get("current_track")
    if current_track is None:
        await messagesender(bot, ctx.channel.id, content="There's no track information available to seek.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={current_track}", download=False)
                duration = info.get("duration", 0)

        if position.endswith("%"):
            percent = int(position.strip("%"))
            if not (0 <= percent <= 100):
                raise ValueError("Percentage must be between 0 and 100.")
            seconds = int(duration * (percent / 100))
        else:
            seconds = int(position)
            if seconds < 0 or seconds > duration:
                raise ValueError(f"Position must be between 0 and {duration} seconds.")

        ctx.voice_client.stop()
        audio_file = await download_audio(current_track)
        ffmpeg_options = f"-ss {seconds}"
        source = FFmpegPCMAudio(audio_file, options=ffmpeg_options)
        ctx.voice_client.play(source, after=lambda _: asyncio.run_coroutine_threadsafe(play_next(ctx, ctx.voice_client), bot.loop))

        await messagesender(bot, ctx.channel.id, f"Seeking to {seconds} seconds.")
    except Exception as e:
        await messagesender(bot, ctx.channel.id, f"An error occurred while seeking: {e}")

@bot.command(name="mute")
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


@bot.command(name="join")
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

@bot.command(name="leave")
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
    guild_id = ctx.guild.id
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
                title = title.replace("<title>", "").replace("</title>", "").removesuffix(" - YouTube")
                
                if "drake" in title.lower():
                    raise IndexError("Out of bounds error: 'drake' is not allowed.")
                    
                return title
        except (aiohttp.ClientError, IndexError) as e:
            print(f"Error fetching video title: {e}")
            return None

async def timeout_handler(ctx):
    await asyncio.sleep(TIMEOUT_TIME) 
    
    if ctx.guild.id in bot.voice_clients and not ctx.voice_client.is_playing():
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



bot.run(BOT_TOKEN)

# Common utility functions used across cogs
import discord
import asyncio
import aiohttp
import yt_dlp
import json
import os
import logging
from bs4 import BeautifulSoup

def get_server_config(guild_id):
    """Get server configuration"""
    try:
        config_file = "config/server_config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config.get(str(guild_id), {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False})
    except:
        return {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}

async def check_perms(ctx, guild_id, bot):
    """Check if user has permissions to use commands"""
    banned_users = getattr(bot, 'banned_users', {})
    
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
        return False

    return True

async def messagesender(bot, channel_id, content=None, embed=None, command_message=None, file=None):
    """Send messages to Discord channels"""
    channel = bot.get_channel(channel_id)
    if not channel:
        logging.error(f"[Error] Channel with ID {channel_id} not found.")
        return
    
    messages = []
    
    # Ensure file is a discord.File instance if provided
    if file and isinstance(file, str):
        try:
            file = discord.File(file)
        except Exception as e:
            logging.error(f"[Error] Failed to create discord.File: {e}")
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
                    logging.error("[Error] Content must be a string.")
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
                logging.error("[Error] Either 'content', 'embed', or 'file' must be provided.")
                return
        except discord.HTTPException as e:
            logging.error(f"[Error] Failed to send message: {e}")
            return

    message_map = getattr(bot, 'message_map', {})
    if command_message:
        message_map[command_message.guild.id] = messages
    elif messages:
        message_map[messages[0].guild.id] = messages

async def fetch_video_id_from_ytsearch(search: str, ctx, bot):
    """Fetch video ID from YouTube search"""
    executor = getattr(bot, 'executor', None)
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
    
    result = await loop.run_in_executor(executor, lambda: run_yt_dlp(ydl_opts_music))
    
    if not result:
        ydl_opts_regular = {
            "default_search": "ytsearch1",
            "quiet": True,
            "no_warnings": True,
        }
        result = await loop.run_in_executor(executor, lambda: run_yt_dlp(ydl_opts_regular))
    
    if not result:
        await messagesender(bot, ctx.channel.id, f"Failed to find a song for: `{search}`")
        return None
    
    return result

async def get_youtube_video_title(video_id):
    """Get YouTube video title"""
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

                return title

    except (aiohttp.ClientError, AttributeError) as e:
        logging.error(f"Error fetching video title from YouTube page: {e}")
        return None

async def safe_voice_connect(bot, guild, channel, max_retries=3):
    """Safe voice connection with retry logic and cooldown"""
    guild_id = guild.id
    
    # Check cooldown
    now = asyncio.get_event_loop().time()
    reconnect_cooldowns = getattr(bot, 'reconnect_cooldowns', {})
    cooldown = reconnect_cooldowns.get(guild_id, 0)
    if now < cooldown:
        remaining = int(cooldown - now)
        logging.info(f"Voice connect on cooldown for {guild.name}, {remaining}s remaining")
        return None

    for attempt in range(max_retries):
        try:
            # Disconnect existing connection if any
            if guild.voice_client:
                await guild.voice_client.disconnect(force=True)
                await asyncio.sleep(1)

            # Attempt connection
            voice_client = await channel.connect(timeout=10.0, reconnect=True)
            
            if voice_client and voice_client.is_connected():
                logging.info(f"Successfully connected to {channel.name} in {guild.name}")
                
                # Apply volume if set
                guild_volumes = getattr(bot, 'guild_volumes', {})
                if guild_id in guild_volumes and voice_client.source:
                    try:
                        voice_client.source = discord.PCMVolumeTransformer(voice_client.source)
                        voice_client.source.volume = guild_volumes[guild_id] / 100
                    except Exception as e:
                        logging.warning(f"Failed to apply volume: {e}")
                
                return voice_client
            else:
                raise Exception("Voice client not connected after connection attempt")
                
        except Exception as e:
            logging.warning(f"Voice connect attempt {attempt + 1}/{max_retries} failed for {guild.name}: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                # Set cooldown on final failure
                reconnect_cooldowns[guild_id] = now + 60  # 1 minute cooldown
                logging.error(f"All voice connect attempts failed for {guild.name}")

    return None

def is_docker():
    """Check if running in Docker container"""
    return os.path.exists('/.dockerenv') or os.environ.get('container') == 'docker'

def load_config_from_file_or_env():
    """Load configuration from file if not in Docker, otherwise from environment variables"""
    if is_docker():
        # Running in Docker, use environment variables
        return {
            'BOT_TOKEN': os.getenv('BOT_TOKEN'),
            'MUSICBRAINZ_USERAGENT': os.getenv('MUSICBRAINZ_USERAGENT', 'default_user'),
            'MUSICBRAINZ_VERSION': os.getenv('MUSICBRAINZ_VERSION', '1.0'),
            'MUSICBRAINZ_CONTACT': os.getenv('MUSICBRAINZ_CONTACT', 'default@example.com'),
            'BOT_OWNER_ID': int(os.getenv('BOT_OWNER_ID', 123456789)),
            'EXECUTOR_MAX_WORKERS': int(os.getenv('EXECUTOR_MAX_WORKERS', '10')),
            'QUEUE_PAGE_SIZE': int(os.getenv('QUEUE_PAGE_SIZE', '10')),
            'HISTORY_PAGE_SIZE': int(os.getenv('HISTORY_PAGE_SIZE', '10')),
            'TIMEOUT_TIME': int(os.getenv('TIMEOUT_TIME', '60'))
        }
    else:
        # Not in Docker, try to load from configs.json
        try:
            with open('configs.json', 'r') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            # Fallback to environment variables if configs.json doesn't exist
            return {
                'BOT_TOKEN': os.getenv('BOT_TOKEN'),
                'MUSICBRAINZ_USERAGENT': os.getenv('MUSICBRAINZ_USERAGENT', 'default_user'),
                'MUSICBRAINZ_VERSION': os.getenv('MUSICBRAINZ_VERSION', '1.0'),
                'MUSICBRAINZ_CONTACT': os.getenv('MUSICBRAINZ_CONTACT', 'default@example.com'),
                'BOT_OWNER_ID': int(os.getenv('BOT_OWNER_ID', 123456789)),
                'EXECUTOR_MAX_WORKERS': int(os.getenv('EXECUTOR_MAX_WORKERS', '10')),
                'QUEUE_PAGE_SIZE': int(os.getenv('QUEUE_PAGE_SIZE', '10')),
                'HISTORY_PAGE_SIZE': int(os.getenv('HISTORY_PAGE_SIZE', '10')),
                'TIMEOUT_TIME': int(os.getenv('TIMEOUT_TIME', '60'))
            }
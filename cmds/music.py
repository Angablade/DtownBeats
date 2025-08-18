# Cog for music playback commands only
from discord.ext import commands
import discord
import asyncio
import os
import logging
import re
import json
import yt_dlp
from utils.common import check_perms, messagesender, fetch_video_id_from_ytsearch, get_youtube_video_title
from sources.bandcamp_mp3 import get_bandcamp_audio, get_bandcamp_title
from sources.soundcloud_mp3 import get_soundcloud_audio, get_soundcloud_title
from sources.spotify_mp3 import spotify_to_youtube, get_spotify_tracks_from_playlist, get_spotify_title
from sources.apple_music_mp3 import get_apple_music_audio

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Access shared state from bot instance
        self.server_queues = getattr(bot, 'server_queues', {})
        self.current_tracks = getattr(bot, 'current_tracks', {})
        self.queue_paused = getattr(bot, 'queue_paused', {})
        self.autoplay_enabled = getattr(bot, 'autoplay_enabled', {})
        self.guild_volumes = getattr(bot, 'guild_volumes', {})
        self.banned_users = getattr(bot, 'banned_users', {})
        
        # Constants
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.VOLUME_CONFIG_PATH = "config/volume.json"

    def get_server_config(self, guild_id):
        """Get server configuration"""
        try:
            with open("config/server_config.json", 'r') as f:
                config = json.load(f)
            return config.get(str(guild_id), {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False})
        except:
            return {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}

    def update_server_config(self, guild_id, key, value):
        """Update server configuration"""
        try:
            with open("config/server_config.json", 'r') as f:
                config = json.load(f)
        except:
            config = {}
        if str(guild_id) not in config:
            config[str(guild_id)] = {"prefix": "!", "dj_role": None, "channel": None, "autoplay": False}
        config[str(guild_id)][key] = value
        with open("config/server_config.json", 'w') as f:
            json.dump(config, f, indent=4)

    def save_volume_settings(self, volume_data):
        """Save volume settings"""
        with open(self.VOLUME_CONFIG_PATH, "w") as f:
            json.dump(volume_data, f, indent=4)

    async def handle_voice_connection(self, ctx):
        """Handle voice connection"""
        guild_id = ctx.guild.id
        if ctx.author.voice and ctx.author.voice.channel:
            voice_channel = ctx.author.voice.channel
            if not ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = False
                from utils.common import safe_voice_connect
                voice_client = await safe_voice_connect(self.bot, ctx.guild, voice_channel)
                if not voice_client:
                    await messagesender(self.bot, ctx.channel.id, content="Failed to connect to voice channel!")
                    return False
        else:
            await messagesender(self.bot, ctx.channel.id, content="You need to be in a voice channel for me to join!")
            return False
        return True

    async def fetch_video_id(self, ctx, search: str) -> str:
        """Fetch video ID from various sources"""
        if self.bot.is_banned_title(search):
            raise ValueError("Out of bounds error: This content is not allowed.")
            
        youtube_id_match = re.match(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/|music\.youtube\.com/watch\?v=)?([\w-]{11})', 
            search
        )
        direct_file_match = re.match(r'(https?://\S+\.(mp3|wav|aac|flac))', search)

        if youtube_id_match:
            return youtube_id_match.group(1)
        elif direct_file_match:
            await messagesender(self.bot, ctx.channel.id, f"Queued direct file: {search}")
            return search
        else:
            return await fetch_video_id_from_ytsearch(search, ctx, self.bot)

    @commands.command(name="play")
    async def play(self, ctx, *, srch: str):
        """Play music from various sources"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await check_perms(ctx, guild_id, self.bot):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return

            patterns = {
                "bandcamp": r"https?://.*bandcamp\.com/.*",
                "soundcloud": r"https?://.*soundcloud\.com/.*",
                "spotify": r"https?://.*spotify\.com/.*",
                "applemusic": r"https?://.*music\.apple\.com/.*",
                "youtube": r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.*"
            }

            if re.match(patterns["bandcamp"], srch):
                await self.bandcamp(ctx, srch)
            elif re.match(patterns["soundcloud"], srch):
                await self.soundcloud(ctx, srch)
            elif re.match(patterns["spotify"], srch):
                await self.spotify(ctx, srch)
            elif re.match(patterns["applemusic"], srch):
                await self.applemusic(ctx, srch)
            else:
                await self.youtube(ctx, search=srch)

    @commands.command(name="youtube", aliases=["yt"])
    async def youtube(self, ctx, *, search: str = None):
        """Play from YouTube"""
        async with ctx.typing():
            guild_id = ctx.guild.id
        
            if not await check_perms(ctx, guild_id, self.bot):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return
        
            if search:
                if "playlist" in search and "list=" in search:
                    playlist_id = search.split("list=")[-1]
                    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                    video_ids = await self.bot.fetch_playlist_videos(ctx, playlist_id, playlist_url)
                    current_ids = set() 

                    scanning_message = await ctx.send(f"Scanning playlist")
                    for video_id in video_ids:
                        await scanning_message.edit(content=f"Scanned: {video_id}")
                        if video_id not in current_ids:
                            current_ids.add(video_id)
                            video_title = await get_youtube_video_title(video_id)
                            await self.server_queues[guild_id].put([video_id, video_title])
                            await scanning_message.edit(content=f"added: {video_id}!")

                    await messagesender(self.bot, ctx.channel.id, f"Added {self.server_queues[guild_id].qsize()} tracks from the playlist to the queue.")
                    if not ctx.voice_client.is_playing():
                        await self.bot.play_next(ctx, ctx.voice_client)
                else:
                    video_id = await self.fetch_video_id(ctx, search)
                    if video_id:
                        await self.bot.queue_and_play_next(ctx, guild_id, video_id)
                    else:
                        await messagesender(self.bot, ctx.channel.id, content="Failed to find the song.")

    @commands.command(name="bandcamp", aliases=["bc"])
    async def bandcamp(self, ctx, url: str):
        """Play from Bandcamp"""
        async with ctx.typing():
            guild_id = ctx.guild.id
        
            if not await check_perms(ctx, guild_id, self.bot):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return
        
            await messagesender(self.bot, ctx.channel.id, f"Processing Bandcamp link: <{url}>")
            file_path = await get_bandcamp_audio(url)
            if file_path:
                trackdata = await get_bandcamp_title(url)
                await self.bot.queue_and_play_next(ctx, ctx.guild.id, file_path, trackdata)
            else:
                await messagesender(self.bot, ctx.channel.id, "Failed to process Bandcamp track.")

    @commands.command(name="soundcloud", aliases=["sc"])
    async def soundcloud(self, ctx, url: str):
        """Play from SoundCloud"""
        async with ctx.typing():
            guild_id = ctx.guild.id
        
            if not await check_perms(ctx, guild_id, self.bot):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return
        
            await messagesender(self.bot, ctx.channel.id, f"Processing SoundCloud link: <{url}>")
            file_path = await get_soundcloud_audio(url)
            soundcloud_title = await get_soundcloud_title(url)
            if file_path:
                await self.bot.queue_and_play_next(ctx, ctx.guild.id, file_path, soundcloud_title)
            else:
                await messagesender(self.bot, ctx.channel.id, f"Failed to process SoundCloud track. ({file_path})")

    @commands.command(name="spotify", aliases=["sp"])
    async def spotify(self, ctx, url: str):
        """Play from Spotify"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await check_perms(ctx, guild_id, self.bot):
                return

            if guild_id not in self.server_queues:
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return

            track_urls = [url]

            if "playlist" in url:
                await messagesender(self.bot, ctx.channel.id, f"Fetching Spotify playlist: <{url}>")
                try:
                    track_urls = await self.bot.run_blocking_in_executor(get_spotify_tracks_from_playlist, url)

                    if not track_urls:
                        await messagesender(self.bot, ctx.channel.id, "? Failed to retrieve tracks from Spotify playlist.")
                        return
                except Exception as e:
                    await messagesender(self.bot, ctx.channel.id, f"?? Error processing Spotify: {e}")
                    return

            total_tracks = len(track_urls)
            if total_tracks == 0:
                await messagesender(self.bot, ctx.channel.id, "? No tracks found")
                return

            progress_message = await ctx.send(f"?? Processing {total_tracks} track(s) from Spotify")

            async def update_progress(current):
                bar_length = 20
                progress = current / total_tracks
                filled_length = int(bar_length * progress)
                bar = "?" * filled_length + "?" * (bar_length - filled_length)
                await progress_message.edit(content=f"?? Processing Spotify\n[{bar}] {current}/{total_tracks}")

            def _download_sync(ydl_opts, url):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info("https://music.youtube.com/watch?v=" + url, download=True)

            async def S_download_audio(youtube_link):
                output_path = f"music/{youtube_link}.mp3"
                ydl_opts = {
                    'format': 'bestaudio[acodec^=opus]/bestaudio',
                    'cookies': "/config/cookies.txt",
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }],
                    'outtmpl': f'music/%(id)s',
                }

                try:
                    await self.bot.run_blocking_in_executor(_download_sync, ydl_opts, youtube_link)
                    return output_path
                except Exception as e:
                    logging.error(f"Error downloading mp3 format from {youtube_link}: {e}")
                    return False

            async def process_track(track_url):
                try:
                    logging.info(f"?? Converting track: {track_url}")
                    youtube_link = await self.bot.run_blocking_in_executor(spotify_to_youtube, track_url)

                    if not youtube_link:
                        logging.error(f"? Failed to convert {track_url}")
                        return None

                    file_path = await S_download_audio(youtube_link)
                    spotify_title = await self.bot.run_blocking_in_executor(get_spotify_title, track_url)
                    return file_path, spotify_title

                except Exception as e:
                    logging.error(f"?? Error processing track {track_url}: {e}")
                    return None

            tasks = [process_track(track_url) for track_url in track_urls]
            results = await asyncio.gather(*tasks)

            queue_count = 0
            for idx, result in enumerate(results, start=1):
                await update_progress(idx)
                if result:
                    file_path, spotify_title = result
                    await self.server_queues[guild_id].put([file_path, spotify_title])
                    queue_count += 1

            if queue_count == 0:
                await progress_message.edit(content="? No tracks were added to the queue.")
            else:
                await progress_message.edit(content=f"? Added {queue_count}/{total_tracks} tracks to the queue.")

            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await self.bot.play_next(ctx, ctx.voice_client)

    @commands.command(name="applemusic", aliases=["ap"])
    async def applemusic(self, ctx, url: str):
        """Play from Apple Music"""
        async with ctx.typing():
            guild_id = ctx.guild.id
        
            if not await check_perms(ctx, guild_id, self.bot):
                return

            if not self.server_queues.get(guild_id):
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if not await self.handle_voice_connection(ctx):
                return
        
            await messagesender(self.bot, ctx.channel.id, f"Processing Apple Music link: <{url}>")
            video_id = await get_apple_music_audio(ctx, url)
            if video_id:
                await self.bot.queue_and_play_next(ctx, guild_id, video_id)
            else:
                await messagesender(self.bot, ctx.channel.id, content="Failed to find the song.")

    @commands.command(name="grablist", aliases=["grabplaylist"])
    async def playlister(self, ctx, *, search: str = None):
        """Grab and queue a YouTube playlist"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not await check_perms(ctx, guild_id, self.bot):
                return
        
            if guild_id not in self.server_queues:
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}

            if search:
                from utils.youtube_pl import grab_youtube_pl
                playlists_json = await grab_youtube_pl(search)
                playlists = json.loads(playlists_json) 

                if not playlists:
                    await messagesender(self.bot, ctx.channel.id, "No playlists found for query.")
                    return

                index = 0
                playlist_id = playlists[index]
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                playlist_title = await self.bot.get_youtube_playlist_title(playlist_id)

                while "podcast" in playlist_title.lower():
                    index += 1
                    if index >= len(playlists):
                        await messagesender(self.bot, ctx.channel.id, "No suitable playlists found (all contained 'podcast').")
                        return
                    playlist_id = playlists[index]
                    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                    playlist_title = await self.bot.get_youtube_playlist_title(playlist_id)

                video_ids = await self.bot.fetch_playlist_videos(ctx, playlist_id, playlist_url)
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
                        video_title = await get_youtube_video_title(video_id)
                        await self.server_queues[guild_id].put([video_id, video_title])
                        await scanning_message.edit(content=f"Scanning: {video_id} - ({vidscrn}/{vidsadd}/{vidscnt})\nAdded: {video_id}!")

                queue_size = self.server_queues[guild_id].qsize()
                await scanning_message.edit(content=f"Added {queue_size} tracks from the playlist to the queue.")

                if ctx.voice_client is None:
                    channel = ctx.author.voice.channel if ctx.author.voice else None
                    if channel:
                        from utils.common import safe_voice_connect
                        await safe_voice_connect(self.bot, ctx.guild, channel)
                    else:
                        await scanning_message.edit(content=f"You are not in a voice channel.")
                        return

                if not ctx.voice_client.is_playing():
                    await self.bot.play_next(ctx, ctx.voice_client)
            else:
                await messagesender(self.bot, ctx.channel.id, "No search query entered!")

    @commands.command(name="pause", aliases=["hold"])
    async def pause(self, ctx):
        """Pause the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                self.queue_paused[guild_id] = True
                await messagesender(self.bot, ctx.channel.id, content="Paused the music")

    @commands.command(name="resume", aliases=["continue"])
    async def resume(self, ctx):
        """Resume the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if ctx.voice_client and ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                self.queue_paused[guild_id] = False
                await messagesender(self.bot, ctx.channel.id, content="Resumed the music")

    @commands.command(name="stop")
    async def stop(self, ctx):
        """Stop playback and disconnect"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if ctx.voice_client:
                intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
                intentional_disconnections[guild_id] = True
                await ctx.voice_client.disconnect()
                self.server_queues[guild_id] = asyncio.Queue()
                self.current_tracks[guild_id] = {"current_track": None, "is_looping": False}
                await messagesender(self.bot, ctx.channel.id, content="Stopped the bot and left the voice channel.")

    @commands.command(name="skip", aliases=["next"])
    async def skip(self, ctx):
        """Skip the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.stop()
                await messagesender(self.bot, ctx.channel.id, content="Skipped the current track.")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, volume: int):
        """Set the playback volume"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await messagesender(self.bot, ctx.channel.id, content="There's no audio currently playing.")
                return
            
            if 0 <= volume <= 200:
                ctx.voice_client.source = discord.PCMVolumeTransformer(ctx.voice_client.source)
                ctx.voice_client.source.volume = volume / 100
                self.guild_volumes[guild_id] = volume
                self.save_volume_settings(self.guild_volumes)
                await messagesender(self.bot, ctx.channel.id, f"Volume set to {volume}% and saved.")
            else:
                await messagesender(self.bot, ctx.channel.id, content="Volume must be between 0 and 200.")

    @commands.command(name="autoplay", aliases=["autodj"])
    async def autoplay(self, ctx, mode: str):
        """Toggle autoplay mode"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return

            if mode.lower() not in ["on", "off"]:
                await messagesender(self.bot, ctx.channel.id, "Use `!autoplay on` or `!autoplay off`.")
                return

            autoplay_value = mode.lower() == "on"
            self.autoplay_enabled[guild_id] = autoplay_value
            self.update_server_config(guild_id, "autoplay", autoplay_value)
            
            intentional_disconnections = getattr(self.bot, 'intentional_disconnections', {})
            intentional_disconnections[guild_id] = False 

            status = "enabled" if autoplay_value else "disabled"
            await messagesender(self.bot, ctx.channel.id, f"Autoplay is now {status} for this server.")

    @commands.command(name="forceplay", aliases=["fplay"])
    async def forceplay(self, ctx, *, query: str):
        """Force play a track (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        guild_id = ctx.guild.id
        await messagesender(self.bot, ctx.channel.id, content=f"Forcing playback for: {query}")
        await self.play(ctx, srch=query)
        await asyncio.sleep(1) 

        if ctx.voice_client and ctx.voice_client.is_playing():
            logging.info("Having to move things.")
            queue = self.server_queues.get(guild_id)._queue if self.server_queues.get(guild_id) else None

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
                    logging.error("Error moving track in fplay: Invalid index")

            ctx.voice_client.stop()

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx, *, query: str):
        """Search for tracks"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
        
            ydl_opts = {"default_search": "ytsearch10", "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(query, download=False)
                    results = info['entries']
                
                    if not results:
                        await messagesender(self.bot, ctx.channel.id, content="No search results found.")
                        return
                
                    embed = discord.Embed(title=f"Search Results: {query}", color=discord.Color.green())
                    for entry in results[:10]:
                        video_id = entry['id']
                        video_title = entry['title']
                    
                        embed.add_field(name=video_title, value=f"```{ctx.prefix}yt {video_id}```", inline=False)
                    await messagesender(self.bot, ctx.channel.id, embed=embed)
            
                except Exception as e:
                    await messagesender(self.bot, ctx.channel.id, f"Failed to search: {e}")

async def setup(bot):
    await bot.add_cog(Music(bot))

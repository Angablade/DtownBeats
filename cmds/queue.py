# Cog for queue management commands
from discord.ext import commands
import discord
import asyncio
import random
import os
import logging
import shutil
import subprocess
import time
from utils.common import check_perms, messagesender

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Access shared state from bot instance
        self.server_queues = getattr(bot, 'server_queues', {})
        self.current_tracks = getattr(bot, 'current_tracks', {})
        self.track_history = getattr(bot, 'track_history', {})
        self.banned_users = getattr(bot, 'banned_users', {})
        self.metadata_manager = getattr(bot, 'metadata_manager', None)
        self.fetcher = getattr(bot, 'fetcher', None)
        
        # Constants
        self.QUEUE_PAGE_SIZE = int(os.getenv("QUEUE_PAGE_SIZE", "10"))
        self.HISTORY_PAGE_SIZE = int(os.getenv("HISTORY_PAGE_SIZE", "10"))

    @commands.command(name="queue", aliases=["list"])
    async def show_queue(self, ctx, page: int = 1):
        """Show the current queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not self.server_queues.get(guild_id) or self.server_queues[guild_id].empty():
                await messagesender(self.bot, ctx.channel.id, content="The queue is empty.")
                return

            queue = list(self.server_queues[guild_id]._queue)
        
            items_per_page = self.QUEUE_PAGE_SIZE
            total_pages = (len(queue) + items_per_page - 1) // items_per_page
        
            if page < 1 or page > total_pages:
                await messagesender(self.bot, ctx.channel.id, f"Invalid page number. Please enter a number between 1 and {total_pages}.")
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
                except Exception as e:
                    logging.error("Error processing queue item.")
            await messagesender(self.bot, ctx.channel.id, embed=embed)

    @commands.command(name="clear")
    async def clear(self, ctx):
        """Clear the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if self.server_queues.get(guild_id):
                self.server_queues[guild_id]._queue.clear()
            await messagesender(self.bot, ctx.channel.id, content="Cleared the queue.")

    @commands.command(name="remove")
    async def remove(self, ctx, index: int):
        """Remove a track from the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            try:
                removed = self.server_queues[guild_id]._queue.pop(index - 1)
                await messagesender(self.bot, ctx.channel.id, f"Removed track {removed} from the queue.")
            except IndexError:
                await messagesender(self.bot, ctx.channel.id, content="Invalid index.")

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx):
        """Toggle loop mode"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            self.current_tracks[guild_id]["is_looping"] = not self.current_tracks[guild_id].get("is_looping", False)
            await messagesender(self.bot, ctx.channel.id, content="Looping " + ("enabled." if self.current_tracks[guild_id]["is_looping"] else "disabled."))

    @commands.command(name="shuffle")
    async def shuffle_queue(self, ctx):
        """Shuffle the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if self.server_queues.get(guild_id) and len(self.server_queues[guild_id]._queue) > 1:
                random.shuffle(self.server_queues[guild_id]._queue)
                await messagesender(self.bot, ctx.channel.id, content="The queue has been shuffled! ??")
            else:
                await messagesender(self.bot, ctx.channel.id, content="The queue is too short to shuffle.")

    @commands.command(name="move")
    async def move_song(self, ctx, from_pos: int, to_pos: int):
        """Move a track in the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            queue = self.server_queues.get(guild_id)._queue if self.server_queues.get(guild_id) else None

            if queue and 1 <= from_pos <= len(queue) and 1 <= to_pos <= len(queue):
                from_pos -= 1
                to_pos -= 1
                track = queue[from_pos]
                del queue[from_pos]
                queue.insert(to_pos, track)

                await messagesender(self.bot, ctx.channel.id, f"Moved **{''.join(track[1:])}** from position {from_pos + 1} to {to_pos + 1}.")
            else:
                await messagesender(self.bot, ctx.channel.id, content="Invalid positions. Please provide valid track numbers from the queue.")

    @commands.command(name="history", aliases=["played"])
    async def history(self, ctx):
        """Show recently played tracks"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return

            history_list = self.track_history.get(guild_id, [])

            if not history_list:
                await messagesender(self.bot, ctx.channel.id, "No recent tracks available.")
                return
        
            embed = discord.Embed(title="?? Recently Played Songs", color=discord.Color.blue())
            for index, track in enumerate(history_list[-self.HISTORY_PAGE_SIZE:], start=1):
                embed.add_field(name=f"{index}. {track[1]}", value=f"ID: {track[0]}", inline=False)
            await messagesender(self.bot, ctx.channel.id, embed=embed)

    @commands.command(name="nowplaying", aliases=["current", "np"])
    async def nowplaying(self, ctx):
        """Show the currently playing track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return

            current_track = self.current_tracks.get(guild_id, {}).get("current_track")
            if not current_track:
                await messagesender(self.bot, ctx.channel.id, content="No track is currently playing.")
                return

            video_id = current_track[0]
            metadata = self.metadata_manager.load_metadata(video_id)
            if not metadata:
                video_title = current_track[1]
                metadata = self.metadata_manager.get_or_fetch_metadata(video_id, video_title)
                self.metadata_manager.save_metadata(video_id, metadata)

            artist = metadata["artist"]
            title = metadata["title"]
            duration = metadata.get("duration", "Unknown")

            image_path = self.fetcher.get_album_art(title)
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
            try:
                embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02d}" if duration != "Unknown" else "Unknown", inline=True)
            except Exception as e:
                try:
                    audio_file = self.bot.retrieve_audio_file_for_current_track(guild_id)
                    duration = self.metadata_manager.ffmpeg_get_track_length(audio_file)
                    embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02d}" if duration != "Unknown" else "Unknown", inline=True)
                except Exception as e:
                    embed.add_field(name="Duration", value="Unknown", inline=True)
            embed.set_footer(text=f"ID: {video_id}", icon_url="https://cdn.discordapp.com/avatars/1216449470149955684/137c7c7d86c6d383ae010ca347396b47.webp?size=240")

            await messagesender(self.bot, ctx.channel.id, embed=embed, file=file)

    @commands.command(name="seek")
    async def seek(self, ctx, position: str):
        """Seek to a position in the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return
            
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await messagesender(self.bot, ctx.channel.id, content="There's no audio currently playing.")
                return

            current_track = self.current_tracks.get(guild_id, {}).get("current_track")
            if not current_track:
                await messagesender(self.bot, ctx.channel.id, content="There's no track information available to seek.")
                return
        
            video_id = current_track[0] 
            audio_file = f"music/{video_id}.mp3"
            if not os.path.exists(audio_file):
                audio_file = f"music/{video_id}.opus"
            if not os.path.exists(audio_file):
                await messagesender(self.bot, ctx.channel.id, content="Audio file not found for seeking.")
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
                    logging.error(f"Error getting duration: {e}")
                return None

            duration = get_audio_duration(audio_file)
            if not duration:
                await messagesender(self.bot, ctx.channel.id, content="Could not determine audio duration.")
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
                source = discord.FFmpegPCMAudio(audio_file, executable="ffmpeg", options=ffmpeg_options)
                ctx.voice_client.play(source, after=lambda _: asyncio.run_coroutine_threadsafe(self.bot.play_next(ctx, ctx.voice_client), self.bot.loop))

                await messagesender(self.bot, ctx.channel.id, f"? Seeking to `{seconds}` seconds.")
        
            except Exception as e:
                await messagesender(self.bot, ctx.channel.id, f"An error occurred while seeking: {e}")

    @commands.command(name="sendplox", aliases=["dlfile"])
    async def sendmp3(self, ctx):
        """Send the current track file"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await check_perms(ctx, guild_id, self.bot):
                return

            current_track = self.current_tracks.get(guild_id, {}).get("current_track")
            
            if not current_track:
                await messagesender(self.bot, ctx.channel.id, content="No current track found.")
                return
            
            base_filename, _ = os.path.splitext(current_track[0])
            
            possible_extensions = [".mp3", ".opus"]
            
            file_path = None
            for ext in possible_extensions:
                path = f"music/{base_filename}{ext}"
                if os.path.exists(path):
                    file_path = path
                    break
            
            if not file_path:
                await messagesender(self.bot, ctx.channel.id, content="File not found.")
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

async def setup(bot):
    await bot.add_cog(Queue(bot))

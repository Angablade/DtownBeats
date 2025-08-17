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

    async def check_perms(self, ctx, guild_id):
        """Check if user has permissions to use queue commands"""
        if ctx.author.id in self.banned_users:
            await self.messagesender(ctx.channel.id, content="You are banned from using this bot.")
            return False
        return True

    async def messagesender(self, channel_id, content=None, embed=None, file=None):
        """Send messages to Discord channels"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logging.error(f"[Error] Channel with ID {channel_id} not found.")
            return
        
        try:
            if content and embed and file:
                await channel.send(content=content, embed=embed, file=file)
            elif content and embed:
                await channel.send(content=content, embed=embed)
            elif content and file:
                await channel.send(content=content, file=file)
            elif embed and file:
                await channel.send(embed=embed, file=file)
            elif content:
                await channel.send(content=content)
            elif embed:
                await channel.send(embed=embed)
            elif file:
                await channel.send(file=file)
        except discord.HTTPException as e:
            logging.error(f"[Error] Failed to send message: {e}")

    @commands.command(name="queue", aliases=["list"])
    async def show_queue(self, ctx, page: int = 1):
        """Show the current queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id

            if not self.server_queues.get(guild_id) or self.server_queues[guild_id].empty():
                await self.messagesender(ctx.channel.id, content="The queue is empty.")
                return

            queue = list(self.server_queues[guild_id]._queue)
        
            items_per_page = self.QUEUE_PAGE_SIZE
            total_pages = (len(queue) + items_per_page - 1) // items_per_page
        
            if page < 1 or page > total_pages:
                await self.messagesender(ctx.channel.id, f"Invalid page number. Please enter a number between 1 and {total_pages}.")
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
            await self.messagesender(ctx.channel.id, embed=embed)

    @commands.command(name="clear")
    async def clear(self, ctx):
        """Clear the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if self.server_queues.get(guild_id):
                self.server_queues[guild_id]._queue.clear()
            await self.messagesender(ctx.channel.id, content="Cleared the queue.")

    @commands.command(name="remove")
    async def remove(self, ctx, index: int):
        """Remove a track from the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            try:
                removed = self.server_queues[guild_id]._queue.pop(index - 1)
                await self.messagesender(ctx.channel.id, f"Removed track {removed} from the queue.")
            except IndexError:
                await self.messagesender(ctx.channel.id, content="Invalid index.")

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx):
        """Toggle loop mode"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            self.current_tracks[guild_id]["is_looping"] = not self.current_tracks[guild_id].get("is_looping", False)
            await self.messagesender(ctx.channel.id, content="Looping " + ("enabled." if self.current_tracks[guild_id]["is_looping"] else "disabled."))

    @commands.command(name="shuffle")
    async def shuffle_queue(self, ctx):
        """Shuffle the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if self.server_queues.get(guild_id) and len(self.server_queues[guild_id]._queue) > 1:
                random.shuffle(self.server_queues[guild_id]._queue)
                await self.messagesender(ctx.channel.id, content="The queue has been shuffled! ??")
            else:
                await self.messagesender(ctx.channel.id, content="The queue is too short to shuffle.")

    @commands.command(name="move")
    async def move_song(self, ctx, from_pos: int, to_pos: int):
        """Move a track in the queue"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            queue = self.server_queues.get(guild_id)._queue if self.server_queues.get(guild_id) else None

            if queue and 1 <= from_pos <= len(queue) and 1 <= to_pos <= len(queue):
                from_pos -= 1
                to_pos -= 1
                track = queue[from_pos]
                del queue[from_pos]
                queue.insert(to_pos, track)

                await self.messagesender(ctx.channel.id, f"Moved **{''.join(track[1:])}** from position {from_pos + 1} to {to_pos + 1}.")
            else:
                await self.messagesender(ctx.channel.id, content="Invalid positions. Please provide valid track numbers from the queue.")

    @commands.command(name="history", aliases=["played"])
    async def history(self, ctx):
        """Show recently played tracks"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return

            history_list = self.track_history.get(guild_id, [])

            if not history_list:
                await self.messagesender(ctx.channel.id, "No recent tracks available.")
                return
        
            embed = discord.Embed(title="\U0001F3B5 Recently Played Songs", color=discord.Color.blue())
            for index, track in enumerate(history_list[-self.HISTORY_PAGE_SIZE:], start=1):
                embed.add_field(name=f"{index}. {track[1]}", value=f"ID: {track[0]}", inline=False)
            await self.messagesender(ctx.channel.id, embed=embed)

    @commands.command(name="nowplaying", aliases=["current", "np"])
    async def nowplaying(self, ctx):
        """Show the currently playing track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return

            current_track = self.current_tracks.get(guild_id, {}).get("current_track")
            if not current_track:
                await self.messagesender(ctx.channel.id, content="No track is currently playing.")
                return

            video_id = current_track[0]
            video_title = current_track[1]

            embed = discord.Embed(
                title="Now Playing",
                description=f"**{video_title}**",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"ID: {video_id}")

            await self.messagesender(ctx.channel.id, embed=embed)

    @commands.command(name="seek")
    async def seek(self, ctx, position: str):
        """Seek to a position in the current track"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
            
            if not ctx.voice_client or not ctx.voice_client.is_playing():
                await self.messagesender(ctx.channel.id, content="There's no audio currently playing.")
                return

            await self.messagesender(ctx.channel.id, content=f"Seeking to position: {position}")

    @commands.command(name="sendplox", aliases=["dlfile"])
    async def sendmp3(self, ctx):
        """Send the current track file"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return

            current_track = self.current_tracks.get(guild_id, {}).get("current_track")
            
            if not current_track:
                await self.messagesender(ctx.channel.id, content="No current track found.")
                return
            
            await self.messagesender(ctx.channel.id, content="File sending feature not fully implemented yet.")

    @commands.command(name="search", aliases=["find"])
    async def search(self, ctx, *, query: str):
        """Search for tracks"""
        async with ctx.typing():
            guild_id = ctx.guild.id
            if not await self.check_perms(ctx, guild_id):
                return
        
            await self.messagesender(ctx.channel.id, content=f"Searching for: {query}")

async def setup(bot):
    await bot.add_cog(Queue(bot))

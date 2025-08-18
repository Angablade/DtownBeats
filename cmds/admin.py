# Cog for admin commands
from discord.ext import commands
import discord
import os
import shutil
import subprocess
import sys
import asyncio
import json
import time
import logging
try:
    import psutil
except ImportError:
    psutil = None
    
import platform
from utils.common import messagesender

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 123456789))
        self.QUEUE_BACKUP_DIR = "config/queuebackup/"
        self.LOG_FILE = "config/debug.log"

    def get_backup_path(self, guild_id=None):
        """Get backup file path"""
        if guild_id:
            return os.path.join(self.QUEUE_BACKUP_DIR, f"{guild_id}.json")
        return os.path.join(self.QUEUE_BACKUP_DIR, "global_backup.json")

    def save_queue_backup(self, guild_id=None):
        """Save queue backup"""
        server_queues = getattr(self.bot, 'server_queues', {})
        backup_path = self.get_backup_path(guild_id)
        backup_data = {}
        
        if guild_id:
            backup_data[guild_id] = list(server_queues.get(guild_id, asyncio.Queue())._queue)
        else:
            for gid, queue in server_queues.items():
                backup_data[gid] = list(queue._queue)
        
        with open(backup_path, "w") as f:
            json.dump(backup_data, f, indent=4)

    def load_queue_backup(self, guild_id=None):
        """Load queue backup"""
        backup_path = self.get_backup_path(guild_id)
        if os.path.exists(backup_path):
            with open(backup_path, "r") as f:
                return json.load(f)
        return {}

    @commands.command(name="health")
    async def health_check(self, ctx):
        """Get bot health status (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        try:
            # Get system stats if psutil is available
            if psutil:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
            else:
                cpu_percent = "N/A"
                memory = type('obj', (object,), {'percent': 'N/A', 'available': 0})()
                disk = type('obj', (object,), {'percent': 'N/A', 'free': 0})()
            
            uptime = time.time() - getattr(self.bot, 'start_time', time.time())
            server_queues = getattr(self.bot, 'server_queues', {})
            now_playing = getattr(self.bot, 'now_playing', {})
            
            # Create embed
            embed = discord.Embed(
                title="Bot Health Status",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Bot status
            embed.add_field(
                name="Bot Status",
                value=f"**Status:** Healthy\n"
                      f"**Uptime:** {int(uptime // 3600)}h {int((uptime % 3600) // 60)}m\n"
                      f"**Guilds:** {len(self.bot.guilds)}\n"
                      f"**Ping:** {round(self.bot.latency * 1000)}ms",
                inline=True
            )
            
            # System resources
            if psutil:
                embed.add_field(
                    name="System Resources",
                    value=f"**CPU:** {cpu_percent}%\n"
                          f"**Memory:** {memory.percent}% ({round(memory.available / (1024**3), 1)}GB free)\n"
                          f"**Disk:** {disk.percent}% ({round(disk.free / (1024**3), 1)}GB free)",
                    inline=True
                )
            else:
                embed.add_field(
                    name="System Resources",
                    value="**System monitoring not available**\n(psutil not installed)",
                    inline=True
                )
            
            # Music activity
            active_queues = len([q for q in server_queues.values() if not q.empty()])
            total_queued = sum(q.qsize() for q in server_queues.values())
            
            embed.add_field(
                name="Music Activity",
                value=f"**Active Queues:** {active_queues}\n"
                      f"**Now Playing:** {len(now_playing)}\n"
                      f"**Total Queued:** {total_queued}",
                inline=True
            )
            
            # Add platform info
            embed.set_footer(text=f"Platform: {platform.system()} {platform.release()}")
            
            await messagesender(self.bot, ctx.channel.id, embed=embed)
            
        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"Error getting health status: {e}")

    @commands.command(name="metrics", aliases=["sysinfo"])
    async def detailed_metrics(self, ctx):
        """Get detailed system metrics (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        try:
            # System metrics
            if psutil:
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()
                boot_time = psutil.boot_time()
            else:
                cpu_percent = cpu_count = "N/A"
                memory = type('obj', (object,), {'total': 0, 'used': 0, 'percent': 'N/A', 'available': 0})()
                disk = type('obj', (object,), {'total': 0, 'used': 0, 'percent': 'N/A', 'free': 0})()
                network = type('obj', (object,), {'bytes_sent': 0, 'bytes_recv': 0})()
                boot_time = time.time()
            
            # Bot metrics
            uptime = time.time() - getattr(self.bot, 'start_time', time.time())
            server_queues = getattr(self.bot, 'server_queues', {})
            now_playing = getattr(self.bot, 'now_playing', {})
            track_history = getattr(self.bot, 'track_history', {})
            
            # Calculate queue sizes
            queue_sizes = {str(guild_id): q.qsize() for guild_id, q in server_queues.items()}
            total_tracks_queued = sum(queue_sizes.values())
            total_history = sum(len(hist) for hist in track_history.values())
            
            # Create embeds (split due to Discord limits)
            embed1 = discord.Embed(
                title="Detailed System Metrics",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # System info
            embed1.add_field(
                name="System Information",
                value=f"**Platform:** {platform.system()} {platform.release()}\n"
                      f"**Architecture:** {platform.machine()}\n"
                      f"**Python:** {platform.python_version()}\n"
                      f"**Boot Time:** <t:{int(boot_time)}:R>",
                inline=False
            )
            
            # CPU & Memory
            if psutil:
                embed1.add_field(
                    name="CPU & Memory",
                    value=f"**CPU Usage:** {cpu_percent}%\n"
                          f"**CPU Cores:** {cpu_count}\n"
                          f"**Memory Total:** {round(memory.total / (1024**3), 2)}GB\n"
                          f"**Memory Used:** {round(memory.used / (1024**3), 2)}GB ({memory.percent}%)\n"
                          f"**Memory Available:** {round(memory.available / (1024**3), 2)}GB",
                    inline=True
                )
                
                # Disk & Network
                embed1.add_field(
                    name="Disk & Network",
                    value=f"**Disk Total:** {round(disk.total / (1024**3), 2)}GB\n"
                          f"**Disk Used:** {round(disk.used / (1024**3), 2)}GB ({disk.percent}%)\n"
                          f"**Disk Free:** {round(disk.free / (1024**3), 2)}GB\n"
                          f"**Network Sent:** {round(network.bytes_sent / (1024**2), 1)}MB\n"
                          f"**Network Received:** {round(network.bytes_recv / (1024**2), 1)}MB",
                    inline=True
                )
            else:
                embed1.add_field(
                    name="System Resources",
                    value="**System monitoring not available**\n(psutil not installed)",
                    inline=False
                )
            
            # Bot metrics embed
            embed2 = discord.Embed(
                title="Bot Metrics",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed2.add_field(
                name="Bot Statistics",
                value=f"**Uptime:** {int(uptime // 86400)}d {int((uptime % 86400) // 3600)}h {int((uptime % 3600) // 60)}m\n"
                      f"**Guilds:** {len(self.bot.guilds)}\n"
                      f"**Latency:** {round(self.bot.latency * 1000)}ms\n"
                      f"**Commands:** {len(self.bot.commands)}",
                inline=True
            )
            
            embed2.add_field(
                name="Music Statistics",
                value=f"**Active Queues:** {len([q for q in server_queues.values() if not q.empty()])}\n"
                      f"**Total Tracks Queued:** {total_tracks_queued}\n"
                      f"**Now Playing Count:** {len(now_playing)}\n"
                      f"**Total History Tracks:** {total_history}",
                inline=True
            )
            
            # Top 5 queue sizes
            if queue_sizes:
                top_queues = sorted(queue_sizes.items(), key=lambda x: x[1], reverse=True)[:5]
                queue_text = "\n".join([f"**{guild_id}:** {size}" for guild_id, size in top_queues])
                embed2.add_field(
                    name="Top Queues",
                    value=queue_text or "No active queues",
                    inline=False
                )
            
            await messagesender(self.bot, ctx.channel.id, embed=embed1)
            await messagesender(self.bot, ctx.channel.id, embed=embed2)
            
        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"Error getting metrics: {e}")
            logging.error(f"Error in metrics command: {e}")

    @commands.command(name="webpanel", aliases=["panel", "web"])
    async def web_panel_info(self, ctx):
        """Get web panel access information (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        web_port = os.getenv('WEB_PORT', '80')
        session_secret = os.getenv('SESSION_SECRET', 'change_me_secret')
        discord_client_id = os.getenv('DISCORD_CLIENT_ID', '')
        
        embed = discord.Embed(
            title="Web Panel Information",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="Access Information",
            value=f"**Port:** {web_port}\n"
                  f"**Health Check:** `/health`\n"
                  f"**Metrics:** `/metrics`\n"
                  f"**Queues:** `/queues`\n"
                  f"**Library:** `/library`",
            inline=True
        )
        
        embed.add_field(
            name="OAuth Status",
            value=f"**Client ID Configured:** {'Yes' if discord_client_id else 'No'}\n"
                  f"**Session Secret:** {'Set' if session_secret != 'change_me_secret' else 'Default'}\n"
                  f"**OAuth Available:** {'Yes' if discord_client_id else 'No'}",
            inline=True
        )
        
        embed.add_field(
            name="Quick Links",
            value="**Endpoints:**\n"
                  "- `/health` - Health status\n"
                  "- `/metrics` - Detailed metrics\n"
                  "- `/queues` - All guild queues\n"
                  "- `/library` - Music library\n"
                  "- `/login` - Discord OAuth login",
            inline=False
        )
        
        if session_secret == 'change_me_secret':
            embed.add_field(
                name="Security Warning",
                value="The SESSION_SECRET is still set to default. Please update it for security!",
                inline=False
            )
        
        await messagesender(self.bot, ctx.channel.id, embed=embed)

    @commands.command(name="shutdown", aliases=["die"])
    async def shutdown(self, ctx):
        """Shutdown the bot (Owner only)"""
        logging.info(f"Requesting ID: {ctx.author.id}\nOwner ID:{self.BOT_OWNER_ID}")
        if ctx.author.id == self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="Shutting down.")
            await self.bot.close()
        else:
            await messagesender(self.bot, ctx.channel.id, content="You do not have permission to shut down the bot.")

    @commands.command(name="reboot", aliases=["restart"])
    async def reboot(self, ctx):
        """Restart the bot (Owner only)"""
        logging.info(f"Requesting ID: {ctx.author.id}\nOwner ID:{self.BOT_OWNER_ID}")
        if ctx.author.id == self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="Restarting the bot...")
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            await messagesender(self.bot, ctx.channel.id, content="You do not have permission to restart the bot.")

    @commands.command(name="dockboot", aliases=["dockerrestart"])
    async def dockboot(self, ctx):
        """Docker restart (Owner only)"""
        logging.info(f"Requesting ID: {ctx.author.id}\nOwner ID: {self.BOT_OWNER_ID}")
        if ctx.author.id == self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="Shutting down and restarting")
            subprocess.Popen(["/bin/bash", "init.sh"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os._exit(0)  
        else:
            await messagesender(self.bot, ctx.channel.id, content="You do not have permission to restart the bot.")

    @commands.command(name="say")
    async def say(self, ctx, guild_id: int, channel_id: int, *, message: str):
        """
        Makes the bot send a specified message in a given channel from a given server.
        Only available via DM from the bot owner.
        Usage: say <guild_id> <channel_id> "<message>"
        """
        if ctx.guild is not None:
            await ctx.send("? This command can only be used in DMs.")
            return

        if ctx.author.id != self.BOT_OWNER_ID:
            await ctx.send("? You are not authorized to use this command.")
            return

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await ctx.send("? Could not find the specified guild.")
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            await ctx.send("? Could not find the specified channel in the given guild.")
            return

        try:
            await channel.send(message)
            await ctx.send("? Message sent successfully.")
        except Exception as e:
            await ctx.send(f"? Failed to send message: {e}")

    @commands.command(name="backupqueue")
    async def backup_queue(self, ctx, scope: str = "guild"):
        """Backup queue (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        if scope == "global":
            self.save_queue_backup()
            await messagesender(self.bot, ctx.channel.id, content="Global queue backup saved.")
        else:
            self.save_queue_backup(ctx.guild.id)
            await messagesender(self.bot, ctx.channel.id, content=f"Queue backup saved for {ctx.guild.name}.")

    @commands.command(name="restorequeue")
    async def restore_queue(self, ctx, scope: str = "guild"):
        """Restore queue from backup (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        server_queues = getattr(self.bot, 'server_queues', {})
        
        if scope == "global":
            backup_data = self.load_queue_backup()
            for gid, queue_data in backup_data.items():
                if gid not in server_queues:
                    server_queues[gid] = asyncio.Queue()
                for item in queue_data:
                    await server_queues[gid].put(item)
            await messagesender(self.bot, ctx.channel.id, content="Global queue restored.")
        else:
            backup_data = self.load_queue_backup(ctx.guild.id)
            if ctx.guild.id not in server_queues:
                server_queues[ctx.guild.id] = asyncio.Queue()
            for item in backup_data.get(str(ctx.guild.id), []):
                await server_queues[ctx.guild.id].put(item)
            await messagesender(self.bot, ctx.channel.id, content=f"Queue restored for {ctx.guild.name}.")

    @commands.command(name="purgequeues")
    async def purge_queues(self, ctx):
        """Purge all queues (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        server_queues = getattr(self.bot, 'server_queues', {})
        cleared_count = 0
        
        for guild_id in list(server_queues.keys()):
            if isinstance(server_queues[guild_id], asyncio.Queue):
                server_queues[guild_id] = asyncio.Queue()
                cleared_count += 1
        
        await messagesender(self.bot, ctx.channel.id, content=f"Cleared queues for {cleared_count} servers.")

    @commands.command(name="sendglobalmsg")
    async def send_global_message(self, ctx, *, message: str):
        """Send message to all servers (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return
        
        success_count = 0
        failure_count = 0
        last_active_channels = getattr(self.bot, 'last_active_channels', {})
        
        for guild in self.bot.guilds:
            target_channel = None
            
            # Check last active channel first
            if guild.id in last_active_channels:
                target_channel = self.bot.get_channel(last_active_channels[guild.id])
            
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
        
        await messagesender(self.bot, ctx.channel.id, content=f"Message sent to {success_count} servers. Failed in {failure_count}.")

    @commands.command(name="updateyt")
    async def update_yt_dlp(self, ctx):
        """Update yt-dlp (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        await messagesender(self.bot, ctx.channel.id, content="?? Updating pip and yt-dlp...")
        try:
            pip_proc = await asyncio.create_subprocess_exec(
                "python3", "-m", "pip", "install", "--upgrade", "pip",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await pip_proc.communicate()

            yt_proc = await asyncio.create_subprocess_exec(
                "python3", "-m", "pip", "install", "--no-cache-dir", "--upgrade", "--force-reinstall", "yt-dlp",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await yt_proc.communicate()

            if yt_proc.returncode == 0:
                output = stdout.decode().strip()
                await messagesender(self.bot, ctx.channel.id, content=f"? yt-dlp updated:\n```\n{output}\n```")
            else:
                error = stderr.decode().strip()
                await messagesender(self.bot, ctx.channel.id, content=f"? Update failed:\n```\n{error}\n```")

        except Exception as e:
            await messagesender(self.bot, ctx.channel.id, content=f"? Error: {str(e)}")

    @commands.command(name="fetchlogs", aliases=["logs"])
    async def fetchlogs(self, ctx):
        """Fetch and send bot logs (Owner only)"""
        if ctx.author.id != self.BOT_OWNER_ID:
            await messagesender(self.bot, ctx.channel.id, content="You don't have permission to use this command.")
            return

        if not os.path.exists(self.LOG_FILE):
            await messagesender(self.bot, ctx.channel.id, content="File not found.")
            return

        file_size = os.path.getsize(self.LOG_FILE)
        if file_size > 8 * 1024 * 1024:
            zip_path = self.LOG_FILE + ".zip"
            shutil.make_archive(self.LOG_FILE, 'zip', root_dir=os.path.dirname(self.LOG_FILE), base_dir=os.path.basename(self.LOG_FILE))
            zip_size = os.path.getsize(zip_path)
            if zip_size > 8 * 1024 * 1024:
                split_path = self.LOG_FILE + ".7z"
                split_command = f'7z a -t7z -v7m "{split_path}" "{self.LOG_FILE}"'
                subprocess.run(split_command, shell=True)
                split_parts = [f for f in os.listdir(os.path.dirname(self.LOG_FILE)) if f.startswith(os.path.basename(split_path))]
                for part in sorted(split_parts):
                    part_path = os.path.join(os.path.dirname(self.LOG_FILE), part)
                    await ctx.author.send(file=discord.File(part_path))
                    os.remove(part_path)
            else:
                with open(zip_path, 'rb') as file:
                    await ctx.author.typing()
                    await ctx.author.send(file=discord.File(file, filename=os.path.basename(zip_path)))
                os.remove(zip_path) 
        else:
            with open(self.LOG_FILE, 'rb') as file:
                await ctx.author.typing()
                await ctx.author.send(file=discord.File(file, filename=os.path.basename(self.LOG_FILE)))
                await messagesender(self.bot, ctx.channel.id, content="Sent debug logs via DM.")

async def setup(bot):
    await bot.add_cog(Admin(bot))

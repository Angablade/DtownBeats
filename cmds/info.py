# Cog for info and utility commands
from discord.ext import commands
import discord
import os
import time
import platform
import resource
import shutil

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = getattr(bot, 'start_time', time.time())
        self.LOG_FILE = "config/debug.log"
        self.COMMANDS_FILE_PATH = "config/commands.txt"

    async def messagesender(self, channel_id, content=None, embed=None, file=None):
        """Send messages to Discord channels"""
        channel = self.bot.get_channel(channel_id)
        if not channel:
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
                await channel.send(content)
            elif embed:
                await channel.send(embed=embed)
            elif file:
                await channel.send(file=file)
        except Exception as e:
            print(f"Error sending message: {e}")

    @commands.command(name="stats")
    async def stats(self, ctx):
        uptime = time.time() - self.start_time
        server_count = len(self.bot.guilds)

        if platform.system() == "Windows":
            process = os.popen('wmic process where "ProcessId=%d" get WorkingSetSize' % os.getpid())
            memory_usage = int(process.read().strip().split("\n")[-1]) / (1024 * 1024)
            process.close()
        else:
            memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        embed = discord.Embed(title="?? Bot Stats", color=discord.Color.green())
        embed.add_field(name="? Uptime", value=f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s", inline=False)
        embed.add_field(name="?? Memory Usage", value=f"{memory_usage:.2f} MB", inline=False)
        embed.add_field(name="?? Servers", value=f"{server_count} servers", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="version", aliases=["ver"])
    async def version(self, ctx):
        async with ctx.typing():
                                                #[HHMMSS-DDMMYYYY]
            embed = discord.Embed(
                title=f"DtownBeats - Version 0.4J.5 [023323-04072025]",
                description="?? Bringing beats to your server with style!",
                color=discord.Color.dark_blue()
            )

            embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/1216449470149955684/137c7c7d86c6d383ae010ca347396b47.webp?size=240")
        
            embed.add_field(name="", value=(""), inline=False)

            embed.add_field(
                name="?? Source Code",
                value="[GitHub Repository](https://github.com/Angablade/DtownBeats)",
                inline=False
            )

            embed.add_field(name="", value=(""), inline=False)

            embed.add_field(
                name="?? Docker Image",
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
                await self.messagesender(ctx.channel.id, content="I've sent you a DM with the bot version. ??")
            except discord.Forbidden:
                await self.messagesender(ctx.channel.id, content="I couldn't send you a DM. Please check your privacy settings.")

    @commands.command(name="cmds", aliases=["commands"])
    async def help_command(self, ctx):
        async with ctx.typing():
            commands_text = """Available Commands:
            
            ?? **Music Commands**
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
            
            ? **Queue Commands**
            Command           | Aliases        | Description
            ------------------|----------------|---------------------------------
            clear             | None           | Clear the queue
            remove <#>        | None           | Remove a song from the queue
            loop              | repeat         | Toggle looping
            shuffle           | None           | Shuffle the queue
            move <#> <#>      | None           | Move a song in the queue
            history           | played         | Show recently played tracks
            
            ?? **Configuration**
            Command            | Aliases        | Description
            -------------------|----------------|--------------------------------
            setprefix <p>      | prefix         | Change the bot prefix
            setdjrole <r>      | setrole        | Assign DJ role
            setchannel <c>     | None           | Restrict bot to a channel
            debugmode          | None           | Toggle debug logging
            showstats          | None           | Toggle bot stats in profile
            
            ??? **Admin Commands**
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
            
            ?? **Other Commands**
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
            
            with open(self.COMMANDS_FILE_PATH, "w") as f:
                f.write(commands_text)
         
            try:
                await ctx.author.send(file=discord.File(self.COMMANDS_FILE_PATH))
                await ctx.send(f"{ctx.author.mention}, I've sent you the command list as a file.")
            except discord.Forbidden:
                await ctx.send(f"{ctx.author.mention}, I couldn't send you a DM. Please check your privacy settings.")

    @commands.command(name="invite", aliases=["link"])
    async def invite(self, ctx):
        bot_id = self.bot.user.id 
        permissions = 277025515584
        scopes = "bot"
        invite_url = f"https://discord.com/oauth2/authorize?client_id={bot_id}&permissions={permissions}&scope={scopes}"
        await ctx.author.send(f"<:afoyawn:1330375212302336030> Invite me to your server using this link: {invite_url}")

    @commands.command(name="fetchlogs", aliases=["logs"])
    async def fetchlogs_cmd(self, ctx):
        if not os.path.exists(self.LOG_FILE):
            await ctx.send("File not found.")
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
                await ctx.send("Sent debug logs via DM.")

async def setup(bot):
    await bot.add_cog(Info(bot))

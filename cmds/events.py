# Cog for bot events
from discord.ext import commands
import discord
import logging

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to do that.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: {error.param.name}")
        else:
            await ctx.send(f"An error occurred: {error}")
            raise error

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        message_map = getattr(self.bot, 'message_map', {})
        if message.id in message_map:
            try:
                await message_map[message.id].delete()
            except discord.NotFound:
                pass
            del message_map[message.id]

async def setup(bot):
    await bot.add_cog(Events(bot))

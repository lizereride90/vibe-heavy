"""General: !help, !ping, !model."""
import discord
from discord.ext import commands

from config import settings as cfg


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):
        await ctx.reply(
            "**VibeHeavy** 💪 (runs here, not 24/7)\n"
            "`@me <task>` — build anything → reply + zip\n"
            "`!run <cmd>` `!up <name> <cmd>` `!down <name>` `!ps` `!logs <name>` (admin)\n"
            "`!zip <path>` `!get <path>` `!files [path]` (admin)\n"
            f"`!model` — current opencode model")

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.reply(f"pong ({round(self.bot.latency * 1000)}ms)")

    @commands.command(name="model")
    async def model(self, ctx: commands.Context):
        await ctx.reply(f"🧠 `{cfg.MODEL}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))

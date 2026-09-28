"""Shell + supervisor: !run !up !down !ps !logs (admins only)."""
import discord
from discord.ext import commands

from config import settings as cfg
from core import engine, supervisor as sup
from core.helpers import admin_only, chunked_send


class Shell(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="run")
    async def run(self, ctx: commands.Context, *, shell: str = ""):
        """Run a shell command in the sandbox."""
        if not await admin_only(ctx):
            return
        if not shell.strip():
            await ctx.reply("usage: `!run <shell command>`")
            return
        async with ctx.typing():
            out = await engine.run_shell(shell.strip(), cfg.RUN_TIMEOUT)
        await chunked_send(ctx.channel, f"```\n{engine.redact(out)[-1800:]}\n```")

    @commands.command(name="up")
    async def up(self, ctx: commands.Context, name: str = "", *, cmd: str = ""):
        """Keep a command running in background: !up <name> <command...>"""
        if not await admin_only(ctx):
            return
        if not name or not cmd:
            await ctx.reply("usage: `!up <name> <command...>`")
            return
        _, msg = sup.start(name, cmd)
        await ctx.reply(msg)

    @commands.command(name="down")
    async def down(self, ctx: commands.Context, name: str = ""):
        """Stop a background job."""
        if not await admin_only(ctx):
            return
        if not name:
            await ctx.reply("usage: `!down <name>`")
            return
        await ctx.reply(sup.stop(name))

    @commands.command(name="ps")
    async def ps(self, ctx: commands.Context):
        """List background jobs."""
        if not await admin_only(ctx):
            return
        await ctx.reply(sup.list_procs())

    @commands.command(name="logs")
    async def logs(self, ctx: commands.Context, name: str = ""):
        """Tail a background job's log."""
        if not await admin_only(ctx):
            return
        if not name:
            await ctx.reply("usage: `!logs <name>`")
            return
        await chunked_send(ctx.channel, f"```\n{sup.tail(name)[-1800:]}\n```")


async def setup(bot: commands.Bot):
    await bot.add_cog(Shell(bot))

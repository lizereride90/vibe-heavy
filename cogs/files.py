"""File drops: !zip !get !files (admins only)."""
import io
import os
import zipfile

import discord
from discord.ext import commands

from core import engine
from core.helpers import admin_only


class Files(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="files")
    async def files(self, ctx: commands.Context, path: str = "."):
        """List the sandbox tree."""
        if not await admin_only(ctx):
            return
        await ctx.reply(engine.list_tree(path))

    @commands.command(name="get")
    async def get(self, ctx: commands.Context, path: str = ""):
        """Send one file as attachment."""
        if not await admin_only(ctx):
            return
        if not path:
            await ctx.reply("usage: `!get <path>`")
            return
        p = engine.safe_path(path)
        if not p or not os.path.isfile(p):
            await ctx.reply("no such file (sandbox only).")
            return
        if os.path.getsize(p) > 24 * 1024 * 1024:
            await ctx.reply("too big (>24MB).")
            return
        await ctx.send(file=discord.File(p, os.path.basename(p)))

    @commands.command(name="zip")
    async def zip(self, ctx: commands.Context, path: str = ""):
        """Zip a file/folder and send it."""
        if not await admin_only(ctx):
            return
        if not path:
            await ctx.reply("usage: `!zip <path>`")
            return
        p = engine.safe_path(path)
        if not p or not os.path.exists(p):
            await ctx.reply("no such path (sandbox only).")
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            if os.path.isfile(p):
                z.write(p, os.path.basename(p))
            else:
                for root, _, files in os.walk(p):
                    for f in files[:500]:
                        fp = os.path.join(root, f)
                        z.write(fp, os.path.relpath(fp, p))
        buf.seek(0)
        await ctx.send("📦 here:", file=discord.File(buf, "vibe.zip"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Files(bot))

"""Shared helpers for cogs: admin checks, chunked sends."""
import discord
from discord.ext import commands

from config import settings as cfg


def is_admin(ctx_or_member) -> bool:
    m = getattr(ctx_or_member, "author", ctx_or_member)
    if getattr(m.guild_permissions, "administrator", False):
        return True
    return str(getattr(m, "id", "")) in cfg.ADMIN_IDS


async def chunked_send(ch, text: str):
    text = text or "(empty)"
    for i in range(0, len(text), 1900):
        await ch.send(text[i:i + 1900])


async def admin_only(ctx: commands.Context) -> bool:
    if is_admin(ctx):
        return True
    await ctx.reply("admins only, gng.")
    return False

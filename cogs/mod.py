"""Discord server kit (the stuff vibe-bot does): moderation, roles, channels, info.

Admin-only for anything that changes the server. Reads open to everyone.
"""
import datetime
import re

import discord
from discord.ext import commands

from core.helpers import admin_only

WARNS: dict[tuple[int, int], list[str]] = {}


def _parse_dur(s: str) -> datetime.timedelta | None:
    m = re.fullmatch(r"(\d+)(s|m|h|d)?", (s or "").strip().lower())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2) or "m"
    return {"s": datetime.timedelta(seconds=n), "m": datetime.timedelta(minutes=n),
            "h": datetime.timedelta(hours=n), "d": datetime.timedelta(days=n)}[u]


async def _member(ctx: commands.Context, q: str) -> discord.Member | None:
    g = ctx.guild
    if ctx.message.mentions:
        return ctx.message.mentions[0]
    q = q.strip().strip("<@!>")
    if q.isdigit():
        m = g.get_member(int(q))
        if m:
            return m
    ql = q.lower()
    for m in g.members:
        if m.display_name.lower() == ql or m.name.lower() == ql:
            return m
    found = [m for m in g.members if ql in m.display_name.lower() or ql in m.name.lower()]
    return found[0] if len(found) == 1 else None


def _role(g: discord.Guild, q: str) -> discord.Role | None:
    q = q.strip()
    if q.isdigit():
        r = g.get_role(int(q))
        if r:
            return r
    ql = q.lower()
    for r in g.roles:
        if r.name.lower() == ql:
            return r
    found = [r for r in g.roles if ql in r.name.lower()]
    return found[0] if len(found) == 1 else None


class Mod(commands.Cog):
    """Server management. Changing stuff = admins only."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----- moderation -----
    @commands.command(name="purge")
    async def purge(self, ctx: commands.Context, limit: int = 10):
        if not await admin_only(ctx):
            return
        deleted = await ctx.channel.purge(limit=max(1, min(limit, 100)))
        await ctx.send(f"🧹 deleted {len(deleted)}.", delete_after=10)

    @commands.command(name="timeout")
    async def timeout(self, ctx: commands.Context, member: str = "", dur: str = "10m", *, reason: str = "mod"):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        t = _parse_dur(dur)
        if not m or not t:
            await ctx.reply("usage: `!timeout @user 10m [reason]`")
            return
        try:
            await m.timeout(t, reason=f"{ctx.author}: {reason}"[:150])
            await ctx.reply(f"⏱️ {m.display_name} timed out for {dur}.")
        except discord.Forbidden:
            await ctx.reply("no perms (need Moderate Members + higher role).")

    @commands.command(name="untimeout")
    async def untimeout(self, ctx: commands.Context, member: str = ""):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        if not m:
            await ctx.reply("usage: `!untimeout @user`")
            return
        try:
            await m.timeout(None, reason=f"{ctx.author}: untimeout")
            await ctx.reply(f"✅ {m.display_name} released.")
        except discord.Forbidden:
            await ctx.reply("no perms.")

    @commands.command(name="kick")
    async def kick(self, ctx: commands.Context, member: str = "", *, reason: str = "mod"):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        if not m:
            await ctx.reply("usage: `!kick @user [reason]`")
            return
        try:
            await m.kick(reason=f"{ctx.author}: {reason}"[:150])
            await ctx.reply(f"👢 {m.display_name} kicked.")
        except discord.Forbidden:
            await ctx.reply("no perms (need Kick + higher role).")

    @commands.command(name="ban")
    async def ban(self, ctx: commands.Context, member: str = "", *, reason: str = "mod"):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        if not m:
            await ctx.reply("usage: `!ban @user [reason]`")
            return
        try:
            await m.ban(reason=f"{ctx.author}: {reason}"[:150], delete_message_days=0)
            await ctx.reply(f"🔨 {m.display_name} banned.")
        except discord.Forbidden:
            await ctx.reply("no perms (need Ban + higher role).")

    @commands.command(name="unban")
    async def unban(self, ctx: commands.Context, user_id: str = ""):
        if not await admin_only(ctx):
            return
        if not user_id.strip().strip("<@!>").isdigit():
            await ctx.reply("usage: `!unban <user_id>`")
            return
        try:
            await ctx.guild.unban(discord.Object(id=int(user_id.strip().strip("<@!>"))))
            await ctx.reply(f"✅ <@{user_id.strip().strip('<@!>')}> unbanned.")
        except Exception:
            await ctx.reply("unban failed (bad ID or no perms).")

    @commands.command(name="warn")
    async def warn(self, ctx: commands.Context, member: str = "", *, reason: str = "no reason"):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        if not m:
            await ctx.reply("usage: `!warn @user [reason]`")
            return
        WARNS.setdefault((ctx.guild.id, m.id), []).append(reason[:200])
        await ctx.reply(f"⚠️ {m.display_name} warned ({len(WARNS[(ctx.guild.id, m.id)])} total): {reason[:150]}")

    @commands.command(name="warns")
    async def warns(self, ctx: commands.Context, member: str = ""):
        m = await _member(ctx, member) if member else None
        target = m or ctx.author
        lst = WARNS.get((ctx.guild.id, target.id), [])
        await ctx.reply(f"**{target.display_name}** warnings ({len(lst)}):\n" +
                        ("\n".join(f"{i+1}. {w}" for i, w in enumerate(lst[-10:])) or "clean ✨"))

    # ----- nicknames / roles -----
    @commands.command(name="nick")
    async def nick(self, ctx: commands.Context, member: str = "", *, nickname: str = ""):
        if not await admin_only(ctx):
            return
        m = await _member(ctx, member)
        if not m or not nickname:
            await ctx.reply("usage: `!nick @user <new nickname>`")
            return
        try:
            await m.edit(nick=nickname[:32], reason=f"{ctx.author}")
            await ctx.reply(f"✏️ {m.display_name} → `{nickname[:32]}`")
        except discord.Forbidden:
            await ctx.reply("no perms (need Manage Nicknames + higher role).")

    @commands.command(name="role")
    async def role(self, ctx: commands.Context, member: str = "", *, rolename: str = ""):
        """Give a role: !role @user <role>"""
        if not await admin_only(ctx):
            return
        m, r = await _member(ctx, member), _role(ctx.guild, rolename)
        if not m or not r:
            await ctx.reply("usage: `!role @user <role>` (need exact-ish name)")
            return
        try:
            await m.add_roles(r, reason=f"{ctx.author}")
            await ctx.reply(f"🎖️ gave `{r.name}` to {m.display_name}.")
        except discord.Forbidden:
            await ctx.reply("no perms (need Manage Roles + higher role).")

    @commands.command(name="unrole")
    async def unrole(self, ctx: commands.Context, member: str = "", *, rolename: str = ""):
        if not await admin_only(ctx):
            return
        m, r = await _member(ctx, member), _role(ctx.guild, rolename)
        if not m or not r:
            await ctx.reply("usage: `!unrole @user <role>`")
            return
        try:
            await m.remove_roles(r, reason=f"{ctx.author}")
            await ctx.reply(f"➖ removed `{r.name}` from {m.display_name}.")
        except discord.Forbidden:
            await ctx.reply("no perms.")

    @commands.command(name="roles")
    async def roles(self, ctx: commands.Context):
        await ctx.reply("**roles:** " + ", ".join(
            f"`{r.name}`" for r in sorted(ctx.guild.roles, key=lambda x: x.position, reverse=True)
            if r.name != "@everyone")[:1800])

    # ----- channels -----
    @commands.command(name="slowmode")
    async def slowmode(self, ctx: commands.Context, seconds: int = 0):
        if not await admin_only(ctx):
            return
        try:
            await ctx.channel.edit(slowmode_delay=max(0, min(seconds, 21600)), reason=f"{ctx.author}")
            await ctx.reply(f"🐢 slowmode → {max(0, min(seconds, 21600))}s.")
        except discord.Forbidden:
            await ctx.reply("no perms (need Manage Channels).")

    @commands.command(name="lock")
    async def lock(self, ctx: commands.Context):
        if not await admin_only(ctx):
            return
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False,
                                              reason=f"{ctx.author}")
            await ctx.reply("🔒 locked.")
        except discord.Forbidden:
            await ctx.reply("no perms.")

    @commands.command(name="unlock")
    async def unlock(self, ctx: commands.Context):
        if not await admin_only(ctx):
            return
        try:
            await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None,
                                              reason=f"{ctx.author}")
            await ctx.reply("🔓 unlocked.")
        except discord.Forbidden:
            await ctx.reply("no perms.")

    # ----- info (everyone) -----
    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: str = ""):
        m = await _member(ctx, member) if member else ctx.author
        m = m or ctx.author
        await ctx.reply(f"{m.display_name}'s avatar: {m.display_avatar.url}")

    @commands.command(name="whois")
    async def whois(self, ctx: commands.Context, member: str = ""):
        m = await _member(ctx, member) if member else ctx.author
        m = m or ctx.author
        roles = ", ".join(r.name for r in m.roles if r.name != "@everyone") or "none"
        await ctx.reply(f"**{m.display_name}** (`{m.id}`)\n"
                        f"joined: {m.joined_at.strftime('%Y-%m-%d') if m.joined_at else '?'}\n"
                        f"roles: {roles}"[:1500])

    @commands.command(name="server")
    async def server(self, ctx: commands.Context):
        g = ctx.guild
        await ctx.reply(f"**{g.name}** (`{g.id}`)\n"
                        f"👥 {g.member_count} members • #{len(g.text_channels)} text • "
                        f"🔊 {len(g.voice_channels)} voice • 🎖️ {len(g.roles)} roles\n"
                        f"owner: {g.owner} • created: {g.created_at.strftime('%Y-%m-%d')}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Mod(bot))

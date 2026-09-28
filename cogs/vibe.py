"""Passive server life, ported from vibe-bot: welcome/goodbye, autorole,
member counter, first-🎉 giveaway wins, reaction roles add/remove.

All driven by per-server settings (setup via @ping tools like
setup_welcome / setup_autorole / add_reaction_role). No LLM here.
"""
import discord
from discord.ext import commands

from core.vibe import settings as cfg
from core.vibe.tools import _find_role, _find_text_channel, _fmt
from core.vibe.ui import send_v2


async def _update_counter(guild: discord.Guild):
    s = cfg.get_settings(guild.id)
    tmpl = s.get("counter", "")
    if not tmpl:
        return
    label = tmpl.replace("{count}", str(guild.member_count)) if "{count}" in tmpl else f"{tmpl}: {guild.member_count}"
    for vc in guild.voice_channels:
        cur = vc.name
        base = tmpl.replace("{count}", "").strip(": ") if "{count}" in tmpl else tmpl
        if cur.startswith(base[:20]) or cur.startswith("Members"):
            try:
                await vc.edit(name=label[:100], reason="Vibe counter")
            except Exception:
                pass
            return


class VibeLife(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            guild = member.guild
            s = cfg.get_settings(guild.id)
            if s.get("autorole"):
                role = _find_role(guild, s["autorole"])
                if role:
                    try:
                        await member.add_roles(role, reason="Vibe autorole")
                    except Exception:
                        pass
            if not s.get("welcome_enabled"):
                return
            ch = _find_text_channel(guild, s.get("welcome_channel", ""))
            if not ch:
                ch = guild.system_channel
            if not ch:
                return
            msg = _fmt(s.get("welcome_message", "welcome {member}!"), member, guild)
            ping = member.mention if s.get("welcome_ping") else None
            if s.get("welcome_embed", True):
                await send_v2(ch, f"Welcome to {guild.name}! 🎉", msg, "#A78BFA",
                              footer=f"You're member #{guild.member_count}",
                              thumbnail=member.display_avatar.url, content=ping)
            else:
                await ch.send(f"{ping + ' ' if ping else ''}{msg}"[:1900])
        except Exception as e:
            print(f"welcome error: {e}")
        try:
            await _update_counter(member.guild)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            s = cfg.get_settings(member.guild.id)
            if not s.get("goodbye_enabled"):
                return
            ch = _find_text_channel(member.guild, s.get("goodbye_channel", ""))
            if not ch:
                return
            await ch.send(_fmt(s.get("goodbye_message", "{member} left."), member, member.guild)[:1900])
        except Exception:
            pass
        try:
            await _update_counter(member.guild)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
            me_id = self.bot.user.id if self.bot.user else 0
            if payload.user_id == me_id:
                return
            if str(payload.emoji) == "🎉":
                info = cfg.get_giveaway(payload.message_id)
                if info and not info.get("ended") and info.get("mode") == "first" and guild:
                    ch = guild.get_channel(payload.channel_id)
                    try:
                        user = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                    except Exception:
                        user = None
                    if user and not user.bot:
                        cfg.end_giveaway_store(payload.message_id)
                        try:
                            await send_v2(ch, "⚡ Giveaway Winner ⚡",
                                          f"Prize: **{info['prize']}**\nWinner: {user.mention} — fastest 🎉 wins! Congrats!",
                                          "#FFD700")
                        except Exception:
                            await ch.send(f"⚡ **GIVEAWAY WINNER** ⚡\nPrize: **{info['prize']}**\nWinner: {user.mention} — fastest 🎉 wins! Congrats!")
                        return
            if guild:
                rr = cfg.find_rr(payload.message_id, str(payload.emoji))
                if rr and str(rr.get("guild")) == str(guild.id):
                    role = _find_role(guild, rr.get("role", ""))
                    try:
                        member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                    except Exception:
                        member = None
                    if role and member and not member.bot:
                        try:
                            await member.add_roles(role, reason="Vibe reaction role")
                        except Exception:
                            pass
        except Exception as e:
            print(f"giveaway reaction error: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        try:
            guild = self.bot.get_guild(payload.guild_id) if payload.guild_id else None
            if not guild or (self.bot.user and payload.user_id == self.bot.user.id):
                return
            rr = cfg.find_rr(payload.message_id, str(payload.emoji))
            if rr and str(rr.get("guild")) == str(guild.id):
                role = _find_role(guild, rr.get("role", ""))
                try:
                    member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
                except Exception:
                    member = None
                if role and member and not member.bot:
                    try:
                        await member.remove_roles(role, reason="Vibe reaction role removed")
                    except Exception:
                        pass
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(VibeLife(bot))

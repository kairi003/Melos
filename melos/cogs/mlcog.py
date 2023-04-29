#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import deque
from collections import defaultdict
import discord
import asyncio
import re

import gtts.lang
from discord.ext import commands
from typing import Optional, Dict, Set, Deque

import logging
from ..bot import MelosBot
from ..utils.ttss import TTSSource

logger = logging.getLogger(__name__)

RadingChannel = Dict[discord.Guild, Set[discord.TextChannel]]
PlayQueue = Dict[discord.Guild, Deque[TTSSource]]

TTS_LANGS = gtts.lang.tts_langs()


class MelosCog(commands.Cog):
    def __init__(self, bot: MelosBot):
        self.bot = bot
        self.reading_channel: RadingChannel = defaultdict(set)
        self.play_queue: PlayQueue = defaultdict(deque)
        self.tts_source = bot.config.tts_source
        self.member_config = defaultdict(lambda: ['ja', 1.0, 0])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            # Own message
            return
        if message.channel not in self.reading_channel[message.guild]:
            # Not observing channel
            return
        if message.guild.voice_client is None:
            # Not connecting to voice channel
            return
        ctx = await self.bot.get_context(message)
        if ctx.command is not None:
            # It's command
            return
        lang, tempo, key_diff = self.member_config[message.author.id]
        for ttss in self.tts_source.from_message(message, lang, tempo, key_diff):
            self.update_queue(ttss.guild, ttss)

    def update_queue(self, guild: discord.Guild, new_src: Optional[TTSSource] = None):
        voice_client: discord.VoiceClient = guild.voice_client
        play_queue = self.play_queue[guild]
        if new_src is not None:
            play_queue.append(new_src)
        if voice_client is None:
            play_queue.clear()
            return
        if not voice_client.is_playing() and play_queue:
            jtalk = play_queue.popleft()
            voice_client.play(jtalk, after=lambda e: self.update_queue(guild))
            return

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        voice_client = member.guild.voice_client
        if voice_client is None or not isinstance(voice_client.channel, discord.VoiceChannel):
            return
        if voice_client and len(voice_client.channel.members) == 1:
            await voice_client.disconnect(force=True)

    @commands.group(name='ml')
    async def main(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send('To see help, type `!ml help`.')

    @main.command(aliases=['s'])
    async def start(self, ctx: commands.Context):
        if ctx.author.voice is None:
            raise
        if ctx.voice_client is None:
            await ctx.author.voice.channel.connect()
        if ctx.voice_client.channel == ctx.author.voice.channel:
            self.reading_channel[ctx.guild].add(ctx.channel)
            await ctx.send(f'Started', reference=ctx.message)
        else:
            raise

    @main.command(aliases=['c'])
    async def close(self, ctx: commands.Context):
        if ctx.voice_client is not None:
            await ctx.voice_client.disconnect(force=True)
            self.reading_channel[ctx.guild].clear()
            await ctx.send(f'Disconnected', reference=ctx.message)

    @main.command(aliases=['sk'])
    async def skip(self, ctx: commands.Context):
        if ctx.voice_client is None:
            raise
        if ctx.voice_client.is_playing():
            msg = ctx.voice_client.source.message
            ctx.voice_client.stop()
            await ctx.send('Skipped', reference=msg)

    @main.command(aliases=['set', 'st'])
    async def setting(self, ctx: commands.Context, *, arg=''):
        config = self.member_config[ctx.author.id]
        if (n := re.search(r'[a-z]{2}(-[A-Z]{2})?', arg)) and n[0] in TTS_LANGS:
            config[0] = n[0]
        if n := re.search(r'(?<![\d.+-])(\d+\.?\d*|\d*\.\d+)', arg):
            config[1] = float(n[0])
        if n := re.search(r'[+-]\d+', arg):
            config[2] = int(n[0])
        lang, tempo, key_diff = config
        await ctx.send(f'Language: {TTS_LANGS[lang]}\nTempo: x{tempo}\nKey: {key_diff:+}', reference=ctx.message)

    @main.command(aliases=['h'])
    async def help(self, ctx: commands.Context, name=None):
        logger.info('help')
        if name == 'langs':
            await ctx.send('```\n' + '\n'.join(f'{k}: {v}' for k, v in TTS_LANGS.items()) + '\n```')
            return
        if name == 'setting':
            embed = discord.Embed(title="!ml setting [lang][tempo][[+-]key]",
                                  description="Setting user config as lang, tempo or key. The values are extracted from the argument using regular expressions, in no particular order.", color=0xff0000)
            embed.add_field(
                name="lang", value="Country code. `!ml help langs` for details.\nexp: `[a-z]{2}(-[A-Z]{2})?`", inline=False)
            embed.add_field(
                name="tempo", value="A Tempo as float.\nexp: `(?<![\d.+-])(\d+\.?\d*|\d*\.\d+)`", inline=False)
            embed.add_field(
                name="[+-]key", value="A Key as int.\nprefixed `:`.\nexp: `[+-]\d+`", inline=False)
            embed.add_field(
                name="Example", value="`!ml setting en .5 +1`\n=> English, Tempo x0.5, Key +1\n`!ml setting -5ja10`\n=> Japanese, Tempo x10.0, Key -5", inline=False)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title="Melos's Help", description="I'm Melos and talk your text.", color=0xff0000)
        embed.add_field(
            name="!ml start(s)", value="Connect to your voice channel and add your text channel to the reading set.", inline=False)
        embed.add_field(
            name="!ml close(c)", value="Disconnect from my voice channel and clear my reading set.", inline=False)
        embed.add_field(name="!ml skip(sk)",
                        value="Skip my talking.", inline=False)
        embed.add_field(name="!ml setting(set,st) [lang][tempo][[+-]key]",
                        value="Setting user config as lang, tempo or key.\n`!ml help setting` for details.", inline=False)
        embed.add_field(name="!ml help(h)", value="Show help.", inline=False)
        embed.add_field(name="!ml reload",
                        value="[Owner Only] Reload extensions.", inline=False)
        embed.add_field(name="Modifier Prefix", value="To temporarily reflect the setting, prefix the text with `\\xx1.0+1 `, a backslash, a country code, a tempo, a pitch, and a space. There will be no space between the country code and the tempo. (e.g. `\\en0.5+6 Hello, World!`)\nLanguages List: `!ml help langs`", inline=False)
        await ctx.send(embed=embed)

    @main.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context):
        await self.bot.reload()


async def setup(bot: MelosBot):
    await bot.add_cog(MelosCog(bot))


async def teardown(bot: MelosBot):
    await asyncio.gather(*(client.disconnect(force=True) for client in bot.voice_clients))
    await bot.remove_cog('MelosCog')

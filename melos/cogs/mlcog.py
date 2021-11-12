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
        self.member_config = defaultdict(lambda :['ja',1.0])

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
        lang, tempo = self.member_config[message.author.id]
        for ttss in self.tts_source.from_message(message, lang, tempo):
            self.update_queue(ttss.guild, ttss)

    def update_queue(self, guild:discord.guild, new_src:Optional[TTSSource]=None):
        voice_client: discord.VoiceClient = guild.voice_client
        play_queue = self.play_queue[guild]
        if new_src is not None:
            play_queue.append(new_src)
        if voice_client is None:
            play_queue.clear()
            return
        if not voice_client.is_playing() and play_queue:
            jtalk = play_queue.popleft()
            voice_client.play(jtalk, after=lambda e:self.update_queue(guild))
            return

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        voice_client = member.guild.voice_client
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
        if (m := re.search(r'[a-zA-Z-]+', arg)) and (lang := m[0]) in TTS_LANGS:
            config[0] = lang
        if (m := re.search(r'[\d.]+', arg)):
            try:
                tempo = min(max(0.5, float(m[0])), 100)
                config[1] = tempo
            except ValueError:
                pass
        lang, tempo = config
        await ctx.send(f'lang: {TTS_LANGS[lang]}\ntempo: {tempo}', reference=ctx.message)
    
    @main.command(aliases=['h'])
    async def help(self, ctx: commands.Context, name=None):
        logger.info('help')
        if name == 'langs':
            await ctx.send('```\n' + '\n'.join(f'{k}: {v}' for k,v in TTS_LANGS.items()) + '\n```')
            return
        embed=discord.Embed(title="Melos's Help", description="I'm Melos and talk your text.", color=0xff0000)
        embed.add_field(name="!ml start(s)", value="Connect to your voice channel and add your text channel to the reading set.", inline=False)
        embed.add_field(name="!ml close(c)", value="Disconnect from my voice channel and clear my reading set.", inline=False)
        embed.add_field(name="!ml skip(sk)", value="Skip my talking.", inline=False)
        embed.add_field(name="!ml setting(set,st) [lang] [tempo]", value="Setting user config. `lang` is a country code and `tempo` is in between 0.5-100", inline=False)
        embed.add_field(name="!ml help(h)", value="Show help.", inline=False)
        embed.add_field(name="!ml reload", value="[Owner Only] Reload extensions.", inline=False)
        embed.add_field(name="Modifier Prefix", value="To temporarily reflect the setting, prefix the text with `\\xx1.0 `, a backslash, a country code, a tempo, and a space. There will be no space between the country code and the tempo. (e.g. `\\en0.5 Hello, World!`)\nLanguages List: `!ml help langs`", inline=False)
        await ctx.send(embed=embed)
    
    @main.command()
    @commands.is_owner()
    async def reload(self, ctx: commands.Context):
        self.bot.reload()
        
def setup(bot: MelosBot):
    bot.add_cog(MelosCog(bot))

def teardown(bot: MelosBot):
    loop = asyncio.get_event_loop()
    loop.run_until_complete((asyncio.gather(*(client.disconnect(force=True) for client in bot.voice_clients))))    
    bot.remove_cog('MelosCog')

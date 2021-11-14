#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import os
import re
from threading import Thread
from subprocess import Popen, PIPE
from typing import Iterator
import discord
import gtts.lang
from gtts import gTTS
from abc import ABCMeta, abstractclassmethod

TTS_SOURCE_REPR_MAX = 20


class TTSSource(discord.PCMVolumeTransformer, metaclass=ABCMeta):
    MAX_TEXT_PER_VOICE = 2000
    DEFAULT_TEMPO = 1.0
    DEFAULT_BITRATE = 24000

    def __init__(self, original: discord.AudioSource, text: str, message: discord.Message, volume: float = 1.0):
        super().__init__(original, volume)
        self.text: str = text
        self.message: discord.Message = message
        self.guild: discord.Guild = message.guild

    def __repr__(self):
        if len(self.text) < TTS_SOURCE_REPR_MAX:
            return self.text
        return self.text[:TTS_SOURCE_REPR_MAX] + '...'
    
    @classmethod
    def audio_filter(cls, tempo, key_diff):
        mod_tempo = tempo
        a_filters = []
        if key_diff != 0:
            pitch_rate = 2**(key_diff/12)
            mod_tempo /= pitch_rate
            a_filters.append(f'asetrate={cls.DEFAULT_BITRATE * pitch_rate}')
        while mod_tempo > 100:
            a_filters.append('atempo=100')
            mod_tempo /= 100
        while mod_tempo < 0.5:
            a_filters.append('atempo=0.5')
            mod_tempo *= 2
        if not math.isclose(mod_tempo, 1):
            a_filters.append(f'atempo={mod_tempo}')
        return ['-af', ','.join(a_filters)]

    @classmethod
    @abstractclassmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja', tempo=1, key_diff=0) -> 'TTSSource':
        pass

    @classmethod
    def from_message(cls, message: discord.Message, lang='ja', tempo=1, key_diff=0) -> Iterator['TTSSource']:
        content = cls.message_ruby(message).strip()
        if m := re.match(r'\\([a-zA-Z\d.*+-]+) (.+)', content, re.DOTALL):
            prefix = m[1]
            content = m[2]
            if n := re.search(r'[a-z]{2}(-[A-Z]{2})?', prefix):
                lang = n[0]
            if n := re.search(r'(?<![\d.+-])(\d+\.?\d*|\d*\.\d+)', prefix):
                tempo *= float(n[0])
            if n:= re.search(r'[+-]\d+', prefix):
                key_diff += int(n[0])
        if not content:
            return
        x = cls.MAX_TEXT_PER_VOICE
        for i in range(math.ceil(len(content)/x)):
            yield cls.from_text(content[i*x:(i+1)*x], message, lang, tempo, key_diff)

    @staticmethod
    def message_ruby(message: discord.Message):
        raw_content = message.content

        def mention_repl(m):
            try:
                type = m[1]
                id = int(m[2])
                guild: discord.Guild = message.guild
                if type == '@':
                    user = guild.get_member(id)
                    return user.name
                elif type == '@!':
                    user = guild.get_member(id)
                    return user.nick or user.name
                elif type == '#':
                    channel = guild.get_channel(id)
                    return channel.name
                elif type == '@&':
                    role = guild.get_role(id)
                    return role.name
            except Exception as e:
                return 'メンション'

        content = re.sub(r'<([@#][!&]?)(\d+)>', mention_repl, raw_content)
        content = re.sub(r'<a?:(\w+):\d+>', r'\1', content)
        return content


class gTTSSource(TTSSource):
    MAX_TEXT_PER_VOICE = 2000
    DEFAULT_TEMPO = 1.4
    DEFAULT_BITRATE = 24000
    TTS_LANGS = gtts.lang.tts_langs()

    @classmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja', tempo=1, key_diff=0):
        if lang not in cls.TTS_LANGS:
            lang = 'ja'
        ffmpeg_options = ['-loglevel', 'quiet'] + cls.audio_filter(tempo, key_diff)
        r, w = os.pipe()

        def _write_to_stream():
            with open(w, 'wb') as f:
                gtts = gTTS(text=text, lang=lang, lang_check=False)
                gtts.write_to_fp(f)

        Thread(target=_write_to_stream).start()
        read_stream = open(r, 'rb')
        original = discord.FFmpegPCMAudio(
            read_stream, pipe=True, options=' '.join(ffmpeg_options))
        return cls(original, text, message)


class JTalkSource(TTSSource):
    MAX_TEXT_PER_VOICE = 500
    DEFAULT_TEMPO = 1.0
    DEFAULT_BITRATE = 24000

    @classmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja', tempo=1, key_diff=0):
        program = 'open_jtalk'
        args = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic',
                '-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice',
                '-ow', '/dev/stdout']
        ffmpeg_options = ['-loglevel', 'quiet'] + cls.audio_filter(tempo, key_diff)
        proc = Popen([program, *args], stdin=PIPE, stdout=PIPE)

        def _write_to_stream():
            try:
                proc.stdin.write(text.encode())
            finally:
                proc.stdin.close()

        Thread(target=_write_to_stream).start()
        original = discord.FFmpegPCMAudio(
            proc.stdout, pipe=True, options=' '.join(ffmpeg_options))
        return cls(original, text, message)


def setup(bot):
    pass


def teardown(bot):
    pass

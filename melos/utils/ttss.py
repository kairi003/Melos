#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from threading import Thread
from subprocess import Popen, PIPE
from typing import Iterator
import discord
from gtts import gTTS
from abc import ABCMeta, abstractclassmethod

TTS_SOURCE_REPR_MAX = 20


class TTSSource(discord.PCMVolumeTransformer, metaclass=ABCMeta):
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
    @abstractclassmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja') -> 'TTSSource':
        pass

    @classmethod
    def from_message(cls, message: discord.Message) -> Iterator['TTSSource']:
        content = cls.message_ruby(message).strip()
        lang = 'ja'
        if re.match(r'\\[a-z]{2} ', content):
            lang = content[1:3]
            content = content[4:]
        if not content:
            return
        yield cls.from_text(content, message, lang)

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
    @classmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja'):
        ffmpeg_options = ['-loglevel', 'quiet', '-af', 'atempo=1.5']
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
    @classmethod
    def from_text(cls, text: str, message: discord.Message, lang='ja'):
        program = 'open_jtalk'
        args = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic',
                '-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice',
                '-ow', '/dev/stdout']
        ffmpeg_options = ['-loglevel', 'quiet']
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

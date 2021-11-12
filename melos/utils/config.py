#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import List
from ..utils.ttss import TTSSource, gTTSSource, JTalkSource

TTS_SOURCE = {
    'gtts': gTTSSource,
    'jtalk': JTalkSource
}

class Config:
    def __init__(self, config_data):
        self.command_prefix: str = config_data['command_prefix']
        self.description: str = config_data['description']
        self.token: str = config_data['token']
        self.tts_source: TTSSource  = TTS_SOURCE[config_data['ttss']]
        self.extensions: List[str] = config_data['extensions']
    
    @classmethod
    def parse(cls, filename):
        with open(filename, encoding='utf-8') as f:
            config_data = json.load(f)
            return cls(config_data)

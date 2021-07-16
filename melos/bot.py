#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
from melos.utils.config import Config

logger = logging.getLogger(__name__)
 
class MelosBot(commands.Bot):
    def __init__(self):
        self.config = Config.parse('config.json')
        intents: discord.Intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix=self.config.command_prefix,
            description=self.config.description,
            intents=intents
        )
        self.remove_command('help')
        for ext in self.config.extensions:
            self.load_extension(ext)
    
    def reload(self):
        self.config = Config.parse('config.json')
        self.command_prefix = self.config.command_prefix
        self.description = self.config.description
        for ext in self.config.extensions:
            self.reload_extension(ext)
        logger.info('Reloaded')
    
    def run(self):
        super().run(self.config.token)

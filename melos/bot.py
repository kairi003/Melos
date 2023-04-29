#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
from .utils.config import Config

logger = logging.getLogger(__name__)

class MelosBot(commands.Bot):
    def __init__(self, config_file):
        self.config = Config.parse(config_file)
        intents: discord.Intents = discord.Intents.all()
        super().__init__(
            command_prefix=self.config.command_prefix,
            description=self.config.description,
            intents=intents
        )
        self.remove_command('help')
    
    async def setup(self):
        for ext in self.config.extensions:
            await self.load_extension(ext, package=__spec__.parent)

    async def reload(self):
        self.config = Config.parse('config.json')
        self.command_prefix = self.config.command_prefix
        self.description = self.config.description
        for ext in self.config.extensions:
            self.reload_extension(ext, package=__spec__.parent)
        logger.info('Reloaded')
    
    async def run(self):
        await self.setup()
        await self.start(self.config.token)

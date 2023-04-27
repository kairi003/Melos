#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from logging.config import fileConfig
from melos import MelosBot

if __name__ == '__main__':
    fileConfig('logging.ini')
    bot = MelosBot('config.json')
    bot.run()

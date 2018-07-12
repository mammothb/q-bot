#!/usr/bin/python3
import logging

from qbot import config
from qbot.bot import QBot

# Load plugins by importing them
from qbot.plugins.quote import Quote
from qbot.plugins.search import Search
from qbot.plugins.streamers import Streamers

logging.basicConfig(level=logging.INFO)

BOT = QBot(shard_id=int(config.SHARD), shard_count=int(config.SHARD_COUNT))
BOT.run(config.TOKEN)

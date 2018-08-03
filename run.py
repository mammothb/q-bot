##!/usr/bin/python3
import logging

from qbot import config
from qbot.bot import QBot

# Load plugins by importing them
from qbot.plugins.help import Help
from qbot.plugins.moderator import Moderator
from qbot.plugins.quote import Quote
from qbot.plugins.search import Search
from qbot.plugins.streamers import Streamers
from qbot.plugins.youtubers import Youtubers

logging.basicConfig(level=logging.INFO)

BOT = QBot(shard_id=int(config.SHARD), shard_count=int(config.SHARD_COUNT))
BOT.run(config.TOKEN)

from collections import defaultdict

import asyncio
import logging
import re

import aiohttp
import aiosqlite

from qbot.config import GOOGLE_API_KEY
from qbot.const import PREFIX
from qbot.decorators import bg_task, command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")
NOT_FOUND = "I didn't find anything 😢..."

class Platform:
    def __init__(self, name):
        self.name = name

    def collector(self, collector_func):
        self.collector = collector_func

class Streamer:
    def __init__(self, name, display_name, link, stream_id):
        self.name = name
        self.display_name = display_name
        self.link = link
        self.stream_id = stream_id

YOUTUBE_PLATFORM = Platform("youtube")

@YOUTUBE_PLATFORM.collector
async def youtube_collector(streamers):
    streamers = list(map(lambda s: s.replace(" ", "_"), streamers))
    live_streamers = []
    for i in range(0, len(streamers), 100):
        chunk = streamers[i : i + 100]
        url = ("https://api.twitch.tv/kraken/streams"
               "?channel={}&limit=100".format(",".join(chunk)))
        async with aiohttp.ClientSession() as session:
            params = {"client_id": TWITCH_CLIENT_ID}
            async with session.get(url, params=params) as resp:
                result = await resp.json()
                for stream in result["streams"]:
                    streamer = Streamer(
                        stream["channel"]["name"],
                        stream["channel"]["display_name"],
                        stream["channel"]["url"],
                        str(stream["_id"])
                    )
                    live_streamers.append(streamer)
    return live_streamers

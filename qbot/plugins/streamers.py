from collections import defaultdict

import logging
import json
import re

import aiohttp
from discord.channel import TextChannel

from qbot.config import TWITCH_CLIENT_ID
from qbot.decorators import bg_task
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")

class Platform:
    def __init__(self, name, db_name=None):
        self.name = name
        self.db_name = db_name or name

    def collector(self, collector_func):
        self.collector = collector_func

class Streamer:
    def __init__(self, name, display_name, link, stream_id):
        self.name = name
        self.display_name = display_name
        self.link = link
        self.stream_id = stream_id

# Twitch
TWITCH_PLATFORM = Platform("twitch", db_name="streamers")

@TWITCH_PLATFORM.collector
async def twitch_collector(streamers):
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

class Streamers(Plugin):
    """Plugin logic"""
    fancy_name = "Streamers"

    platforms = [TWITCH_PLATFORM]

    async def get_guild_list(self):
        return self.client.guilds

    async def get_live_streamers_by_guilds(self):
        guilds = await self.get_guild_list()
        data = defaultdict(list)
        for platform in self.platforms:
            streamers = []
            temp_data = {}
            for guild in guilds:
                guild_streamers = ["lilypichu", "pokimane", "dakotaz"]
                temp_data[guild] = guild_streamers
                streamers += guild_streamers
            streamers = set(streamers)
            if not streamers:
                continue

            streamers = set(map(lambda s: re.sub("[^0-9a-zA-Z_]+", "", s),
                                streamers))
            try:
                live_streamers = await platform.collector(streamers)
                for guild, guild_streamers in temp_data.items():
                    for streamer in live_streamers:
                        if streamer.name in guild_streamers:
                            data[guild.id].append(streamer)
                # remove streamer from shelves if they are offline
                streamer_names = [streamer.name for streamer in live_streamers]
                for guild in guilds:
                    storage = self.get_storage(guild)
                    for streamer in streamers:
                        if streamer not in streamer_names:
                            try:
                                del storage[streamer]
                                LOG.info("Streamer %s went offline", streamer)
                            except KeyError:
                                pass
                    storage.close()

            except Exception as e:
                LOG.info("Cannot gather live streamers from %s", platform.name)
                LOG.info("With streamers: %s", ",".join(streamers))
                LOG.info(e)
        return data

    @bg_task(30)
    async def streamer_check(self):
        data = await self.get_live_streamers_by_guilds()
        for guild_id, live_streamers in data.items():
            guild = self.client.get_guild(guild_id)
            if not guild:
                continue

            storage = self.get_storage(guild)
            for channel_id in guild._channels:
                if (isinstance(guild._channels[channel_id], TextChannel) and
                        guild._channels[channel_id].name == "general"):
                    announcement_channel = self.client.get_channel(channel_id)
            announcement_message = "{streamer} is now live on {link}!"
            for streamer in live_streamers:
                streamer_ids = [storage[key] for key in storage.keys()]
                checked = streamer.stream_id in streamer_ids
                if checked:
                    continue
                try:
                    await self.client.send_message(
                        announcement_channel.id,
                        announcement_message.replace(
                            "{streamer}", streamer.name
                        ).replace(
                            "{link}", streamer.link
                        )
                    )
                    storage[streamer.name] = streamer.stream_id
                except Exception as e:
                    LOG.info(e)
            storage.close()

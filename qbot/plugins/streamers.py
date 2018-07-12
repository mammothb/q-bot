from collections import defaultdict

import asyncio
import logging
import json
import re

import aiohttp
import aiosqlite
from discord.channel import TextChannel

from qbot.config import TWITCH_CLIENT_ID
from qbot.const import PREFIX
from qbot.decorators import bg_task, command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")
NOT_FOUND = "I didn't find anything 😢..."

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

    def __init__(self, client):
        super().__init__(client)
        self._ready = asyncio.Event(loop=self.client.loop)

    async def wait_until_ready(self):
        await self._ready.wait()

    async def on_ready(self):
        guilds = await self.get_guild_list()
        for guild in guilds:
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS streamers_{} (".format(
                        guild.id) +
                    "name TEXT PRIMARY KEY,"
                    "id TEXT,"
                    "online INTEGER NOT NULL);")
                await conn.commit()
        self._ready.set()

    async def get_guild_list(self):
        return self.client.guilds

    async def get_live_streamers_by_guilds(self):
        guilds = await self.get_guild_list()
        data = defaultdict(list)
        for platform in self.platforms:
            streamers = []
            temp_data = {}
            for guild in guilds:
                async with aiosqlite.connect(self.db.path) as conn:
                    cursor = await conn.execute(
                        "SELECT name FROM streamers_{}".format(guild.id))
                    guild_streamers = await cursor.fetchall()
                    await cursor.close()
                # cursor fetch all returns the entries as tuples
                guild_streamers = [s[0] for s in guild_streamers]
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
                streamer_names = [streamer.name for streamer in live_streamers]
                for guild in guilds:
                    for streamer in streamers:
                        if streamer in streamer_names:
                            continue
                        # set offline streamer
                        async with aiosqlite.connect(self.db.path) as conn:
                            await conn.execute(
                                "UPDATE streamers_{} SET online = 0 WHERE "
                                "name='{}'".format(guild.id, streamer))
                            await conn.commit()
                        LOG.info("Streamer %s went offline", streamer)

            except Exception as e:
                LOG.info("Cannot gather live streamers from %s", platform.name)
                LOG.info("With streamers: %s", ",".join(streamers))
                LOG.info(e)
        return data

    @command(db_name="streamer",
             pattern="^" + PREFIX + "streamer (.*)",
             db_check=True,
             usage=PREFIX + "streamer streamer_name")
    async def streamer(self, message, args):
        cmd = args[0].split(" ")
        if len(cmd) != 2:
            response = "Nont enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        op = cmd[0]
        streamer_name = cmd[1]
        if op == "add":
            url = ("https://api.twitch.tv/kraken/streams"
                   "?channel={}&limit=1".format(streamer_name))
            async with aiohttp.ClientSession() as session:
                params = {"client_id": TWITCH_CLIENT_ID}
                async with session.get(url, params=params) as resp:
                    result = await resp.json()
                    if not result["streams"]:
                        response = NOT_FOUND
                    for stream in result["streams"]:
                        async with aiosqlite.connect(self.db.path) as conn:
                            await conn.execute(
                                "INSERT OR IGNORE INTO streamers_{} "
                                "(name,id,online) VALUES(?,?,?)".format(
                                    message.guild.id),
                                (streamer_name, str(stream["_id"]), 0))
                            await conn.commit()
                            response = "Added streamer {}!".format(
                                streamer_name)
        elif op == "rm":
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "DELETE FROM streamers_{} WHERE name=?".format(
                        message.guild.id), (streamer_name,))
                await conn.commit()
                response = "Removed streamer {}!".format(
                    streamer_name)
        else:
            response = "Unknown command, use 'add' or 'rm'."

        await self.client.send_message(message.channel.id, response)

    @bg_task(30)
    async def streamer_check(self):
        data = await self.get_live_streamers_by_guilds()
        for guild_id, live_streamers in data.items():
            guild = self.client.get_guild(guild_id)
            if not guild:
                continue

            for channel_id in guild._channels:
                if (isinstance(guild._channels[channel_id], TextChannel) and
                        guild._channels[channel_id].name == "bot-test"):
                    announcement_channel = self.client.get_channel(channel_id)
            announcement_message = "{streamer} is now live on {link} !"
            async with aiosqlite.connect(self.db.path) as conn:
                cursor = await conn.execute(
                    "SELECT id FROM streamers_{} WHERE online = 1".format(
                        guild.id))
                streamer_ids = await cursor.fetchall()
                await cursor.close()
            streamer_ids = [id[0] for id in streamer_ids
                            if id[0] != "" and id[0] is not None]
            for streamer in live_streamers:
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
                    async with aiosqlite.connect(self.db.path) as conn:
                        tbl_name = "streamers_{}".format(guild.id)
                        await conn.execute(
                            "INSERT OR REPLACE INTO {} (name,id,online) "
                            "VALUES(COALESCE((SELECT name FROM {} WHERE "
                            "name = '{}'), '{}'),?,?)".format(
                                tbl_name, tbl_name, streamer.name,
                                streamer.name), (streamer.stream_id, 1))
                        await conn.commit()
                except Exception as e:
                    LOG.info(e)

from collections import defaultdict

import asyncio
import logging
import re

import aiohttp
import aiosqlite

from qbot.config import TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
from qbot.const import PREFIX
from qbot.decorators import bg_task, command
from qbot.plugin import Plugin
from qbot.utility import replace_multiple

LOG = logging.getLogger("discord")
NOT_FOUND = "I didn't find anything 😢..."

class Platform:  # pylint: disable=R0903
    def __init__(self, name):
        self.name = name
        self.collector = None

    def set_collector(self, collector_func):
        self.collector = collector_func

class Streamer:  # pylint: disable=R0903
    def __init__(self, user_name, user_id):
        self.user_name = user_name
        self.user_id = user_id
        self.link = f"https://www.twitch.tv/{user_name}"

# Twitch
TWITCH_PLATFORM = Platform("twitch")

TWITCH_GET_STREAM = ("https://api.twitch.tv/helix/streams?user_id=$USER_ID$&"
                     "first=100")
TWITCH_GET_USER = "https://api.twitch.tv/helix/users"
TWITCH_AUTHORIZE = ("https://id.twitch.tv/oauth2/token"
                    f"?client_id={TWITCH_CLIENT_ID}"
                    f"&client_secret={TWITCH_CLIENT_SECRET}"
                    "&grant_type=client_credentials")
TWITCH_VALIDATE = "https://id.twitch.tv/oauth2/validate"
TWITCH_ACCESS_TOKEN = ""

def set_twitch_access_token(token):
    global TWITCH_ACCESS_TOKEN
    TWITCH_ACCESS_TOKEN = token
    LOG.info("Updated twitch access token")

@TWITCH_PLATFORM.set_collector
async def twitch_collector(streamers):
    streamers = list(map(lambda s: s.replace(" ", "_"), streamers))
    live_streamers = []
    for i in range(0, len(streamers), 100):
        user_id = "&user_id=".join(streamers[i : i + 100])
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {TWITCH_ACCESS_TOKEN}",
                       "Client-ID": TWITCH_CLIENT_ID}
            async with session.get(TWITCH_GET_STREAM.replace(
                "$USER_ID$", user_id), headers=headers) as stream_resp:
                stream_result = await stream_resp.json()
                if stream_result.get("status") == 401:
                    async with session.post(TWITCH_AUTHORIZE) as auth_resp:
                        auth_result = await auth_resp.json()
                        set_twitch_access_token(auth_result["access_token"])
                for stream in stream_result["data"]:
                    params = {"id": stream["user_id"]}
                    async with session.get(TWITCH_GET_USER, headers=headers,
                                           params=params) as user_resp:
                        user_result = (await user_resp.json())["data"][0]
                        streamer = Streamer(user_result["login"],
                                            stream["user_id"])
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
                    f"CREATE TABLE IF NOT EXISTS streamers_{guild.id} ("
                    "name TEXT NOT NULL,"
                    "user_id TEXT PRIMARY KEY,"
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
                        f"SELECT user_id FROM streamers_{guild.id}")
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
                        if streamer.user_id in guild_streamers:
                            data[guild.id].append(streamer)
                streamer_ids = [streamer.user_id
                                for streamer in live_streamers]
                for guild in guilds:
                    for streamer in streamers:
                        if streamer in streamer_ids:
                            continue
                        # set offline streamer
                        async with aiosqlite.connect(self.db.path) as conn:
                            await conn.execute(
                                f"UPDATE streamers_{guild.id} SET online=0 "
                                "WHERE user_id=?", (streamer,))
                            await conn.commit()

            except Exception as exception:  # pylint: disable=W0703
                LOG.info("Cannot gather live streamers from %s", platform.name)
                LOG.info("With streamers: %s", ",".join(streamers))
                LOG.exception(exception)
        return data

    @command(pattern="^" + PREFIX + "streamer (.*)",
             description="Add or remove Twitch streamer from notification",
             usage=PREFIX + "streamer (add/rm) streamer_name")
    async def streamer(self, message, args):
        cmd = args[0].split(" ")
        if len(cmd) < 2:
            response = "Not enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        operation = cmd[0]
        streamer_name = cmd[1]
        guild_id = message.guild.id
        if operation == "add":
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {TWITCH_ACCESS_TOKEN}",
                           "Client-ID": TWITCH_CLIENT_ID}
                params = {"login": streamer_name}
                # Check if channel exist
                async with session.get(TWITCH_GET_USER, headers=headers,
                                       params=params) as resp:
                    data = await resp.json()
                if not data["data"]:
                    response = NOT_FOUND
                else:
                    # write entry using channel name instead of display name
                    async with aiosqlite.connect(self.db.path) as conn:
                        await conn.execute(
                            f"INSERT OR IGNORE INTO streamers_{guild_id} "
                            "(name,user_id,online) VALUES(?,?,?)",
                            (data["data"][0]["login"],
                             data["data"][0]["id"], 0))
                        await conn.commit()
                        response = f"Added streamer {streamer_name}!"
        elif operation == "rm":
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(f"DELETE FROM streamers_{guild_id} "
                                   "WHERE name=?", (streamer_name,))
                await conn.commit()
                response = f"Removed streamer {streamer_name}!"
        else:
            response = "Unknown command, use 'add' or 'rm'."

        await self.client.send_message(message.channel.id, response)

    @command(pattern="^" + PREFIX + "streamer_setup (.*)",
             description="Add or remove Twitch streamer from notification",
             usage=PREFIX + "streamer_setup msg")
    async def streamer_setup(self, message, args):
        args = args[0].split(" ", 1)
        if len(args) != 2:
            response = "Not enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        streamers_channel = int(args[0][2:-1])
        streamers_text = args[1]
        try:
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "UPDATE guilds SET streamers_channel=?, "
                    "streamers_text=? WHERE id=?",
                    (streamers_channel, streamers_text, message.guild.id))
                await conn.commit()
                response = "Update Streamers annoucement text and channel!"
        except Exception as exception:  # pylint: disable=W0703
            LOG.exception(exception)
            response = ("Couldn't update Streamers annoucement text and "
                        "channel")
        await self.client.send_message(message.channel.id, response)

    @bg_task(30)
    async def streamer_check(self):
        data = await self.get_live_streamers_by_guilds()
        for guild_id, live_streamers in data.items():
            guild = self.client.get_guild(guild_id)
            if not guild:
                continue
            async with aiosqlite.connect(self.db.path) as conn:
                cursor = await conn.execute(
                    "SELECT streamers_channel, streamers_text FROM guilds "
                    "WHERE id=?", (guild.id,))
                streamers_channel, streamers_text = await cursor.fetchone()
                await cursor.close()
            async with aiosqlite.connect(self.db.path) as conn:
                cursor = await conn.execute(
                    f"SELECT user_id FROM streamers_{guild.id} "
                    "WHERE online=1")
                streamer_ids = await cursor.fetchall()
                await cursor.close()
            streamer_ids = [s[0] for s in streamer_ids]
            for streamer in live_streamers:
                checked = streamer.user_id in streamer_ids
                if checked:
                    continue
                try:
                    rep = {
                        "{streamer}": streamer.user_name,
                        "{link}": streamer.link
                    }
                    await self.client.send_message(
                        streamers_channel,
                        replace_multiple(rep, streamers_text)
                    )
                    async with aiosqlite.connect(self.db.path) as conn:
                        await conn.execute(
                            f"UPDATE streamers_{guild.id} SET online=1 "
                            "WHERE user_id=?", (streamer.user_id,))
                        await conn.commit()
                except Exception as exception:  # pylint: disable=W0703
                    LOG.exception(exception)

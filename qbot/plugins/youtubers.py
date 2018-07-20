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

class Video:
    def __init__(self, channel_name, channel_id, video_id):
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.video_id = video_id

YOUTUBE_PLATFORM = Platform("youtube")

@YOUTUBE_PLATFORM.collector
async def youtube_collector(youtubers):
    youtubers = list(map(lambda s: s.replace(" ", "_"), youtubers))
    latest_videos = []
    for channel_id in youtubers:
        url = "https://www.googleapis.com/youtube/v3/search"
        async with aiohttp.ClientSession() as session:
            params = {
                "key": GOOGLE_API_KEY,
                "part": "snippet",
                "channelId": channel_id,
                "maxResults": "1",
                "order": "date"
                }
            async with session.get(url, params=params) as resp:
                result = await resp.json()
                video = Video(
                    result["items"][0]["snippet"]["channelTitle"],
                    channel_id,
                    result["items"][0]["id"]["videoId"]
                )
                latest_videos.append(video)
    return latest_videos

class Youtubers(Plugin):
    """Plugin logic"""
    fancy_name = "YouTubers"

    platforms = [YOUTUBE_PLATFORM]

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
                    "CREATE TABLE IF NOT EXISTS youtubers_{} (".format(
                        guild.id) +
                    "id TEXT PRIMARY KEY,"
                    "latest INTEGER NOT NULL);")
                await conn.commit()
        self._ready.set()

    async def get_guild_list(self):
        return self.client.guilds

    async def get_youtubers_by_guilds(self):
        guilds = await self.get_guild_list()
        data = defaultdict(list)
        for platform in self.platforms:
            youtubers = []
            temp_data = {}
            for guild in guilds:
                async with aiosqlite.connect(self.db.path) as conn:
                    cursor = await conn.execute(
                        "SELECT id FROM youtubers_{}".format(guild.id))
                    guild_youtubers = await cursor.fetchall()
                    await cursor.close()
                # cursor fetch all returns the entries as tuples
                guild_youtubers = [s[0] for s in guild_youtubers]
                temp_data[guild] = guild_youtubers
                youtubers += guild_youtubers
            youtubers = set(youtubers)
            if not youtubers:
                continue

            youtubers = set(map(lambda s: re.sub("[^0-9a-zA-Z_]+", "", s),
                                youtubers))
            try:
                latest_videos = await platform.collector(youtubers)
                for guild, guild_youtubers in temp_data.items():
                    for video in latest_videos:
                        if video.channel_id in guild_youtubers:
                            data[guild.id].append(video)

            except Exception as e:
                LOG.info("Cannot gather youtubers from %s", platform.name)
                LOG.info("With youtubers: %s", ",".join(youtubers))
                LOG.info(e)
        return data

    @command(pattern="^" + PREFIX + "youtuber (.*)",
             description="Add or remove YouTube channel from notification",
             usage=PREFIX + "youtuber add/rm channel_id")
    async def youtuber(self, message, args):
        cmd = args[0].split(" ")
        if len(cmd) != 2:
            response = "Nnt enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        op = cmd[0]
        channel_id = cmd[1]
        if op == "add":
            url = "https://www.googleapis.com/youtube/v3/channels"
            async with aiohttp.ClientSession() as session:
                params = {"key": GOOGLE_API_KEY, "part": "id", "id": channel_id}
                # Check if channel exist
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                if data["pageInfo"]["totalResults"] == 0:
                    response = NOT_FOUND
                else:
                    url = "https://www.googleapis.com/youtube/v3/search"
                    params = {
                        "key": GOOGLE_API_KEY,
                        "part": "snippet",
                        "channelId": channel_id,
                        "maxResults": "1",
                        "order": "date"
                        }
                    # check for latest video
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                    if data["pageInfo"]["totalResults"] == 0:
                        response = NOT_FOUND
                    else:
                        # write entry using channel name instead of display name
                        async with aiosqlite.connect(self.db.path) as conn:
                            await conn.execute(
                                "INSERT OR IGNORE INTO youtubers_{} "
                                "(id,latest) VALUES(?,?)".format(
                                    message.guild.id),
                                (channel_id, data["items"][0]["id"]["videoId"]))
                            await conn.commit()
                            response = "Added channel {}!".format(channel_id)
        elif op == "rm":
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "DELETE FROM youtubers_{} WHERE id=?".format(
                        message.guild.id), (channel_id,))
                await conn.commit()
                response = "Removed channel {}!".format(channel_id)
        else:
            response = "Unknown command, use 'add' or 'rm'."

        await self.client.send_message(message.channel.id, response)

    @bg_task(30)
    async def youtuber_check(self):
        data = await self.get_youtubers_by_guilds()
        for guild_id, latest_videos in data.items():
            guild = self.client.get_guild(guild_id)
            if not guild:
                continue

            async with aiosqlite.connect(self.db.path) as conn:
                cursor = await conn.execute(
                    "SELECT announcement_channel FROM guilds WHERE id=?",
                    (guild.id,))
                announcement_channel = await cursor.fetchone()
                await cursor.close()
            for video in latest_videos:
                async with aiosqlite.connect(self.db.path) as conn:
                    cursor = await conn.execute(
                        "SELECT latest FROM youtubers_{} WHERE id=?".format(
                            guild.id), (video.channel_id,))
                    video_ids = await cursor.fetchall()
                    await cursor.close()
                video_ids = [id[0] for id in video_ids
                             if id[0] != "" and id[0] is not None]
                if video.video_id in video_ids:
                    continue
                try:
                    await self.client.send_message(
                        announcement_channel,
                        "{} uploaded a new video! "
                        "https://www.youtube.com/watch?v={}".format(
                            video.channel_name, video.video_id)
                    )
                    async with aiosqlite.connect(self.db.path) as conn:
                        await conn.execute(
                            "UPDATE youtubers_{} SET latest=? WHERE "
                            "id=?".format(guild.id),
                            (video.video_id, video.channel_id))
                        await conn.commit()
                except Exception as e:
                    LOG.info(e)

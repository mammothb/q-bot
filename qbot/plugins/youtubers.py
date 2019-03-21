from collections import defaultdict

import asyncio
import logging
import re

import aiohttp
import aiosqlite
from lxml import etree as ET

from qbot.config import GOOGLE_API_KEY
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

class Video:  # pylint: disable=R0903
    def __init__(self, channel_name, channel_id, video_id):
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.video_id = video_id

YOUTUBE_PLATFORM = Platform("youtube")

@YOUTUBE_PLATFORM.set_collector
async def youtube_collector(youtubers):
    youtubers = list(map(lambda s: s.replace(" ", "_"), youtubers))
    latest_videos = []
    for channel_id in youtubers:
        url = "https://www.youtube.com/feeds/videos.xml"
        async with aiohttp.ClientSession() as session:
            params = {
                "channel_id": channel_id
            }
            async with session.get(url, params=params) as resp:
                result = await resp.text()
                root = ET.fromstring(result.encode("utf-8"))
                nsmap = {k if k is not None else "default": v
                         for k, v in root.nsmap.items()}
                video = Video(
                    root.find(".//default:title", namespaces=nsmap).text,
                    root.find(".//yt:channelId", namespaces=nsmap).text,
                    root.find("./default:entry/yt:videoId",
                              namespaces=nsmap).text
                )
                latest_videos.append(video)
        # url = "https://www.googleapis.com/youtube/v3/search"
        # async with aiohttp.ClientSession() as session:
        #     params = {
        #         "key": GOOGLE_API_KEY,
        #         "part": "snippet",
        #         "channelId": channel_id,
        #         "maxResults": "1",
        #         "order": "date"
        #         }
        #     async with session.get(url, params=params) as resp:
        #         result = await resp.json()
        #         video = Video(
        #             result["items"][0]["snippet"]["channelTitle"],
        #             channel_id,
        #             result["items"][0]["id"]["videoId"]
        #         )
        #         latest_videos.append(video)
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
                    "CREATE TABLE IF NOT EXISTS youtubers_{} ("
                    "id TEXT PRIMARY KEY,"
                    "latest INTEGER NOT NULL);".format(guild.id))
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

            youtubers = set(map(lambda s: re.sub("[^0-9a-zA-Z_-]+", "", s),
                                youtubers))
            try:
                latest_videos = await platform.collector(youtubers)
                for guild, guild_youtubers in temp_data.items():
                    for video in latest_videos:
                        if video.channel_id in guild_youtubers:
                            data[guild.id].append(video)

            except Exception as exception:  # pylint: disable=W0703
                LOG.info("Cannot gather youtubers from %s", platform.name)
                LOG.info("With youtubers: %s", ",".join(youtubers))
                LOG.exception(exception)
        return data

    @command(pattern="^" + PREFIX + "youtuber (.*)",
             description="Add or remove YouTube channel from notification",
             usage=PREFIX + "youtuber add/rm channel_id")
    async def youtuber(self, message, args):
        cmd = args[0].split(" ")
        if len(cmd) != 2:
            response = "Not enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        operation = cmd[0]
        channel_id = cmd[1]
        if operation == "add":
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
        elif operation == "rm":
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "DELETE FROM youtubers_{} WHERE id=?".format(
                        message.guild.id), (channel_id,))
                await conn.commit()
                response = "Removed channel {}!".format(channel_id)
        else:
            response = "Unknown command, use 'add' or 'rm'."

        await self.client.send_message(message.channel.id, response)

    @command(pattern="^" + PREFIX + "youtuber_setup (.*)",
             description="Add or remove Twitch streamer from notification",
             usage=PREFIX + "youtuber_setup msg")
    async def youtuber_setup(self, message, args):
        args = args[0].split(" ", 1)
        if len(args) < 2:
            response = "Not enough arguments"
            await self.client.send_message(message.channel.id, response)
            return
        youtubers_channel = int(args[0][2:-1])
        youtubers_text = args[1]
        try:
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "UPDATE guilds SET youtubers_channel=?, youtubers_text=? "
                    "WHERE id=?", (youtubers_channel, youtubers_text,
                                   message.guild.id))
                await conn.commit()
                response = "Update YouTubers annoucement text and channel!"
        except Exception as exception:  # pylint: disable=W0703
            LOG.exception(exception)
            response = "Couldn't update YouTubers annoucement text and channel"
        await self.client.send_message(message.channel.id, response)

    @bg_task(60 * 60)
    async def youtuber_check(self):
        data = await self.get_youtubers_by_guilds()
        for guild_id, latest_videos in data.items():
            guild = self.client.get_guild(guild_id)
            if not guild:
                continue
            async with aiosqlite.connect(self.db.path) as conn:
                cursor = await conn.execute(
                    "SELECT youtubers_channel, youtubers_text FROM guilds "
                    "WHERE id=?", (guild.id,))
                youtubers_channel, youtubers_text = await cursor.fetchone()
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
                    rep = {
                        "{youtuber}": video.channel_name,
                        "{link}": "https://www.youtube.com/watch?v={}".format(
                            video.video_id)
                    }
                    await self.client.send_message(
                        youtubers_channel,
                        replace_multiple(rep, youtubers_text)
                    )
                    async with aiosqlite.connect(self.db.path) as conn:
                        await conn.execute(
                            "UPDATE youtubers_{} SET latest=? WHERE "
                            "id=?".format(guild.id),
                            (video.video_id, video.channel_id))
                        await conn.commit()
                except Exception as exception:  # pylint: disable=W0703
                    LOG.exception(exception)

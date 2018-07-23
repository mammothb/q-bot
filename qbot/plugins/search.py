# -*- coding: utf-8 -*-
import json

import aiohttp

from qbot.config import GOOGLE_API_KEY, TWITCH_CLIENT_ID
from qbot.const import PREFIX
from qbot.decorators import command
from qbot.plugin import Plugin

NOT_FOUND = "I didn't find anything 😢..."

class Search(Plugin):
    @command(pattern="^" + PREFIX + "youtube (.*)",
             description="Search for YouTube videos",
             usage=PREFIX + "youtube video_name")
    async def youtube(self, message, args):
        search = args[0]
        url = "https://www.googleapis.com/youtube/v3/search"
        async with aiohttp.ClientSession() as session:
            params = {"type": "video", "q": search, "part": "snippet",
                      "key": GOOGLE_API_KEY}
            async with session.get(url, params=params) as resp:
                data = await resp.json()
        if data["items"]:
            video = data["items"][0]
            response = "https://youtu.be/" + video["id"]["videoId"]
        else:
            response = NOT_FOUND

        await self.client.send_message(message.channel.id, response)

    @command(pattern="^" + PREFIX + "twitch (.*)",
             description="Search for Twitch streamers",
             usage=PREFIX + "twitch streamer_name")
    async def twitch(self, message, args):
        search = args[0]
        url = "https://api.twitch.tv/kraken/search/channels"
        async with aiohttp.ClientSession() as session:
            params = {"q": search, "client_id": TWITCH_CLIENT_ID}
            async with session.get(url, params=params) as resp:
                data = await resp.json()
        if data["channels"]:
            channel = data["channels"][0]
            response = "\n**" + channel["display_name"] + "**: " + channel["url"]
            response += " {0[followers]} followers & {0[views]} views".format(
                channel)
        else:
            response = NOT_FOUND

        await self.client.send_message(message.channel.id, response)

    @command(pattern="^" + PREFIX + "wiki (.*)",
             description="Search for Wikipedia pages",
             usage=PREFIX + "wiki <search terms>")
    async def wiki(self, message, args):
        search = args[0]
        url = "https://en.wikipedia.org/w/api.php"
        async with aiohttp.ClientSession() as session:
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srlimit": "1",
                "srsearch": search
            }
            async with session.get(url, params=params) as resp:
                data = await resp.json()
        if data["query"]["searchinfo"]["totalhits"] > 0:
            page_id = str(data["query"]["search"][0]["pageid"])
            async with aiohttp.ClientSession() as session:
                params = {
                    "action": "query",
                    "format": "json",
                    "prop": "info",
                    "pageids": page_id,
                    "inprop": "url"
                }
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
            response = data["query"]["pages"][page_id]["fullurl"]
        else:
            response = NOT_FOUND

        await self.client.send_message(message.channel.id, response)

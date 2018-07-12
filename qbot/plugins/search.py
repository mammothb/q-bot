# -*- coding: utf-8 -*-
import aiohttp

from qbot.config import GOOGLE_API_KEY, TWITCH_CLIENT_ID
from qbot.const import PREFIX
from qbot.decorators import command
from qbot.plugin import Plugin

NOT_FOUND = "I didn't find anything 😢..."

class Search(Plugin):
    @command(db_name="youtube",
             pattern="^" + PREFIX + "youtube (.*)",
             db_check=True,
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

    @command(db_name="twitch",
             pattern="^" + PREFIX + "twitch (.*)",
             db_check=True,
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

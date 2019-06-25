# -*- coding: utf-8 -*-
import logging
import os

import aiohttp
from discord.file import File
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains

from qbot.config import DB_PATH, GOOGLE_API_KEY, TWITCH_CLIENT_ID
from qbot.const import PREFIX
from qbot.decorators import command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")
NOT_FOUND = "I didn't find anything 😢..."

class Search(Plugin):
    @command(pattern="^" + PREFIX + "googleimg (.*)",
             description="Search for images using Google image",
             usage=PREFIX + "googleimg phrase")
    async def googleimg(self, message, args):
        search = args[0]
        img_path = os.path.join(os.path.dirname(DB_PATH), "googleimg.png")
        response = search

        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--hide-scrollbars")
            chrome_options.add_argument("--log-level=3")
            driver = webdriver.Chrome(options=chrome_options)
            url = "https://www.google.com/search?tbm=isch&q={}".format(
                search.replace(" ", "+"))
            driver.get(url)
            # Scroll to the top edge of image results
            element = driver.find_element_by_id("center_col")
            actions = ActionChains(driver)
            actions.move_to_element(element).perform()
            driver.save_screenshot(img_path)
            driver.quit()
            await self.client.send_files(
                [File(img_path, filename=os.path.basename(img_path))],
                message.channel.id,
                content="Google Images results for **{}**".format(search))
        except Exception as exception:  # pylint: disable=W0703
            LOG.info("Cannot google image search with '%s'", search)
            LOG.exception(exception)
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

    @command(pattern="^" + PREFIX + "urbandict (.*)",
             description="Search for Urban Dictionary phrases",
             usage=PREFIX + "urbandict phrase")
    async def urbandict(self, message, args):
        search = args[0]
        url = "https://api.urbandictionary.com/v0/define"
        async with aiohttp.ClientSession() as session:
            params = {"term": search}
            async with session.get(url, params=params) as resp:
                data = await resp.json()
        if data["list"]:
            response = ("{}\n**Word:** {}\n**Definition:** {}\n"
                        "**Example:** {}".format(
                            data["list"][0]["permalink"],
                            data["list"][0]["word"],
                            data["list"][0]["definition"],
                            data["list"][0]["example"]))
            response = response.replace("[", "").replace("]", "")
        else:
            response = NOT_FOUND

        await self.client.send_message(message.channel.id, response)

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

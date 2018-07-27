import logging

import aiosqlite
import discord
from discord.channel import DMChannel, TextChannel

from qbot.config import DB_PATH
from qbot.database import Db
from qbot.pluginmanager import PluginManager

LOG = logging.getLogger("discord")

class QBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = Db(DB_PATH, self.loop)  # pylint: disable=C0103
        self.plugins = []
        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_all()
        self.last_messages = []

        if self.shard_id is not None:
            self.shard = [self.shard_id, self.shard_count]
        else:
            self.shard = [0, 1]

    def run(self, *args, **kwargs):
        self.loop.run_until_complete(self.start(*args, **kwargs))

    async def on_ready(self):
        """Called when the bot is ready.
        Connects to the database
        Dispatched all the ready events
        """
        LOG.info("Logged in")

        await self.add_all_guilds()
        for plugin in self.plugins:
            self.loop.create_task(plugin.on_ready())

    def get_plugins(self):
        return self.plugins

    async def get_message(self, *args, **kwargs):
        return await self.http.get_message(*args, **kwargs)

    async def send_message(self, *args, **kwargs):
        return await self.http.send_message(*args, **kwargs)

    async def on_message(self, message):
        if isinstance(message.channel, DMChannel):
            return

        if message.author.__class__ != discord.Member:
            return

        # pylint: disable=W0212
        for plugin in self.plugins:
            self.loop.create_task(plugin._on_message(message))

    async def add_all_guilds(self):
        """Syncing all the guilds to the DB"""
        LOG.debug("Syncing guilds and db")
        for guild in self.guilds:
            LOG.debug("Adding guild %d\"s id to db", guild.id)
            # pylint: disable=W0212
            for channel_id in guild._channels:
                if (isinstance(guild._channels[channel_id], TextChannel) and
                        guild._channels[channel_id].name == "general"):
                    announcement_channel = channel_id
                    break
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "INSERT OR IGNORE INTO guilds "
                    "(id,name,announcement_channel,announcement_text) "
                    "VALUES(?,?,?,?)",
                    (guild.id, guild.name, announcement_channel,
                     "{streamer} is now live on {link} !"))
                await conn.commit()

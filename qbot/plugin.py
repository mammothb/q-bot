import inspect
import logging

from discord.errors import Forbidden

LOG = logging.getLogger("discord")

class PluginMount(type):
    def __init__(cls, name, bases, attrs):  # pylint: disable=W0613
        """Called when a Plugin derived class is imported"""
        if not hasattr(cls, "plugins"):
            cls.plugins = []
        else:
            cls.plugins.append(cls)
        super(PluginMount, cls).__init__(name, bases, attrs)

class Plugin(object, metaclass=PluginMount):
    is_global = False
    fancy_name = None

    def __init__(self, client):
        self.client = client
        self.db = client.db
        self.commands = {}
        self.bg_tasks = {}

        for __, member in inspect.getmembers(self):
            # registering commands
            if hasattr(member, "_is_command"):
                self.commands[member.__name__] = member
            # registering bg_tasks
            if hasattr(member, "_bg_task"):
                self.bg_tasks[member.__name__] = member
                self.client.loop.create_task(member())
        LOG.info("Registered %d commands / %d bg tasks", len(self.commands),
                 len(self.bg_tasks))

    async def on_ready(self):
        pass

    async def _on_message(self, message):
        for __, func in self.commands.items():
            try:
                await func(message)
            except Forbidden:
                msg = ("⚠️ Oops, it looks like I don't have the permission "
                       "to do that 😐 ⚠️")
                await self.client.send_message(message.channel.id, msg)

        await self.on_message(message)

    async def on_message(self, message):
        pass

    async def on_message_edit(self, before, after):
        pass

    async def on_message_delete(self, message):
        pass

    async def on_channel_create(self, channel):
        pass

    async def on_channel_update(self, before, after):
        pass

    async def on_channel_delete(self, channel):
        pass

    async def on_member_join(self, member):
        pass

    async def on_member_remove(self, member):
        pass

    async def on_member_update(self, before, after):
        pass

    async def on_server_join(self, server):
        pass

    async def on_server_update(self, before, after):
        pass

    async def on_server_role_create(self, server, role):
        pass

    async def on_server_role_delete(self, server, role):
        pass

    async def on_server_role_update(self, server, role):
        pass

    async def on_voice_state_update(self, before, after):
        pass

    async def on_member_ban(self, member):
        pass

    async def on_member_unban(self, member):
        pass

    async def on_typing(self, channel, user, when):
        pass

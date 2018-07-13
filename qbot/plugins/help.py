import logging

from discord.embeds import Embed

from qbot.const import PREFIX
from qbot.decorators import command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")

async def get_help_info(self):
    if self.fancy_name is None:
        self.fancy_name = type(self).__name__

    commands = []
    for cmd in self.commands.values():
        commands.append(cmd.info)
    payload = {
        "name": type(self).__name__,
        "fancy_name": self.fancy_name,
        "commands": commands
    }
    return payload


class Help(Plugin):
    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        # Patch the Plugin class
        Plugin.get_help_info = get_help_info

    async def generate_help(self):
        help_payload = []
        for plugin in self.client.plugins:
            help_info = await plugin.get_help_info()
            help_payload.append(help_info)

        return self.render_message(help_payload)

    def render_message(self, help_payload):
        message_batches = []
        for plugin_info in help_payload:
            if plugin_info["commands"] != []:
                embed = Embed(colour=3447003)
                embed.add_field(
                    name="__**{} Plugin Commands**__".format(
                        plugin_info["fancy_name"]),
                    value="\u200b", inline=True)
                for cmd in plugin_info["commands"]:
                    embed.add_field(
                        name="   **{}**".format(cmd["name"]),
                        value=cmd.get("description", "--"), inline=False)
                message_batches.append(embed)
        return message_batches

    @command(pattern="^" + PREFIX + "help",
             description="Get help",
             usage=PREFIX + "help")
    async def help(self, message, __):
        help_messages = await self.generate_help()
        if help_messages == []:
            help_messages = []
            await self.client.send_message(message.channel.id,
                                           "There's no command to show :cry:")
        else:
            for msg in help_messages:
                await self.client.send_message(
                    message.channel.id, content=None, embed=msg.to_dict())

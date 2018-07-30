# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import logging

from qbot.const import PREFIX, TZ_OFFSET
from qbot.decorators import command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")

class Quote(Plugin):
    @command(pattern="^" + PREFIX + "quote (.*)",
             description="Format quote message as a code block",
             usage=PREFIX + "quote msg_id")
    async def quote(self, message, args):
        msg_id = args[0]
        try:
            msg = await self.client.get_message(message.channel.id, msg_id)
            display_name = message.guild.get_member(
                int(msg["author"]["id"])).display_name
            time_str = (datetime.strptime(msg["timestamp"].split(".")[0],
                                          "%Y-%m-%dT%H:%M:%S") +
                        timedelta(hours=TZ_OFFSET)).strftime("%Y-%m-%d %I:%M %p")
            quote_msg = "```{} - {} UTC+{}\n{}```".format(
                display_name, time_str, TZ_OFFSET, msg["content"])
        except Exception as exception:  # pylint: disable=W0703
            LOG.exception(exception)
            quote_msg = "Message not found!"
        await self.client.send_message(message.channel.id, quote_msg)
        await message.delete()

# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import logging

from discord.errors import NoMoreItems
from symspellpy.symspellpy import SymSpell

from qbot.const import PREFIX, TZ_OFFSET
from qbot.decorators import command
from qbot.plugin import Plugin
from qbot.utility import try_parse_int64

LOG = logging.getLogger("discord")

class Quote(Plugin):
    @command(pattern="^" + PREFIX + "quote (.*)",
             description="Format quote message as a code block",
             usage=PREFIX + "quote msg_id")
    async def quote(self, message, args):
        msg = None
        if try_parse_int64(args[0]) is not None:
            msg_id = args[0]
            try:
                msg = await self.client.get_message(message.channel.id, msg_id)
            except Exception as exception:  # pylint: disable=W0703
                LOG.exception(exception)
        else:
            input_term = args[0]
            sym_spell = SymSpell()
            for term in input_term.split(" "):
                sym_spell.create_dictionary_entry(term, 1)
            target = sym_spell.lookup_compound(input_term, 2)[0].term
            iterator = message.channel.history(limit=100)
            for __ in range(100):
                try:
                    msg = await iterator.next()
                    suggestion = sym_spell.lookup_compound(msg.content, 2)[0]
                    if suggestion.term == target:
                        msg = await self.client.get_message(
                            message.channel.id, msg.id)
                        break
                except NoMoreItems:
                    msg = None
        if msg is not None:
            display_name = message.guild.get_member(
                int(msg["author"]["id"])).display_name
            time_str = (datetime.strptime(msg["timestamp"].split(".")[0],
                                          "%Y-%m-%dT%H:%M:%S") +
                        timedelta(hours=TZ_OFFSET)).strftime(
                            "%Y-%m-%d %I:%M %p")
            quote_msg = "```{} - {} UTC+{}\n{}```".format(
                display_name, time_str, TZ_OFFSET, msg["content"])
        else:
            quote_msg = "Message not found!"

        await self.client.send_message(message.channel.id, quote_msg)
        await message.delete()

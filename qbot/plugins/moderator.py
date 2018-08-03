# -*- coding: utf-8 -*-
import logging

import aiosqlite
import asyncio

from qbot.const import PREFIX
from qbot.decorators import command
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")
NOT_FOUND = "I didn't find anything 😢..."

class Moderator(Plugin):
    @command(pattern="^" + PREFIX + "purge (.*)",
             description="Clear past message by everyone or target user",
             usage=PREFIX + "purge <@user> number")
    async def purge(self, message, args):
        async with aiosqlite.connect(self.db.path) as conn:
            cursor = await conn.execute(
                "SELECT mod_roles FROM guilds WHERE id=?", (message.guild.id,))
            roles = await cursor.fetchone()
            await cursor.close()
        roles = map(int, roles[0].split(","))
        if set(role.id for role in message.author.roles).isdisjoint(set(roles)):
            msg = "You don't have the permisson to do that!"
            await self.client.send_message(message.channel.id, msg)
            return
        args = args[0].split(" ")
        if len(args) == 1:
            deleted = await message.channel.purge(limit=int(args[0]))
        elif len(args) == 2:
            target_id = int(args[0][2:-1])
            def check_id(msg):
                return msg.author.id == target_id
            deleted = await message.channel.purge(limit=int(args[1]),
                                                  check=check_id)
        msg = "Deleted {} message(s)".format(len(deleted))
        confirm_msg = await self.client.send_message(message.channel.id, msg)
        await asyncio.sleep(10)
        await self.client.http.delete_message(message.channel.id,
                                              confirm_msg["id"])

    @command(pattern="^" + PREFIX + "moderator_setup (.*)",
             description="Clear past message by everyone or target user",
             usage=PREFIX + "moderator_setup roles")
    async def moderator_setup(self, message, args):
        args = args[0].split(" ")
        roles = [role.id for role in message.guild.roles if role.name in args]
        roles = ",".join(map(str, roles))
        try:
            async with aiosqlite.connect(self.db.path) as conn:
                await conn.execute(
                    "UPDATE guilds SET mod_roles=? WHERE id=?",
                    (roles, message.guild.id))
                await conn.commit()
                response = "Update Moderator roles!"
        except Exception as exception:  # pylint: disable=W0703
            LOG.exception(exception)
            response = "Couldn't update Moderator roles"
        await self.client.send_message(message.channel.id, response)

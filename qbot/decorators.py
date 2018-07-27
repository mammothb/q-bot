import asyncio
from functools import wraps
import logging
import re

from qbot.const import PREFIX

LOG = logging.getLogger("discord")

def bg_task(sleep_time, ignore_errors=True):
    def actual_decorator(func):
        @wraps(func)
        async def wrapper(self):
            await self.client.wait_until_ready()
            await self.wait_until_ready()
            while True:
                if ignore_errors:
                    try:
                        await func(self)
                    except Exception as exception:  # pylint: disable=W0703
                        LOG.info("An error occured in the %s bg task "
                                 "retrying in %d seconds", func.__name__,
                                 sleep_time)
                        LOG.exception(exception)
                else:
                    await func(self)

                await asyncio.sleep(sleep_time)

        wrapper._bg_task = True  # pylint: disable=W0212
        return wrapper

    return actual_decorator

def command(pattern=None, user_check=None, description="", usage=None):
    def actual_decorator(func):
        name = func.__name__
        cmd_name = PREFIX + name
        prog = re.compile(pattern or cmd_name)
        @wraps(func)
        async def wrapper(self, message):
            # Is it matching?
            match = prog.match(message.content)
            if not match:
                return False

            args = match.groups()
            author = message.author

            is_owner = author.guild.owner.id == author.id

            perms = author.guild_permissions
            is_admin = perms.manage_guild or perms.administrator or is_owner

            # Checking the member with the predicate
            if user_check and not is_admin:
                authorized = await user_check(message.author)
                if not authorized:
                    return

            LOG.info("%s#%s@%s >> %s", message.author.name,
                     message.author.discriminator, message.guild.name,
                     message.clean_content)

            await func(self, message, args)
        wrapper._is_command = True  # pylint: disable=W0212
        if usage:
            command_name = usage
        else:
            command_name = "!" + func.__name__
        wrapper.info = {"name": command_name, "description": description}
        return wrapper
    return actual_decorator

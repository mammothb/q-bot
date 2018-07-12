import logging
import sqlite3

from qbot.storage import Storage

LOG = logging.getLogger("discord")

class Db(object):
    def __init__(self, db_path, loop):
        self.loop = loop
        self.db_path = db_path
        self.loop.create_task(self.create())

    async def create(self):
        self.sqlite = await sqlite3.connect(self.db_path)

    async def get_storage(self, plugin, guild):
        namespace = "{}.{}:".format(plugin.__class__.__name__, guild.id)
        storage = Storage(namespace, self.sqlite)
        return storage

import logging

import aiosqlite

from qbot.storage import Storage

LOG = logging.getLogger("discord")

class Db(object):
    def __init__(self, db_path, loop):
        self.loop = loop
        self.path = db_path
        self.loop.create_task(self.create())

    async def create(self):
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS guilds ("
                               "id INTEGER PRIMARY KEY,"
                               "name TEXT NOT NULL,"
                               "announcement_channel INTEGER NOT NULL,"
                               "announcement_text TEXT NOT NULL);")
            await conn.commit()

    async def get_storage(self, plugin, guild):
        conn = aiosqlite.connect(self.path)
        namespace = "{}.{}:".format(plugin.__class__.__name__, guild.id)
        storage = Storage(namespace, conn)
        return storage

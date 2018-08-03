import logging

import aiosqlite

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
                               "streamers_channel INTEGER NOT NULL,"
                               "streamers_text TEXT NOT NULL,"
                               "youtubers_channel INTEGER NOT NULL,"
                               "youtubers_text TEXT NOT NULL,"
                               "mod_roles TEXT);")
            await conn.commit()

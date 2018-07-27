import logging
from qbot.plugin import Plugin

LOG = logging.getLogger("discord")

class PluginManager:
    def __init__(self, client):
        self.client = client
        self.db = client.db

    def load(self, plugin):
        LOG.info("Loading plugin %s.", plugin.__name__)
        plugin_instance = plugin(self.client)
        self.client.plugins.append(plugin_instance)
        LOG.info("Plugin %s loaded.", plugin.__name__)

    def load_all(self):
        for plugin in Plugin.plugins:
            self.load(plugin)

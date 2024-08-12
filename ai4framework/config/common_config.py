import configparser
import os

class ConfigManager:
    _config = None

    @classmethod
    def load_config(cls, config_file):
    # def load_config(cls, config_file="C:\\Users\\HP\\slab\\ai4fix\\ai4framework\\config\\config.properties"):
        if cls._config is None:
            cls._config = configparser.ConfigParser()
            cls._config.read(config_file)
        return cls._config

    @classmethod
    def get_config(cls):
        if cls._config is None:
            raise Exception("Configuration not loaded. Call load_config() first.")
        return cls._config

# Load the configuration at the start
if os.name == 'nt':
    config_file = 'C:\\Users\\HP\\slab\\ai4fix\\ai4framework\\config\\config.properties'
else:
    config_file = '/mnt/c/Users/HP/slab/ai4fix/ai4framework/config/config_mnt.properties'
ConfigManager.load_config(config_file)
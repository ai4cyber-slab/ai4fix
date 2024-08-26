import configparser
import os

class ConfigManager:
    _config = None

    @classmethod
    def load_config(cls, config_file):
        if cls._config is None:
            cls._config = configparser.ConfigParser()
            cls._config.read(config_file)
        return cls._config

    @classmethod
    def get_config(cls):
        if cls._config is None:
            raise Exception("Configuration not loaded. Call load_config() first.")
        return cls._config

base_dir = os.path.dirname(os.path.abspath(__file__))

if os.name == 'nt':
    config_file = os.path.join(base_dir, 'config.properties')
else:
    config_file = os.path.join(base_dir, 'config_mnt.properties')
ConfigManager.load_config(config_file)
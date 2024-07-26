import configparser

class ConfigManager:
    _config = None

    @classmethod
    def load_config(cls, config_file="config.properties"):
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
ConfigManager.load_config()
config = ConfigManager.get_config()

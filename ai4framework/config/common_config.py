import configparser
import os
from urllib.parse import urlparse
import sys
import openai

class ConfigManager:
    """
    A class to manage configuration settings for the AI4Framework.

    This class provides methods to load and access configuration settings
    from a specified configuration file.
    """

    _config = None

    @classmethod
    def load_config(cls, config_file):
        """
        Load configuration settings from a specified file.

        Args:
            config_file (str): Path to the configuration file.

        Returns:
            configparser.ConfigParser: The loaded configuration object.
        """
        if cls._config is None:
            cls._config = configparser.ConfigParser()
            cls._config.read(config_file)
        return cls._config

    @classmethod
    def get_config(cls):
        """
        Get the loaded configuration object.

        Raises:
            Exception: If configuration has not been loaded yet.

        Returns:
            configparser.ConfigParser: The loaded configuration object.
        """
        if cls._config is None:
            raise Exception("Configuration not loaded. Call load_config() first.")
        return cls._config

    
# Handling command-line arguments or environment variables
def get_project_root():
    """
    Get the project root path from command-line arguments or environment variables.

    Returns:
        str: The path to the project root directory.
    """
    # First, try to get it from command-line arguments
    if len(sys.argv) > 1:
        return sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] != None :
        openai.api_key=sys.argv[2]
    
    # If not passed as an argument, try an environment variable
    project_root = os.getenv("PROJECT_PATH")
    
    if project_root:
        return project_root
    else:
        raise Exception("Project root path must be provided as a command-line argument or set in the PROJECT_ROOT environment variable.")

# Get the base directory of the current file
config_file = os.path.join(get_project_root(), 'config.properties')
# Load the configuration
ConfigManager.load_config(config_file)
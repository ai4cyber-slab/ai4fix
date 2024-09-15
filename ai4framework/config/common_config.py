import configparser
import os
from urllib.parse import urlparse

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
    
    # @classmethod
    # def get_cloned_repo_path(cls):
    #     """
    #     Returns the path to the cloned repository based on the base directory and remote URL.
    #     """
    #     config = cls.get_config()
    #     base_dir = config['DEFAULT']['config.base_dir']
    #     remote_repo_url = config['DEFAULT']['config.remote_repo_url']
        
    #     # Extract the repository name from the URL
    #     repo_name = urlparse(remote_repo_url).path.split('/')[-1].replace('.git', '')
    #     return os.path.join(base_dir, repo_name)

    # @classmethod
    # def get_project_path(cls):
    #     """
    #     Generates project-specific paths dynamically, based on the cloned repo path.
    #     """
    #     cloned_repo_path = cls.get_cloned_repo_path()
    #     return {
    #         "project_path": cloned_repo_path,
    #         "results_path": os.path.join(cloned_repo_path, 'patches'),
    #         # "project_exec_path": os.path.join(cloned_repo_path, 'target'),
    #         # "jsons_listfile": os.path.join(cloned_repo_path, 'jsons.lists'),
    #         "validation_results_path": os.path.join(cloned_repo_path, 'patches', 'validation'),
    #         "generated_patches_path": os.path.join(cloned_repo_path, 'patches'),
    #         "subject_project_path": cloned_repo_path,
    #     }

# Get the base directory of the current file
base_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the config file
config_file = os.path.join(base_dir, 'config.properties')
# Load the configuration
ConfigManager.load_config(config_file)



# def main(config_file):

#     ConfigManager.load_config(config_file)

#     # 2. Get dynamically generated paths based on the repo URL and base directory
#     paths = ConfigManager.get_project_path()

# if __name__ == "__main__":
#     config_file = "config.properties"
#     main(config_file)
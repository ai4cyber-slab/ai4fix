import os
import openai
import argparse
import configparser

from config.config_path_handler import *


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
        Load configuration settings from a specified file, ignoring comments and comment-only lines.

        Args:
            config_file (str): Path to the configuration file.

        Returns:
            configparser.ConfigParser: The loaded configuration object.
        """
        if cls._config is None:
            cls._config = configparser.ConfigParser()

            cleaned_lines = []
            with open(config_file, 'r') as file:
                for line in file:
                    stripped_line = line.strip()

                    if not stripped_line or stripped_line.startswith('#'):
                        continue

                    line = stripped_line.split('#', 1)[0].strip()

                    if line:
                        cleaned_lines.append(line)

            cls._config.read_string('\n'.join(cleaned_lines))

            cls.adjust_config_paths()
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


    @classmethod
    def adjust_config_paths(cls):
        """
        Adjusts paths in the config to include the hidden folder after 'config.project_root'.

        Modifies the config object in place.
        """
        config = cls._config
        project_root = config.get('DEFAULT', 'config.project_root', fallback='')

        if project_root == '':
            print('CONFIG.PROJECT_ROOT is not set in the configuration!')
            sys.exit(1)

        path_keys = [
            {'DEFAULT': 'config.results_path', 'fallback': 'patches'},
            {'DEFAULT': 'config.jsons_listfile', 'fallback': 'jsons.lists'},
            {'ISSUES': 'config.issues_path', 'fallback': 'issues.json'},
            {'ANALYZER': 'config.analyzer_results_path', 'fallback': 'results'},
        ]

        for path in path_keys:
            for key, value in path.items():
                if config.has_option(key, value):
                    original_path = config.get(key, value, fallback=path['fallback'])
                    adjusted_path = cls.insert_hidden_in_path(project_root, original_path)
                    config.set(key, value, adjusted_path)


    @staticmethod
    def insert_hidden_in_path(project_root, original_path):
        """
        Inserts hidden folder into the path after the project_path.

        Args:
            project_path (str): The project root path.
            path (str): The original path.

        Returns:
            str: The adjusted path with hidden folder inserted.
        """
        # Normalize paths
        project_root = os.path.normpath(project_root)
        original_path = os.path.normpath(original_path)

        # Handle absolute paths
        if os.path.isabs(original_path):
            original_path = os.path.relpath(original_path, project_root)

        new_path = os.path.join(project_root, '.ai4framework', original_path)
        new_path = os.path.normpath(new_path)

        return new_path
    

# Handling command-line arguments or environment variables
def get_project_root():
    """
    Get the project root path from command-line arguments or environment variables.

    Returns:
        str: The path to the project root directory.
    """
    parser = argparse.ArgumentParser(description='Process some parameters.')
    parser.add_argument('--project-root', '-p', dest='project_root', type=str, help='Path to the project root directory.')
    parser.add_argument('--openai-key', '-k', dest='openai_key', type=str, help='OpenAI API key.')
    parser.add_argument('--skip-patches', action='store_true', help='If provided, the patches part will be skipped.')
    parser.add_argument('--sast-rerun', action='store_true', help='If provided, issues will be generated for the new java files contents')

    args, unknown = parser.parse_known_args()

    # Set OpenAI API key if provided
    if args.openai_key:
        openai.api_key = args.openai_key

    if args.project_root:
        return args.project_root

    # If not passed as an argument, try an environment variable
    project_root = os.getenv("PROJECT_PATH")

    if project_root:
        return project_root
    else:
        raise Exception("Project root path must be provided as a command-line argument or set in the PROJECT_PATH environment variable.")


def read_config_properties(file_path):
    """
    Reads the config.properties file and extracts all configurations, ignoring section headers and inline comments.

    Args:
        file_path (str): Path to the config.properties file.

    Returns:
        dict: A dictionary of key-value pairs from the properties file, excluding section headers and comments.
    """
    config = {}

    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()

            # Skip comments, empty lines, and section headers
            if not line or line.startswith("#") or (line.startswith("[") and line.endswith("]")):
                continue

            # Process key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)

                # Remove inline comments if present
                value = value.split('#', 1)[0].strip()

                config[key.strip()] = value

    return config


config_file = os.path.join(get_project_root(), 'config.properties')
ConfigManager.load_config(config_file)
config = ConfigManager.get_config()

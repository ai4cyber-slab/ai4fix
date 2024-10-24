import os
import openai
import argparse
import configparser


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
        Adjusts paths in the config to include the hidden folder after 'config.project_path'.

        Modifies the config object in place.
        """
        config = cls._config
        project_path = config.get('DEFAULT', 'config.project_path', fallback=None)
        if not project_path:
            raise Exception("config.project_path is not set in the configuration.")

        path_keys = [
            ('DEFAULT', 'config.results_path'),
            ('DEFAULT', 'config.jsons_listfile'),
            ('ISSUES', 'config.issues_path'),
            ('ANALYZER', 'config.analyzer_results_path'),
        ]

        for section, key in path_keys:
            if config.has_option(section, key):
                original_path = config.get(section, key)
                adjusted_path = cls.insert_hidden_in_path(project_path, original_path)
                config.set(section, key, adjusted_path)


    @staticmethod
    def insert_hidden_in_path(project_path, path):
        """
        Inserts hidden folder into the path after the project_path.

        Args:
            project_path (str): The project root path.
            path (str): The original path.

        Returns:
            str: The adjusted path with hidden folder inserted.
        """
        # Handle relative paths
        if not os.path.isabs(path):
            path = os.path.join(project_path, path)

        # Normalize paths
        project_path = os.path.normpath(project_path)
        path = os.path.normpath(path)

        if not path.startswith(project_path):
            return path

        # Getting the top-level root directory
        root_dir = project_path
        while os.path.dirname(root_dir) != '/':
            root_dir = os.path.dirname(root_dir)

        rel_path = os.path.relpath(path, project_path)
        new_path = os.path.join(root_dir, '.ai4framework', rel_path)
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

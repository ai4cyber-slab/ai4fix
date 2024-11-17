import os
import sys
import configparser
from utils.logger import logger


class ConfigManager:
    """
    A class to manage configuration settings for the AI4Framework.

    This class provides methods to load and access configuration settings
    from a specified configuration file.
    """

    _config = None
    @classmethod
    def get_config(cls, project_root, dir_to_analyze):
        """
        Load configuration settings from a specified file, ignoring comments and comment-only lines.

        Args:
            project_root (str): Path to the root of the project.
            dir_to_analyze (str): Path to the directory that will be analyzed.

        Returns:
            configparser.ConfigParser: The loaded configuration object.
        """
        if project_root == None:
            project_root = os.getenv("PROJECT_PATH")

            if not project_root:
                logger.warning("Project root path must be provided as a command-line argument (-r/--project_root), or set in the PROJECT_PATH environment variable.")
                sys.exit(1)

        if dir_to_analyze == None:
            dir_to_analyze = project_root

        if not os.path.isabs(dir_to_analyze):
            dir_to_analyze = os.path.join(project_root, dir_to_analyze)

        project_name = project_root.replace('/', '')

        if cls._config is None:
            cls._config = configparser.ConfigParser()

            project_config = [
                '[DEFAULT]',
                f'config.project_name={project_name}',
                f'config.project_root={project_root}',
                f'config.dir_to_analyze={dir_to_analyze}',
            ]

            cls._config.read_string('\n'.join(project_config))

            cleaned_lines = []
            config_file = os.path.join(project_root, 'config.properties')
            with open(config_file, 'r') as file:
                for line in file:
                    stripped_line = line.strip()

                    if not stripped_line or stripped_line.startswith('#'):
                        continue

                    line = stripped_line.split('#', 1)[0].strip()

                    if line:
                        cleaned_lines.append(line)

            cls._config.read_string('\n'.join(cleaned_lines))

            cls.adjust_config_paths(project_root)

        return cls._config


    @classmethod
    def adjust_config_paths(cls, project_root):
        """
        Adjusts paths in the config to include the hidden folder after 'config.project_root'.

        Modifies the config object in place.
        """
        config = cls._config

        default_configs = configparser.ConfigParser()

        default_dir = os.getcwd()
        os.chdir('/app')

        with open('config/default_configs.properties', 'r') as f:
            file_content = f.read()
            default_configs.read_string(file_content)

        os.chdir(default_dir)

        path_keys = [
            {'DEFAULT': 'config.results_path', 'fallback': 'patches'},
            {'DEFAULT': 'config.jsons_listfile', 'fallback': 'jsons.lists'},
            {'DEFAULT': 'config.issues_path', 'fallback': 'issues.json'},
            {'DEFAULT': 'config.analyzer_results_path', 'fallback': 'symbolic_results'},
        ]

        for path in path_keys:
            for key, value in path.items():
                if default_configs.has_option(key, value):
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
        project_root = os.path.normpath(project_root)
        original_path = os.path.normpath(original_path)

        if os.path.isabs(original_path):
            original_path = os.path.relpath(original_path, project_root)

        new_path = os.path.join(project_root, '.ai4framework', original_path)
        new_path = os.path.normpath(new_path)

        return new_path
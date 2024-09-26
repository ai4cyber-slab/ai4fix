import configparser
import os
from urllib.parse import urlparse
import sys
import openai
import json
import argparse

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
    parser = argparse.ArgumentParser(description='Process some parameters.')
    parser.add_argument('--project-root', '-p', dest='project_root', type=str, help='Path to the project root directory.')
    parser.add_argument('--openai-key', '-k', dest='openai_key', type=str, help='OpenAI API key.')

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
    Reads the config.properties file and extracts all configurations, ignoring section headers.

    Args:
        file_path (str): Path to the config.properties file.

    Returns:
        dict: A dictionary of key-value pairs from the properties file, excluding section headers.
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
                config[key.strip()] = value.strip()

    return config


def map_config_to_vscode_settings(config):
    """
    Maps config.properties keys from the PLUGIN section to VS Code workspace settings keys.

    Args:
        config (dict): Dictionary of configurations from config.properties.

    Returns:
        dict: Dictionary mapped to VS Code workspace settings keys.
    """
    # mappings = {
    #     "plugin.generated_patches_path": "aifix4seccode.analyzer.generatedPatchesPath",
    #     "plugin.issues_path": "aifix4seccode.analyzer.issuesPath",
    #     "plugin.subject_project_path": "aifix4seccode.analyzer.subjectProjectPath",
    #     "plugin.use_diff_mode": "aifix4seccode.analyzer.useDiffMode",
    #     "plugin.executing_parameters": "aifix4seccode.analyzer.executableParameters",
    #     "plugin.executable_path": "aifix4seccode.analyzer.executablePath"
    # }
    mappings = {
        "config.results_path": "aifix4seccode.analyzer.generatedPatchesPath",
        "config.jsons_listfile": "aifix4seccode.analyzer.issuesPath",
        "config.project_path": "aifix4seccode.analyzer.subjectProjectPath",
        "plugin.use_diff_mode": "aifix4seccode.analyzer.useDiffMode",
        "plugin.executing_parameters": "aifix4seccode.analyzer.executableParameters",
        "plugin.executable_path": "aifix4seccode.analyzer.executablePath"
    }

    vscode_settings = {}
    for key, vscode_key in mappings.items():
        if key in config:
            vscode_settings[vscode_key] = config[key]

    return vscode_settings

def update_vscode_workspace_settings(configurations, workspace_path='.'):
    """
    Updates the VS Code workspace settings with the provided configurations.

    Args:
        configurations (dict): A dictionary of settings to be added/updated.
        workspace_path (str): Path to the workspace folder (defaults to current directory).

    Returns:
        None
    """
    # Path to workspace settings file
    settings_dir = os.path.join(workspace_path, '.vscode')
    settings_file = os.path.join(settings_dir, 'settings.json')

    # Ensure .vscode directory exists
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)

    # Load existing settings if they exist
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings_data = json.load(f)
    else:
        settings_data = {}

    # Update settings with new configurations
    settings_data.update(configurations)

    # Write back to the settings.json file
    with open(settings_file, 'w') as f:
        json.dump(settings_data, f, indent=4)

    print(f"VS Code workspace settings updated at: {settings_file}")

def main(config_file, workspace_path='.'):
    """
    Main function to read config.properties, map values to VS Code settings, and update the settings.

    Args:
        config_file (str): Path to the config.properties file.
        workspace_path (str): Path to the workspace folder (defaults to current directory).

    Returns:
        None
    """

    config = read_config_properties(config_file)


    vscode_settings = map_config_to_vscode_settings(config)


    update_vscode_workspace_settings(vscode_settings, workspace_path)





config_file = os.path.join(get_project_root(), 'config.properties')

ConfigManager.load_config(config_file)

main(config_file, get_project_root())
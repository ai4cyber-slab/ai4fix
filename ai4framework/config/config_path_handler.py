import os
import sys


"""
Handles the paths given in the configuration.

Args:
    config (ConfigParser): Configuration object containing necessary settings.
"""
def path_handler(config):
    project_root = config.get("DEFAULT", "config.project_root", fallback='')
    project_dir = config.get("DEFAULT", "config.project_dir", fallback='')

    if project_root == '':
        print('CONFIG.PROJECT_ROOT is not set in the configuration!')
        sys.exit(1)
    
    if project_dir == '':
        return project_root

    # Handle relative paths
    if not os.path.isabs(project_dir):
        project_dir = os.path.join(project_root, project_dir)

    return project_dir
    
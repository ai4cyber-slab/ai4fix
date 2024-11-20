from utils.logger import logger
import git
import os
import sys
import subprocess
from pathlib import Path

class RepoManager:
    """
    A class to manage Git repository operations.

    This class provides methods for checking out specific commits,
    reverting checkouts, getting changed files, and cloning repositories.
    """

    def __init__(self, repo_path, commit_hash):
        """
        Initialize the RepoManager.

        Args:
            repo_path (str): The path to the local Git repository.
            commit_hash (str): The hash of the commit to work with.
        """
        self.repo_path = repo_path
        self.commit_hash = commit_hash


        if not os.path.exists(repo_path):
            raise FileNotFoundError(f"The repository path '{repo_path}' does not exist.")


        try:
            self.repo = git.Repo(repo_path, search_parent_directories=True)
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"'{repo_path}' is not a valid Git repository.")
        except git.exc.NoSuchPathError:
            raise ValueError(f"The path '{repo_path}' does not exist.")

    def checkout_commit(self):
        """
        Checkout a specific commit in the repository.

        Raises:
            Exception: If the checkout operation fails.
        """
        current_commit = self.repo.head.commit
        if current_commit.hexsha == self.commit_hash:
            logger.info(f"Commit {self.commit_hash} is already checked out.")
            return
        logger.info(f"Checking out commit {self.commit_hash}...")
        try:
            self.repo.git.checkout('-f', self.commit_hash)
            logger.info(f"Checked out to commit {self.commit_hash}.")
        except Exception as e:
            logger.error(f"Failed to checkout commit {self.commit_hash}: {e}")
            raise

    def revert_checkout(self):
        """
        Revert to the previous branch or state.

        Raises:
            Exception: If the revert operation fails.
        """
        logger.info("Reverting to the previous branch/state...")
        try:
            self.repo.git.checkout('-')
            logger.info("Reverted to the previous branch/state.")
        except Exception as e:
            logger.error(f"Failed to revert checkout: {e}")
            raise

    def get_files_to_analyze(self, project_root, filter):
        """
        Get a list of files to be analyzed, filtered to ensure to skip certain files.
        
        Args:
            project_root (str): The path to root of the project.
            filter (str): List of words to filter the files.
        
        Returns:
            list: A list of file paths that will be analyzed. 
        """
        try:
            # Determine files based on whether a commit hash is provided
            if self.commit_hash != '':
                repo_path = Path(self.repo_path)

                if not repo_path.is_dir():
                    logger.error(f"The repository directory {repo_path} does not exist.")
                    sys.exit(1)

                commit = self.repo.commit(self.commit_hash)
                all_files = list(commit.stats.files.keys())
            else:
                # Collect all non-hidden files from the project root
                all_files = []
                for dirpath, dirnames, filenames in os.walk(project_root):
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
                    all_files.extend(
                        os.path.join(dirpath, file)
                        for file in filenames
                        if not file.startswith('.') and file.endswith('.java')
                    )

            # Filter files if a filter is provided
            if filter != '':
                filter_words = filter.split(',')
                files_to_analyze = [
                    file_path
                    for file_path in all_files
                    if not any(word in file_path for word in filter_words)
                ]
            else:
                files_to_analyze = all_files

            # Log total number files
            logger.info(f"Number files to be analyzed: {len(files_to_analyze)}")

            return files_to_analyze

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return []

    def get_parent_commit(self):
        """
        Get the parent commit of the specified commit.

        Returns:
            str: The hash of the parent commit, or None if retrieval fails.
        """
        try:
            os.chdir(self.repo.working_tree_dir)

            git_command = ['git', 'log', '--pretty=%P', '-n', '1', self.commit_hash]

            with subprocess.Popen(git_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                stdout, stderr = process.communicate()

            if process.returncode == 0:
                parent_commit = stdout.strip().split()[0]
                logger.info(f"Successfully retrieved the parent commit: {parent_commit}")
                return parent_commit
            else:
                logger.error(f"Failed to retrieve parent commit. Git command returned error code {process.returncode}")
                logger.error(f"Error output: {stderr}")
                return None

        except Exception as e:
            logger.error(f"An error occurred while retrieving the parent commit: {str(e)}")
            return None
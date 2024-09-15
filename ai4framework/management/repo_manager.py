from utils.logger import logger
import git
import os
import sys
import subprocess

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
        self.repo = git.Repo(repo_path)
        self.commit_hash = commit_hash

    def checkout_commit(self):
        """
        Checkout a specific commit in the repository.

        Raises:
            Exception: If the checkout operation fails.
        """
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

    def get_changed_files(self):
        """
        Get a list of files changed in the specified commit.

        Returns:
            list: A list of file paths that were changed in the commit.
        """
        repo_path = self.repo.working_tree_dir
        if not os.path.isdir(repo_path):
            logger.error(f"The directory {repo_path} does not exist.")
            sys.exit(1)
        try:
            commit = self.repo.commit(self.commit_hash)
            changed_files = list(commit.stats.files.keys())
            return changed_files
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
            git_command = f'git log --pretty=%P -n 1 {self.commit_hash}'
            result = subprocess.run(git_command, shell=True, stdout=subprocess.PIPE, text=True)
            parent_commit = result.stdout.strip().split()[0]
            logger.info(f"Successfully retrieved the parent commit: {parent_commit}")
            return parent_commit
        except Exception as e:
            logger.error(f"Failed to retrieve parent commit: {e}")
            return None

    @classmethod
    def clone_repo(cls, remote_url, base_dir):
        """
        Clone a repository from a remote URL.

        Args:
            remote_url (str): The URL of the remote repository to clone.
            base_dir (str): The base directory where the repository should be cloned.

        Returns:
            RepoManager: An instance of RepoManager for the cloned repository.

        Raises:
            Exception: If the cloning operation fails.
        """
        try:
            # Get the repository name from the remote URL
            repo_name = remote_url.rstrip('/').split('/')[-1].replace('.git', '')
            repo_path = os.path.join(base_dir, repo_name)

            # Clone the repo into the base directory
            logger.info(f"Cloning repository from {remote_url} into {repo_path}...")
            repo = git.Repo.clone_from(remote_url, repo_path)
            logger.info(f"Successfully cloned repository into {repo_path}.")

            return cls(repo_path)  # Return an instance of RepoManager for the cloned repo

        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            raise

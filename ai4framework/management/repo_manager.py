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

    # def get_changed_files(self):
    #     """
    #     Get a list of files changed in the specified commit.

    #     Returns:
    #         list: A list of file paths that were changed in the commit.
    #     """
    #     repo_path = self.repo.working_tree_dir
    #     if not os.path.isdir(repo_path):
    #         logger.error(f"The directory {repo_path} does not exist.")
    #         sys.exit(1)
    #     try:
    #         commit = self.repo.commit(self.commit_hash)
    #         changed_files = list(commit.stats.files.keys())
    #         return changed_files
    #     except Exception as e:
    #         logger.error(f"An error occurred: {str(e)}")
    #         return []
    def get_changed_files(self, absolute=True, validation=False):
        """
        Get a list of files changed in the specified commit, filtered to ensure files are under the repository root.
        
        Args:
            absolute (bool, optional): If True, returns absolute paths of the changed files.
                                    If False, returns relative paths from the repository root.
                                    Defaults to True.
        
        Returns:
            list: A list of file paths that were changed in the commit. 
                Paths are absolute if `absolute=True`, otherwise, relative paths are returned.
        """
        repo_path = Path(self.repo_path)
        dirs = [r for r in str(repo_path).split(os.sep) if r != '']
        prefix = ''
        if len(dirs) == 1:
            prefix = 'src'
        elif len(dirs) > 1:
            prefix = os.path.join(*dirs[1:])
        else:
            prefix = ''

        if not repo_path.is_dir():
            logger.error(f"The repository directory {repo_path} does not exist.")
            sys.exit(1)
        test_dir_prefix = str(os.path.join('src','test'))
        try:
            commit = self.repo.commit(self.commit_hash)
            all_changed_files = list(commit.stats.files.keys())
            
            # Filter files that are strictly under the repository path
            changed_files = [
                file_path for file_path in all_changed_files
                if file_path.startswith(prefix)  # Ensure file exists within repo
                and test_dir_prefix not in file_path  # Ensure file is not a test file
            ]
            
            if absolute:
                changed_files = [os.path.join(str(repo_path), file_path[file_path.find('src'):]) for file_path in changed_files if os.path.exists(os.path.join(str(repo_path), file_path[file_path.find('src'):]))]
            if not validation:
                logger.info(f"Total changed files: {len(changed_files)}")
            return changed_files
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return []

    # def get_parent_commit(self):
    #     """
    #     Get the parent commit of the specified commit.

    #     Returns:
    #         str: The hash of the parent commit, or None if retrieval fails.
    #     """
    #     try:
    #         os.chdir(self.repo.working_tree_dir)
    #         git_command = f'git log --pretty=%P -n 1 {self.commit_hash}'
    #         result = subprocess.run(git_command, shell=True, stdout=subprocess.PIPE, text=True)
    #         parent_commit = result.stdout.strip().split()[0]
    #         logger.info(f"Successfully retrieved the parent commit: {parent_commit}")
    #         return parent_commit
    #     except Exception as e:
    #         logger.error(f"Failed to retrieve parent commit: {e}")
    #         return None

    def get_parent_commit(self):
        """
        Get the parent commit of the specified commit.

        Returns:
            str: The hash of the parent commit, or None if retrieval fails.
        """
        try:
            # Change to the repository's working directory
            os.chdir(self.repo.working_tree_dir)

            # Git command to retrieve the parent commit
            git_command = ['git', 'log', '--pretty=%P', '-n', '1', self.commit_hash]

            # Use 'with' to handle the subprocess safely
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

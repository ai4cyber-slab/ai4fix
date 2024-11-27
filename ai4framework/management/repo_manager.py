import git
from pathlib import Path
from utils.logger import logger


class RepoManager:
    """
    A class to manage Git repository operations.

    This class provides methods for checking out specific commits,
    reverting checkouts, getting changed files, and cloning repositories.
    """

    _files_logged_once = False

    def __init__(self, repo_path, commit_hash=None):
        """
        Initialize the RepoManager.

        Args:
            repo_path (str): The path to the local Git repository.
            commit_hash (str, optional): The hash of the commit to work with. Defaults to None.
        """
        self.repo_path = Path(repo_path)
        self.commit_hash = commit_hash

        if not self.repo_path.is_dir():
            raise FileNotFoundError(f"The repository path '{repo_path}' does not exist.")

        try:
            self.repo = git.Repo(self.repo_path, search_parent_directories=True)
        except git.exc.InvalidGitRepositoryError:
            if commit_hash:
                raise ValueError(f"'{repo_path}' is not a valid Git repository. A commit hash requires a valid Git repository.")
            else:
                logger.debug(f"'{repo_path}' is not a valid Git repository. Analyzing the whole project.")
                self.repo = None

    def checkout_commit(self):
        """Checkout a specific commit in the repository."""
        if not self.repo:
            logger.error("Cannot checkout commit. The repository is not a valid Git repository.")
            raise ValueError("Repository is not a valid Git repository.")

        if self.repo.head.commit.hexsha == self.commit_hash:
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
        """Revert to the previous branch or state."""
        if not self.repo:
            logger.error("Cannot revert checkout. The repository is not a valid Git repository.")
            raise ValueError("Repository is not a valid Git repository.")

        logger.info("Reverting to the previous branch/state...")
        try:
            self.repo.git.checkout('-')
            logger.info("Reverted to the previous branch/state.")
        except Exception as e:
            logger.error(f"Failed to revert checkout: {e}")
            raise

    def get_files_to_analyze(self, project_root, filter):
        """
        Get a list of files to be analyzed, filtered to skip certain files.

        Args:
            project_root (str): The path to the project root.
            filter (str): A comma-separated list of words to filter the files.

        Returns:
            list: A list of file paths to be analyzed.
        """
        try:
            if self.repo and self.commit_hash:
                all_files = list(self.repo.commit(self.commit_hash).stats.files.keys())
            else:
                all_files = [
                    str(file)
                    for file in Path(project_root).rglob('*.java')
                    if not file.name.startswith('.')
                ]

            if filter:
                filter_words = {word.strip() for word in filter.split(',')}
                files_to_analyze = [
                    file for file in all_files
                    if not any(word in file for word in filter_words)
                ]
            else:
                files_to_analyze = all_files

            if not RepoManager._files_logged_once:
                logger.info(f"Number of files to be analyzed: {len(files_to_analyze)}")
                RepoManager._files_logged_once = True

            return files_to_analyze

        except Exception as e:
            logger.error(f"Error while getting files to analyze: {str(e)}")
            return []

    def get_parent_commit(self):
        """
        Get the parent commit of the specified commit.

        Returns:
            str: The hash of the parent commit, or None if retrieval fails.
        """
        if not self.repo:
            logger.error("Cannot retrieve parent commit. The repository is not a valid Git repository.")
            raise ValueError("Repository is not a valid Git repository.")

        try:
            parent_commits = self.repo.commit(self.commit_hash).parents
            if parent_commits:
                parent_commit_hash = parent_commits[0].hexsha
                logger.info(f"Successfully retrieved the parent commit: {parent_commit_hash}")
                return parent_commit_hash
            else:
                logger.warning(f"No parent commit found for {self.commit_hash}")
                return None
        except Exception as e:
            logger.error(f"Error while retrieving the parent commit: {str(e)}")
            return None
from utils.logger import logger
import subprocess
import git

class RepositoryManager:
    def __init__(self, repo_path, commit_hash):
        self.repo = git.Repo(repo_path)
        self.commit_hash = commit_hash

    def checkout_commit(self):
        logger.info(f"Checking out commit {self.commit_hash}...")
        try:
            self.repo.git.checkout('-f', self.commit_hash)
            logger.info(f"Checked out to commit {self.commit_hash}.")
        except Exception as e:
            logger.error(f"Failed to checkout commit {self.commit_hash}: {e}")
            raise

    def revert_checkout(self):
        logger.info("Reverting to the previous branch/state...")
        try:
            self.repo.git.checkout('-')
            logger.info("Reverted to the previous branch/state.")
        except Exception as e:
            logger.error(f"Failed to revert checkout: {e}")
            raise

    def get_changed_files(self):
        try:
            result = subprocess.run(
                ['git', 'show', '--name-only', '--pretty=format:', self.commit_hash],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.repo.working_dir,
                text=True,
                check=True
            )
            changed_files = result.stdout.strip().split('\n')
            return changed_files
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred: {e.stderr}")
            return []
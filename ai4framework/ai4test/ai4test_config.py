import configparser
import os

config = configparser.ConfigParser()
config.read("/app/config.properties")

dep_config = configparser.ConfigParser()
dep_config.read("/app/config/dep_config.ini")


project_dir = f"{os.environ.get('PROJECT_PATH')}"
ai4test_dir = f"{os.path.join(project_dir, '.ai4framework', '.ai4test')}"

process_number = eval(config.get("ai4test-defaults", "process_number"))
test_number = 1
max_rounds = eval(config.get("ai4test-defaults", "max_rounds"))
MAX_PROMPT_TOKENS = eval(config.get("ai4test-defaults", "MAX_PROMPT_TOKENS"))
MIN_ERROR_TOKENS = eval(config.get("ai4test-defaults", "MIN_ERROR_TOKENS"))
TIMEOUT = 30

TEMPLATE_NO_DEPS = "d1_4.jinja2"
TEMPLATE_WITH_DEPS = "d3_4.jinja2"
TEMPLATE_ERROR = "error_3.jinja2"


JUNIT_JAR = dep_config.get("DEFAULT", "JUNIT_JAR")
MOCKITO_JAR = dep_config.get("DEFAULT", "MOCKITO_JAR")
LOG4J_JAR = dep_config.get("DEFAULT", "LOG4J_JAR")
JACOCO_AGENT = dep_config.get("DEFAULT", "JACOCO_AGENT")
JACOCO_CLI = dep_config.get("DEFAULT", "JACOCO_CLI")
JUNIT_VERSION = dep_config.get("DEFAULT", "JUNIT_VERSION")
MOCKITO_VERSION = dep_config.get("DEFAULT", "MOCKITO_VERSION")

dataset_dir = f"{os.path.join(ai4test_dir, 'dataset')}"
result_dir = f"{os.path.join(ai4test_dir, 'result')}"

key = config.get("ai4test-model", "key")
model = config.get("ai4test-model", "model")
temperature = 0.5
provider= config.get("ai4test-model", "provider")
azure_endpoint= config.get("ai4test-model", "azure_endpoint")
azure_api_version= config.get("ai4test-model", "azure_api_version")

database_name = config.get("ai4test-database", "database")


def refresh():
    """Refresh dep_config to get latest changes from file."""
    dep_config.read("/app/config/dep_config.ini")
    config.read("/app/config.properties")
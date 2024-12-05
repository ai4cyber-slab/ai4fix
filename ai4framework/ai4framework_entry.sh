#!/usr/bin/env bash

function show_usage {
    echo "Usage: ai4framework_entry.sh --LOCAL_PROJECT_PATH <string> --CONTAINER_PROJECT_PATH <string> [--RunWithBash] [--PORT <int>] [--MAVEN_VERSION <string>] [--GRADLE_VERSION <string>]"
    echo "Options:"
    echo "  --LOCAL_PROJECT_PATH      Path to the local project directory."
    echo "  --CONTAINER_PROJECT_PATH  Path to the project directory inside the container."
    echo "  --RunWithBash             (Optional) Open the container with bash after execution."
    echo "  --PORT                    (Optional) Specify the port number to use for the container. Default is 8080."
    echo "  --MAVEN_VERSION           (Optional) Specify the Maven version. Default is 3.9.5."
    echo "  --GRADLE_VERSION          (Optional) Specify the Gradle version. Default is 7.6."
    echo "  -h, --help                Display this help message."
    exit 0
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) show_usage ;;
        --LOCAL_PROJECT_PATH) LOCAL_PROJECT_PATH="$2"; shift ;;
        --CONTAINER_PROJECT_PATH) CONTAINER_PROJECT_PATH="$2"; shift ;;
        --PORT) PORT="$2"; shift ;;
        --RunWithBash) RUN_WITH_BASH=true ;;
        --MAVEN_VERSION) MAVEN_VERSION="$2"; shift ;;
        --GRADLE_VERSION) GRADLE_VERSION="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; show_usage ;;
    esac
    shift
done

PORT=${PORT:-8080}
MAVEN_VERSION=${MAVEN_VERSION:-3.9.5}
GRADLE_VERSION=${GRADLE_VERSION:-7.6}

if [[ -z "$LOCAL_PROJECT_PATH" || -z "$CONTAINER_PROJECT_PATH" ]]; then
    echo "Error: Missing required parameters."
    show_usage
fi

if [[ ! -d "$LOCAL_PROJECT_PATH" ]]; then
    echo "Error: The local project path '$LOCAL_PROJECT_PATH' is not a directory."
    exit 1
fi

if [[ "$CONTAINER_PROJECT_PATH" != /* ]]; then
    echo "Error: CONTAINER_PROJECT_PATH must be an absolute path (e.g., '/sample_project')."
    exit 1
fi

function show_banner {
    BANNER_PATH="$(dirname "$0")/banner.txt"
    if [[ -f "$BANNER_PATH" ]]; then
        cat "$BANNER_PATH"
    else
        echo "Welcome to SLAB-ai4cyber Framework!"
    fi
}

function manage_config_properties {
    CONFIG_FILE_PATH="$LOCAL_PROJECT_PATH/config.properties"
    DEFAULT_CONTENT="[DEFAULT]
config.filter=
config.rounds_count=1
config.build_tool=maven

[API]
config.provider=openai
config.key=your_api_key
config.model=gpt-4o-mini
config.temperature=0

[PLUGIN]
plugin.use_diff_mode=view Diffs
plugin.script_path=/app"

    if [[ ! -f "$CONFIG_FILE_PATH" ]]; then
        echo "$DEFAULT_CONTENT" > "$CONFIG_FILE_PATH"
        echo "Default 'config.properties' file created at: $CONFIG_FILE_PATH"
    else
        echo "'config.properties' file already exists. Please edit if necessary."
    fi

    if command -v nano &> /dev/null; then
        nano "$CONFIG_FILE_PATH"
    elif command -v vim &> /dev/null; then
        vim "$CONFIG_FILE_PATH"
    else
        echo "Error: No suitable editor found. Install 'nano' or 'vim'." >&2
        exit 1
    fi
}

function validate_config_properties {
    CONFIG_FILE_PATH="$LOCAL_PROJECT_PATH/config.properties"
    ERRORS=()
    CONFIG_CONTENT=$(cat "$CONFIG_FILE_PATH")

    BUILD_TOOL=$(echo "$CONFIG_CONTENT" | grep -E "config.build_tool=" | cut -d'=' -f2 | tr -d ' ')
    PROVIDER=$(echo "$CONFIG_CONTENT" | grep -E "config.provider=" | cut -d'=' -f2 | tr -d ' ')
    KEY=$(echo "$CONFIG_CONTENT" | grep -E "config.key=" | cut -d'=' -f2 | tr -d ' ')
    MODEL=$(echo "$CONFIG_CONTENT" | grep -E "config.model=" | cut -d'=' -f2 | tr -d ' ')

    if [[ ! "$BUILD_TOOL" =~ ^(maven|gradle)$ ]]; then
        ERRORS+=("Invalid 'config.build_tool'. Must be 'maven' or 'gradle'.")
    fi
    if [[ ! "$PROVIDER" =~ ^(openai|groq|claude)$ ]]; then
        ERRORS+=("Invalid 'config.provider'. Must be one of 'openai', 'groq', 'claude'.")
    fi
    if [[ -z "$KEY" || "$KEY" == "None" ]]; then
        ERRORS+=("Invalid 'config.key'. Cannot be empty or 'None'.")
    fi
    if [[ -z "$MODEL" || "$MODEL" == "None" ]]; then
        ERRORS+=("Invalid 'config.model'. Cannot be empty or 'None'.")
    fi

    if [[ ${#ERRORS[@]} -gt 0 ]]; then
        echo "Validation errors found in 'config.properties':"
        for ERROR in "${ERRORS[@]}"; do
            echo "$ERROR"
        done
        exit 1
    fi
    echo "'config.properties' file validated successfully."
}

show_banner

manage_config_properties
validate_config_properties

echo "Building the Docker image with Maven version $MAVEN_VERSION and Gradle version $GRADLE_VERSION..."
docker build --build-arg MAVEN_VERSION=$MAVEN_VERSION --build-arg GRADLE_VERSION=$GRADLE_VERSION -t ai4framework-analyzer .
if [[ $? -ne 0 ]]; then
    echo "Error: Docker image build failed."
    exit 1
fi
echo "Docker image built successfully."

echo "Starting the Docker container..."
if [[ "$RUN_WITH_BASH" == true ]]; then
    CONTAINER_ID=$(docker run -dit -p "$PORT:8080" -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" ai4framework-analyzer bash)
else
    CONTAINER_ID=$(docker run -dit -p "$PORT:8080" -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" ai4framework-analyzer)
fi

if [[ -z "$CONTAINER_ID" ]]; then
    echo "Error: Failed to start the Docker container."
    exit 1
fi
echo "Container started successfully with ID: $CONTAINER_ID"

echo "Copying the project to the container..."
docker cp "$LOCAL_PROJECT_PATH" "$CONTAINER_ID:$CONTAINER_PROJECT_PATH"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy project to the container."
    docker stop "$CONTAINER_ID" > /dev/null
    exit 1
fi
echo "Project copied successfully to the container."

if [[ "$RUN_WITH_BASH" == true ]]; then
    echo "Attaching to the container with bash in $CONTAINER_PROJECT_PATH..."
    docker exec -it -w "$CONTAINER_PROJECT_PATH" "$CONTAINER_ID" bash -c "python /app/orchestrator.py"
else
    echo "Container is running with code-server support. Navigate to http://localhost:$PORT/?folder=$CONTAINER_PROJECT_PATH"
fi
#!/usr/bin/env bash

function show_usage {
    echo "Usage: ai4framework_entry.sh --LOCAL_PROJECT_PATH <string> --CONTAINER_PROJECT_PATH <string> [--RunWithBash] [--PORT <int>] [--MAVEN_VERSION <string>] [--GRADLE_VERSION <string>] [--MAVEN_REPO_PATH <string>]"
    echo "Options:"
    echo "  --LOCAL_PROJECT_PATH      Path to the local project directory."
    echo "  --CONTAINER_PROJECT_PATH  Path to the project directory inside the container."
    echo "  --RunWithBash             (Optional) Open the container with bash after execution."
    echo "  --PORT                    (Optional) Specify the port number to use for the container. Default is 8080."
    echo "  --MAVEN_VERSION           (Optional) Specify the Maven version. Default is 3.9.5."
    echo "  --GRADLE_VERSION          (Optional) Specify the Gradle version. Default is 7.6."
    echo "  --MAVEN_REPO_PATH         (Optional) Path to local Maven repository (.m2 directory)."
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
        --MAVEN_REPO_PATH) MAVEN_REPO_PATH="$2"; shift ;;
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
    TEMPLATE_PATH="$(dirname "$0")/config_template.properties"
    CONFIG_FILE_PATH="$(dirname "$0")/config.properties"
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

    if [[ -f "$TEMPLATE_PATH" ]]; then
        cp "$TEMPLATE_PATH" "$CONFIG_FILE_PATH"
        echo "Created 'config.properties' from template"
    elif [[ -f "$CONFIG_FILE_PATH" ]]; then
        echo "Using existing 'config.properties' file at: $CONFIG_FILE_PATH"
    else
        echo "$DEFAULT_CONTENT" > "$CONFIG_FILE_PATH"
        echo "Default 'config.properties' file created at: $CONFIG_FILE_PATH"
    fi

    if command -v nano &> /dev/null; then
        nano "$CONFIG_FILE_PATH"
    elif command -v vim &> /dev/null; then
        vim "$CONFIG_FILE_PATH"
    else
        echo "Error: No suitable editor found. Install 'nano' or 'vim'." >&2
        exit 1
    fi

    while true; do
        echo -n "Have you finished editing 'config.properties'? (y/n) "
        read -r configDone
        if [[ ! $configDone =~ ^[YyNn]$ ]]; then
            echo "Please enter y or n only."
            continue
        fi
        if [[ $configDone =~ ^[Nn]$ ]]; then
            if command -v nano &> /dev/null; then
                nano "$CONFIG_FILE_PATH"
            elif command -v vim &> /dev/null; then
                vim "$CONFIG_FILE_PATH"
            fi
            continue
        fi
        break
    done

    validate_config_properties "$CONFIG_FILE_PATH"
}

function validate_config_properties {
    CONFIG_FILE_PATH="$(dirname "$0")/config.properties"
    ERRORS=()
    CONFIG_CONTENT=$(cat "$CONFIG_FILE_PATH")

    BUILD_TOOL=""
    PROVIDER=""
    KEY=""
    MODEL=""
    JDK_VERSION=""
    BUILD_MODE=""

    while IFS= read -r line; do
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

        if [[ -z "$line" || "$line" == \#* ]]; then
            continue
        fi

        if [[ $line =~ ^config\.build_tool= ]]; then
            BUILD_TOOL=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        elif [[ $line =~ ^config\.provider= ]]; then
            PROVIDER=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        elif [[ $line =~ ^config\.key= ]]; then
            KEY=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        elif [[ $line =~ ^config\.model= ]]; then
            MODEL=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        elif [[ $line =~ ^config\.jdk_compiler_version= ]]; then
            JDK_VERSION=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        elif [[ $line =~ ^config\.build_mode= ]]; then
            BUILD_MODE=$(echo "${line#*=}" | sed 's/[[:space:]]*#.*//g' | xargs)
        fi
    done <<< "$CONFIG_CONTENT"

    if [[ ! "$BUILD_TOOL" =~ ^(maven|gradle|javac)$ ]]; then
        ERRORS+=("Invalid 'config.build_tool'. Must be 'maven', 'gradle', or 'javac'.")
    fi
    if [[ ! "$PROVIDER" =~ ^(openai|groq|claude|azureopenai)$ ]]; then
        ERRORS+=("Invalid 'config.provider'. Must be one of 'openai', 'groq', 'claude', 'azureopenai'.")
    fi
    if [[ -z "$KEY" || "$KEY" == "None" ]]; then
        ERRORS+=("Invalid 'config.key'. Cannot be empty or 'None'.")
    fi
    if [[ -z "$MODEL" || "$MODEL" == "None" ]]; then
        ERRORS+=("Invalid 'config.model'. Cannot be empty or 'None'.")
    fi
    if [[ ! "$JDK_VERSION" =~ ^(4|5|6|8|11)$ ]]; then
        ERRORS+=("Invalid 'config.jdk_compiler_version'. Must be one of '4', '5', '6', '8', '11'.")
    fi
    if [[ ! "$BUILD_MODE" =~ ^(online|offline)$ ]]; then
        ERRORS+=("Invalid 'config.build_mode'. Must be 'online' or 'offline'.")
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

function validate_maven_repo() {
    local maven_repo_path="$1"
    
    if [[ -n "$maven_repo_path" && ! -d "$maven_repo_path" ]]; then
        echo "Warning: Maven repository path '$maven_repo_path' does not exist."
        echo "Would you like to:"
        echo "1. Use default Maven repository"
        echo "2. Exit and fix the path"
        read -p "Enter your choice (1 or 2): " choice
        
        if [[ "$choice" == "2" ]]; then
            exit 1
        fi
        return 1
    fi
    
    if [[ -n "$maven_repo_path" && ! -f "$maven_repo_path/settings.xml" ]]; then
        echo "Warning: settings.xml not found in Maven repository path"
        return 1
    fi
    
    return 0
}

function validate_port() {
    local port=$1
    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
        echo "Error: Port must be a number between 1024 and 65535"
        return 1
    fi
    
    if command -v nc >/dev/null 2>&1; then
        if nc -z localhost "$port" 2>/dev/null; then
            echo "Error: Port $port is already in use"
            return 1
        fi
    else
        if (echo >/dev/tcp/localhost/$port) 2>/dev/null; then
            echo "Error: Port $port is already in use"
            return 1
        fi
    fi
    
    return 0
}

show_banner

manage_config_properties

echo "Building the Docker image with Maven version $MAVEN_VERSION and Gradle version $GRADLE_VERSION..."
docker build --build-arg MAVEN_VERSION=$MAVEN_VERSION --build-arg GRADLE_VERSION=$GRADLE_VERSION -t ai4framework-analyzer .
if [[ $? -ne 0 ]]; then
    echo "Error: Docker image build failed."
    exit 1
fi
echo "Docker image built successfully."

echo "Starting the Docker container..."
if ! validate_port "$PORT"; then
    echo "Please choose a different port"
    exit 1
fi

DOCKER_RUN_ARGS=("-dit" "-p" "$PORT:8080" "-e" "PROJECT_PATH=$CONTAINER_PROJECT_PATH" "-e" "PORT=8080")

if [[ -n "$MAVEN_REPO_PATH" ]] && validate_maven_repo "$MAVEN_REPO_PATH"; then
    echo "Using Maven repository from: $MAVEN_REPO_PATH"
    DOCKER_RUN_ARGS+=("-v" "$MAVEN_REPO_PATH:/root/.m2")
else
    echo "Using default Maven repository configuration"
fi

if [[ "$RUN_WITH_BASH" == true ]]; then
    DOCKER_RUN_ARGS+=("ai4framework-analyzer" "bash")
else
    DOCKER_RUN_ARGS+=("ai4framework-analyzer")
fi

CONTAINER_ID=$(docker run "${DOCKER_RUN_ARGS[@]}")

if [[ -z "$CONTAINER_ID" ]]; then
    echo "Error: Failed to start the Docker container."
    exit 1
fi
echo "Container started successfully with ID: $CONTAINER_ID"

docker exec -it "$CONTAINER_ID" git config --global --add safe.directory '*' > /dev/null 2>&1
if [[ $? -ne 0 ]]; then
    echo "If required Run this command inside the container: git config --global --add safe.directory '*'"
fi

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
    docker exec -it -w "$CONTAINER_PROJECT_PATH" "$CONTAINER_ID" bash -c "python /app/orchestrator.py; exec bash"
else
    echo "Container is running with code-server support. Navigate to http://localhost:$PORT/?folder=$CONTAINER_PROJECT_PATH"
fi
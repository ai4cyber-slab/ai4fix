#!/usr/bin/env bash


function show_usage {
    echo "Usage: ai4framework_entry.sh --LOCAL_PROJECT_PATH <string> --CONTAINER_PROJECT_PATH <string> [--RunWithBash] [--PORT <int>]"
    echo "Options:"
    echo "  --LOCAL_PROJECT_PATH      Path to the local project directory."
    echo "  --CONTAINER_PROJECT_PATH  Path to the project directory inside the container."
    echo "  --RunWithBash             (Optional) Open the container with bash after execution."
    echo "  --PORT                    (Optional) Specify the port number to use for the container. Default is 8080."
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
        *) echo "Unknown parameter passed: $1"; show_usage ;;
    esac
    shift
done


PORT=${PORT:-8080}


if [[ -z "$LOCAL_PROJECT_PATH" || -z "$CONTAINER_PROJECT_PATH" ]]; then
    echo "Error: Missing required parameters."
    show_usage
fi


if [[ ! -d "$LOCAL_PROJECT_PATH" ]]; then
    echo "Error: The local project path '$LOCAL_PROJECT_PATH' does not exist."
    exit 1
fi

if [[ "$CONTAINER_PROJECT_PATH" != /* ]]; then
    echo "Error: CONTAINER_PROJECT_PATH must be an absolute path (e.g., '/sample_project')."
    exit 1
fi


function show_banner {
    if [[ -f "$(dirname "$0")/banner.txt" ]]; then
        cat "$(dirname "$0")/banner.txt"
    else
        echo "Welcome to SLAB-ai4cyber Framework!"
    fi
}

show_banner

echo ""
echo "Building the Docker image..."
docker build -t code-analyzer-vs-version .
if [[ $? -ne 0 ]]; then
    echo "Error: Docker image build failed."
    exit 1
fi
echo "Docker image built successfully."

echo "Starting the Docker container..."
if [[ "$RUN_WITH_BASH" == true ]]; then
    CONTAINER_ID=$(docker run -dit -p "${PORT}:8080" \
        -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" \
        code-analyzer-vs-version bash)
else
    CONTAINER_ID=$(docker run -dit -p "${PORT}:8080" \
        -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" \
        code-analyzer-vs-version)
fi

if [[ -z "$CONTAINER_ID" ]]; then
    echo "Error: Failed to start the Docker container."
    exit 1
fi
echo "Container started successfully with ID: $CONTAINER_ID"

echo "Copying the project to the container..."
docker cp "$LOCAL_PROJECT_PATH" "${CONTAINER_ID}:${CONTAINER_PROJECT_PATH}"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to copy project to the container."
    docker stop "$CONTAINER_ID" > /dev/null
    exit 1
fi
echo "Project copied successfully to the container."

if [[ "$RUN_WITH_BASH" == true ]]; then
    echo "Attaching to the container with bash in $CONTAINER_PROJECT_PATH..."
    docker exec -it -w "$CONTAINER_PROJECT_PATH" "$CONTAINER_ID" bash
else
    echo "Container is running with code-server support. Navigate to http://localhost:${PORT}/?folder=${CONTAINER_PROJECT_PATH}"
fi
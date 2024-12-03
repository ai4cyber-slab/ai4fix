param(
    [Parameter(Mandatory=$false, HelpMessage="Show usage instructions")]
    [Alias("h", "usage")]
    [switch]$ShowHelp,

    [string]$LOCAL_PROJECT_PATH,
    [string]$CONTAINER_PROJECT_PATH,
    [int]$PORT = 8080,

    [switch]$RunWithBash
)

function Show-Usage {
    Write-Host "Usage: ai4framework_entry.ps1 -LOCAL_PROJECT_PATH <string> -CONTAINER_PROJECT_PATH <string> [-RunWithBash] [-PORT <int>]" -ForegroundColor Cyan
    Write-Host "Options:"
    Write-Host "  -LOCAL_PROJECT_PATH      Path to the local project directory." -ForegroundColor Yellow
    Write-Host "  -CONTAINER_PROJECT_PATH  Path to the project directory inside the container." -ForegroundColor Yellow
    Write-Host "  -RunWithBash             (Optional) Open the container with bash after execution." -ForegroundColor Yellow
    Write-Host "  -PORT                  (Optional) Specify the port number to use for the container. Default is 8080." -ForegroundColor Yellow
    Write-Host "  -h, -usage               Display this help message." -ForegroundColor Yellow
    exit 0
}

if ($ShowHelp) {
    Show-Usage
}


if (-not $LOCAL_PROJECT_PATH -or -not $CONTAINER_PROJECT_PATH) {
    Write-Host "Error: Missing required parameters." -ForegroundColor Red
    Show-Usage
}


if (-not (Test-Path $LOCAL_PROJECT_PATH)) {
    Write-Host "Error: The local project path '$LOCAL_PROJECT_PATH' is not a directory. Check your enviroment variable." -ForegroundColor Red
    exit 1
}


 if ($CONTAINER_PROJECT_PATH -notmatch "^/") {
    Write-Host "Relative path detected for CONTAINER_PROJECT_PATH: $CONTAINER_PROJECT_PATH"
    $CONTAINER_PROJECT_PATH = "/$CONTAINER_PROJECT_PATH"
    Write-Host "Converted to absolute path: $CONTAINER_PROJECT_PATH"
}


function Show-Banner {
    $bannerPath = Join-Path -Path $PSScriptRoot -ChildPath "banner.txt"
    if (Test-Path $bannerPath) {
        Get-Content $bannerPath | ForEach-Object { Write-Host $_ -ForegroundColor Cyan }
    } else {
        Write-Host "Welcome to SLAB-ai4cyber Framework!" -ForegroundColor Green
    }
}


Show-Banner
Write-Host "Building the Docker image..."
docker build -t code-analyzer-vs-version .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker image build failed." -ForegroundColor Red
    exit 1
}
Write-Host "Docker image built successfully."

Write-Host "Starting the Docker container..."
if ($RunWithBash) {
    $ContainerID = docker run -dit -p $PORT`:8080 `
        -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" `
        code-analyzer-vs-version bash
} else {
    $ContainerID = docker run -dit -p $PORT`:8080 `
        -e PROJECT_PATH="$CONTAINER_PROJECT_PATH" `
        code-analyzer-vs-version
}

if (!$ContainerID) {
    Write-Host "Error: Failed to start the Docker container." -ForegroundColor Red
    exit 1
}
Write-Host "Container started successfully with ID: $ContainerID"

Write-Host "Copying the project to the container..."
docker cp "$LOCAL_PROJECT_PATH" "${ContainerID}:$CONTAINER_PROJECT_PATH"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to copy project to the container." -ForegroundColor Red
    docker stop $ContainerID > $null
    exit 1
}
Write-Host "Project copied successfully to the container."

if ($RunWithBash) {
    Write-Host "Attaching to the container, running orchestrator.py in $CONTAINER_PROJECT_PATH..."
    docker exec -it -w "$CONTAINER_PROJECT_PATH" $ContainerID bash -c "python /app/orchestrator.py; exec bash"
} else {
    Write-Host "Container is running with code-server support. Navigate to http://localhost:$PORT/?folder=$CONTAINER_PROJECT_PATH"
}

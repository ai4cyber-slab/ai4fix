param(
    [Parameter(Mandatory=$false, HelpMessage="Show usage instructions")]
    [Alias("h", "usage")]
    [switch]$ShowHelp,

    [string]$LOCAL_PROJECT_PATH,
    [string]$CONTAINER_PROJECT_PATH,
    [int]$PORT = 8080,

    [string]$MAVEN_REPO_PATH,

    [switch]$RunWithBash,

    [string]$MavenVersion = "3.9.5",
    [string]$GradleVersion = "7.6"
)

function Show-Usage {
    Write-Host "Usage: ai4framework_entry.ps1 -LOCAL_PROJECT_PATH <string> -CONTAINER_PROJECT_PATH <string> [-RunWithBash] [-PORT <int>] [-MavenVersion <string>] [-GradleVersion <string>] [-MAVEN_REPO_PATH <string>]" -ForegroundColor Cyan
    Write-Host "Options:"
    Write-Host "  -LOCAL_PROJECT_PATH      Path to the local project directory." -ForegroundColor Yellow
    Write-Host "  -CONTAINER_PROJECT_PATH  Path to the project directory inside the container." -ForegroundColor Yellow
    Write-Host "  -RunWithBash             (Optional) Open the container with bash after execution." -ForegroundColor Yellow
    Write-Host "  -PORT                    (Optional) Specify the port number to use for the container. Default is 8080." -ForegroundColor Yellow
    Write-Host "  -MavenVersion            (Optional) Specify the Maven version. Default is 3.9.5." -ForegroundColor Yellow
    Write-Host "  -GradleVersion           (Optional) Specify the Gradle version. Default is 7.6." -ForegroundColor Yellow
    Write-Host "  -MAVEN_REPO_PATH         (Optional) Path to local Maven repository (.m2 directory)." -ForegroundColor Yellow
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
    Write-Host "Error: The local project path '$LOCAL_PROJECT_PATH' is not a directory. Check your environment variable." -ForegroundColor Red
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

function Configure-GitSafeDirectory {
    try {
        docker exec -it $ContainerID git config --global --add safe.directory '*' > $null 2>&1
    } catch {
        Write-Host "Warning: Failed to configure Git safe directory. run this command inside the container: git config --global --add safe.directory '*'" -ForegroundColor Yellow
    }
}

function Manage-ConfigProperties {
    $templatePath = Join-Path -Path $PSScriptRoot -ChildPath "config_template.properties"
    $configFilePath = Join-Path -Path $PSScriptRoot -ChildPath "config.properties"
    $defaultContent = @"
[DEFAULT]
config.filter= # Words to filter files (if present in file paths, those files will be ignored). Leave empty to analyze all files.
config.rounds_count=1 # Number of times to run the process. Useful for auto patching with '--auto' option.
config.build_tool=maven # (maven, gradle, or javac)

[API]
config.provider=openai # Service to use ('groq', 'openai', 'claude', 'azureopenai')
config.key=your_api_key # Enter your API key directly
config.model=gpt-4o-mini # Desired model name
config.temperature=0 # Desired temperature

[PLUGIN]
plugin.use_diff_mode=view Diffs # Do not change
plugin.script_path=/app # Do not change
"@

    if (Test-Path $templatePath) {
        Copy-Item -Path $templatePath -Destination $configFilePath -Force
        Write-Host "Created 'config.properties' from template" -ForegroundColor Green
    } elseif (Test-Path $configFilePath) {
        Write-Host "Using existing 'config.properties' file at: $configFilePath" -ForegroundColor Green
    } else {
        Set-Content -Path $configFilePath -Value $defaultContent
        Write-Host "Default 'config.properties' file created at: $configFilePath" -ForegroundColor Green
    }

    Start-Process notepad.exe $configFilePath

    do {
        Write-Host "Have you finished editing 'config.properties'? (Y/N)" -ForegroundColor Yellow -NoNewline
        $configDone = Read-Host
        if ($configDone -notmatch '^[YyNn]$') {
            Write-Host "Please enter Y or N only." -ForegroundColor Red
            continue
        }
        if ($configDone -match '^[Nn]$') {
            Start-Process notepad.exe $configFilePath
            continue
        }
        break
    } while ($true)

    Validate-ConfigProperties $configFilePath
}

function Validate-ConfigProperties {
    param (
        [string]$ConfigFilePath
    )

    $configContent = Get-Content $ConfigFilePath
    $errors = @()

    function Get-CleanedValue {
        param ([string]$Line, [string]$Key)

        if ($Line -match "$Key\s*=\s*(.+)") {
            $rawValue = $Matches[1]
            if ($rawValue -match '^(.*?)#') {
                $cleanedValue = $Matches[1]
            } else {
                $cleanedValue = $rawValue
            }
            return $cleanedValue.Trim()
        }
        return $null
    }

    $buildToolValue = $null
    $providerValue = $null
    $keyValue = $null
    $modelValue = $null

    foreach ($line in $configContent) {
        if (-not $line.Trim().StartsWith("#")) {
            if (-not $buildToolValue) {
                $buildToolValue = Get-CleanedValue -Line $line -Key 'config\.build_tool'
            }
            if (-not $providerValue) {
                $providerValue = Get-CleanedValue -Line $line -Key 'config\.provider'
            }
            if (-not $keyValue) {
                $keyValue = Get-CleanedValue -Line $line -Key 'config\.key'
            }
            if (-not $modelValue) {
                $modelValue = Get-CleanedValue -Line $line -Key 'config\.model'
            }
        }
    }

    if (-not ($buildToolValue -in @('maven', 'gradle', 'javac'))) {
        $errors += "Invalid or missing 'config.build_tool'. It must be either 'maven', 'gradle', or 'javac'."
    }

    if (-not ($providerValue -in @('openai', 'groq', 'claude', 'azureopenai'))) {
        $errors += "Invalid or missing 'config.provider'. It must be one of: 'openai', 'groq', 'claude', 'azureopenai'."
    }

    if (-not ($keyValue -and -not [string]::IsNullOrWhiteSpace($keyValue) -and $keyValue -ne "None")) {
        $errors += "Invalid 'config.key'. It cannot be empty, whitespace-only, or set to 'None'."
    }

    if (-not ($modelValue -and -not [string]::IsNullOrWhiteSpace($modelValue) -and $modelValue -ne "None")) {
        $errors += "Invalid 'config.model'. It cannot be empty, whitespace-only, or set to 'None'."
    }

    if ($errors.Count -gt 0) {
        Write-Host "Validation errors found in 'config.properties':" -ForegroundColor Red
        $errors | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Write-Host "Please fix these errors and run the script again." -ForegroundColor Red
        exit 1
    }

    Write-Host "'config.properties' file validated successfully." -ForegroundColor Green
}

function Validate-MavenRepo {
    param([string]$MavenRepoPath)
    
    if ($MavenRepoPath -and -not (Test-Path $MavenRepoPath)) {
        Write-Host "Warning: Maven repository path '$MavenRepoPath' does not exist." -ForegroundColor Yellow
        Write-Host "Would you like to:" -ForegroundColor Yellow
        Write-Host "1. Use default Maven repository" -ForegroundColor Yellow
        Write-Host "2. Exit and fix the path" -ForegroundColor Yellow
        $choice = Read-Host "Enter your choice (1 or 2)"
        
        if ($choice -eq "2") {
            exit 1
        }
        return $false
    }
    
    if ($MavenRepoPath -and -not (Test-Path (Join-Path $MavenRepoPath "settings.xml"))) {
        Write-Host "Warning: settings.xml not found in Maven repository path" -ForegroundColor Yellow
        return $false
    }
    
    return $true
}

Show-Banner

Manage-ConfigProperties

Write-Host "Building the Docker image with Maven version $MavenVersion and Gradle version $GradleVersion..."
docker build --build-arg MAVEN_VERSION=$MavenVersion --build-arg GRADLE_VERSION=$GradleVersion -t ai4framework-analyzer .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Docker image build failed." -ForegroundColor Red
    exit 1
}
Write-Host "Docker image built successfully."

Write-Host "Starting the Docker container..."
$dockerRunArgs = @(
    "-dit"
    "-p", "${PORT}:8080"
    "-e", "PROJECT_PATH=$CONTAINER_PROJECT_PATH"
)

if ($MAVEN_REPO_PATH -and (Validate-MavenRepo $MAVEN_REPO_PATH)) {
    Write-Host "Using Maven repository from: $MAVEN_REPO_PATH" -ForegroundColor Green
    $dockerRunArgs += "-v"
    $dockerRunArgs += "${MAVEN_REPO_PATH}:/root/.m2"
} else {
    Write-Host "Using default Maven repository configuration" -ForegroundColor Yellow
}

if ($RunWithBash) {
    $dockerRunArgs += "ai4framework-analyzer"
    $dockerRunArgs += "bash"
} else {
    $dockerRunArgs += "ai4framework-analyzer"
}

$ContainerID = docker run @dockerRunArgs

if (!$ContainerID) {
    Write-Host "Error: Failed to start the Docker container." -ForegroundColor Red
    exit 1
}
Write-Host "Container started successfully with ID: $ContainerID"

Configure-GitSafeDirectory

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
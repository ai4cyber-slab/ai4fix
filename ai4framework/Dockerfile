# Use the official Python 3.9 image as the base
FROM python:3.9

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies and necessary tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        maven \
        git \
        unzip \
        curl \
        apt-transport-https \
        software-properties-common && \
    # Determine the architecture and set the appropriate JDK download URL
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then \
        JDK_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.17+8/OpenJDK11U-jdk_x64_linux_hotspot_11.0.17_8.tar.gz"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        JDK_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.17+8/OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.17_8.tar.gz"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    # Download and install OpenJDK based on architecture
    wget -O /tmp/openjdk11.tar.gz "$JDK_URL" && \
    mkdir -p /usr/lib/jvm && \
    tar -xzf /tmp/openjdk11.tar.gz -C /usr/lib/jvm && \
    rm -f /tmp/openjdk11.tar.gz && \
    # Identify the extracted JDK directory (handles version updates)
    JDK_DIR=$(ls /usr/lib/jvm | grep 'jdk-11') && \
    if [ -z "$JDK_DIR" ]; then \
        echo "JDK extraction failed." && exit 1; \
    fi && \
    # Update alternatives to use the newly installed JDK
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/$JDK_DIR/bin/java 1 && \
    update-alternatives --set java /usr/lib/jvm/$JDK_DIR/bin/java && \
    # Verify the Java installation
    java -version && \
    # Clean up APT cache to reduce image size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install PMD 7.4.0
RUN wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F7.4.0/pmd-dist-7.4.0-bin.zip -O /tmp/pmd.zip && \
    unzip /tmp/pmd.zip -d /opt/ && \
    rm /tmp/pmd.zip

# Install SpotBugs 4.8.6
RUN wget https://github.com/spotbugs/spotbugs/releases/download/4.8.6/spotbugs-4.8.6.tgz -O /tmp/spotbugs.tgz && \
    tar -xzf /tmp/spotbugs.tgz -C /opt/ && \
    rm /tmp/spotbugs.tgz

# Install Trivy 0.54.1
# Uncomment the following lines if you wish to install Trivy
# RUN wget https://github.com/aquasecurity/trivy/releases/download/v0.54.1/trivy_0.54.1_Linux-64bit.deb -O /tmp/trivy.deb && \
#     dpkg -i /tmp/trivy.deb && \
#     rm /tmp/trivy.deb

# Install code-server
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Install AI4VULN from the .tgz file
# Copy the AI4VULN.tgz file into the container
COPY slab-9.19-d45fdf7b5.tgz /opt/slab-9.19-d45fdf7b5.tgz

# Unzip the AI4VULN.tgz file inside the container and rename the extracted folder to AI4VULN
RUN tar -xvzf /opt/slab-9.19-d45fdf7b5.tgz -C /opt/ && \
    rm /opt/slab-9.19-d45fdf7b5.tgz && \
    mv /opt/slab-9.19-d45fdf7b5 /opt/AI4VULN

# Set environment variables for tool paths
ENV PMD_BIN=/opt/pmd-bin-7.4.0/bin/pmd
ENV SPOTBUGS_BIN=/opt/spotbugs-4.8.6/bin/spotbugs
# ENV TRIVY_BIN=/usr/bin/trivy
ENV ANALYZER_PATH=/opt/AI4VULN
ENV ANALYZER_BIN=/opt/AI4VULN/Java/AnalyzerJava
ENV ANALYZER_RESULTS_PATH=/app/results

# Set permissions for SpotBugs
RUN chmod +x /opt/spotbugs-4.8.6/bin/spotbugs

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code into the container
COPY . /app

# Copy the plugin into the container
COPY aifix4seccode-vscode-1.0.39.vsix /opt/aifix4seccode-vscode-1.0.39.vsix

# Install the VSIX extension using code-server
RUN code-server --install-extension /opt/aifix4seccode-vscode-1.0.39.vsix

# Expose port 8080 for code-server
EXPOSE 8080

# Set the OpenAI API Key as an environment variable (to be provided at runtime)
ENV OPENAI_API_KEY=''

ENV PROJECT_PATH=''

# Start code-server on container launch and set workspace
CMD ["sh", "-c", "code-server --bind-addr 0.0.0.0:8080 --auth none /"]
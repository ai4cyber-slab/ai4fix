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
    wget -O /tmp/openjdk11.tar.gz https://download.java.net/java/GA/jdk11/9/GPL/openjdk-11.0.2_linux-x64_bin.tar.gz && \
    mkdir -p /usr/lib/jvm && \
    tar -xvf /tmp/openjdk11.tar.gz -C /usr/lib/jvm && \
    rm -rf /tmp/openjdk11.tar.gz && \
    ls /usr/lib/jvm/jdk-11.0.2/bin/ && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/jdk-11.0.2/bin/java 1 && \
    update-alternatives --set java /usr/lib/jvm/jdk-11.0.2/bin/java && \
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
RUN wget https://github.com/aquasecurity/trivy/releases/download/v0.54.1/trivy_0.54.1_Linux-64bit.deb -O /tmp/trivy.deb && \
    dpkg -i /tmp/trivy.deb && \
    rm /tmp/trivy.deb

# Install code-server
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Install AI4VULN from the .tgz file
# Copy the AI4VULN.tgz file into the container
COPY AI4VULN.tgz /opt/AI4VULN.tgz

# Unzip the AI4VULN.tgz file inside the container and rename the extracted folder to AI4VULN
RUN tar -xvzf /opt/AI4VULN.tgz -C /opt/ && \
    rm /opt/AI4VULN.tgz && \
    mv /opt/slab-9.19-d45fdf7b5 /opt/AI4VULN


# Set environment variables for tool paths
ENV PMD_BIN=/opt/pmd-bin-7.4.0/bin/pmd
ENV SPOTBUGS_BIN=/opt/spotbugs-4.8.6/bin/spotbugs
ENV TRIVY_BIN=/usr/bin/trivy
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
COPY aifix4seccode-vscode-1.0.36.vsix /opt/aifix4seccode-vscode-1.0.36.vsix

# Install the VSIX extension using code-server
RUN code-server --install-extension /opt/aifix4seccode-vscode-1.0.36.vsix

# Expose port 8080 for code-server
EXPOSE 8080
# Set the OpenAI API Key as an environment variable (to be provided at runtime)
ENV OPENAI_API_KEY=''

ENV PROJECT_PATH=''

# Start code-server on container launch and set workspace
CMD ["sh", "-c", "code-server --bind-addr 0.0.0.0:8080 --auth none /"]
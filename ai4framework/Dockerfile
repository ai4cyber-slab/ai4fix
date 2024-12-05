FROM python:3.9-slim

WORKDIR /app

ARG MAVEN_VERSION=3.9.5
ARG GRADLE_VERSION=7.6
ENV PMD_VERSION=7.4.0
ENV SPOTBUGS_VERSION=4.8.6
ENV MAVEN_HOME=/opt/maven
ENV GRADLE_HOME=/opt/gradle
ENV PMD_BIN=/opt/pmd-bin-${PMD_VERSION}/bin/pmd
ENV SPOTBUGS_BIN=/opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs
ENV ANALYZER_PATH=/opt/AI4VULN
ENV ANALYZER_BIN=/opt/AI4VULN/Java/AnalyzerJava
ENV ANALYZER_RESULTS_PATH=/app/results
ENV PATH="$MAVEN_HOME/bin:$GRADLE_HOME/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        unzip \
        git \
        curl \
        apt-transport-https \
        software-properties-common \
        patch \
        vim \
        nano && \
    mkdir -p /usr/lib/jvm && \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then \
        JDK_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.17+8/OpenJDK11U-jdk_x64_linux_hotspot_11.0.17_8.tar.gz"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        JDK_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.17+8/OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.17_8.tar.gz"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget -q -O - "$JDK_URL" | tar -xzf - -C /usr/lib/jvm && \
    JDK_DIR=$(ls /usr/lib/jvm | grep 'jdk-11') && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/$JDK_DIR/bin/java 1 && \
    update-alternatives --set java /usr/lib/jvm/$JDK_DIR/bin/java && \
    java -version && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN wget https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip -O /tmp/maven.zip && \
    unzip /tmp/maven.zip -d /opt && \
    mv /opt/apache-maven-${MAVEN_VERSION} /opt/maven && \
    rm /tmp/maven.zip && \
    mvn -version

RUN wget https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -O /tmp/gradle.zip && \
    mkdir -p /opt/gradle && \
    unzip /tmp/gradle.zip -d /opt/gradle && \
    mv /opt/gradle/gradle-${GRADLE_VERSION}/* /opt/gradle/ && \
    rm -rf /tmp/gradle.zip /opt/gradle/gradle-${GRADLE_VERSION} && \
    gradle --version

RUN wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip -O /tmp/pmd.zip && \
    unzip /tmp/pmd.zip -d /opt && rm /tmp/pmd.zip

RUN wget https://github.com/spotbugs/spotbugs/releases/download/${SPOTBUGS_VERSION}/spotbugs-${SPOTBUGS_VERSION}.tgz -O /tmp/spotbugs.tgz && \
    tar -xzf /tmp/spotbugs.tgz -C /opt && rm /tmp/spotbugs.tgz && \
    chmod +x /opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs

RUN curl -fsSL https://code-server.dev/install.sh | sh

COPY slab-9.19-d45fdf7b5.tgz /opt/
RUN tar -xvzf /opt/slab-9.19-d45fdf7b5.tgz -C /opt/ && \
    rm /opt/slab-9.19-d45fdf7b5.tgz && \
    mv /opt/slab-9.19-d45fdf7b5 /opt/AI4VULN

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

COPY aifix4seccode-vscode-1.0.39.vsix /opt/
RUN code-server --install-extension /opt/aifix4seccode-vscode-1.0.39.vsix

EXPOSE 8080

ENV PROJECT_PATH=''
ENV USER=user
ENV USERNAME=user

CMD ["sh", "-c", "code-server --bind-addr 0.0.0.0:8080 --auth none /"]
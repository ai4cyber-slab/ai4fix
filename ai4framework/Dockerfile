FROM azul/zulu-openjdk-debian:11-latest

ENV WORKDIR_PATH=/app
WORKDIR ${WORKDIR_PATH}

# Java versions
ENV JAVA_5_VERSION="5.0.22"
ENV JAVA_6_VERSION="6.0.45"
ENV JAVA_8_VERSION="8.0.392"
ENV JAVA_11_VERSION="11.0.21"

# Other version definitions
ARG MAVEN_VERSION=3.9.5
ARG GRADLE_VERSION=7.6
ENV PMD_VERSION=7.4.0
ENV SPOTBUGS_VERSION=4.8.4
ENV FINDSECBUGS_PLUGIN_VERSION=1.12.0
ENV MAVEN_HOME=/opt/maven
ENV GRADLE_HOME=/opt/gradle
ENV PMD_BIN=/opt/pmd-bin-${PMD_VERSION}/bin/pmd
ENV SPOTBUGS_BIN=/opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs
ENV ANALYZER_PATH=/opt/AI4VULN
ENV ANALYZER_BIN=/opt/AI4VULN/Java/AnalyzerJava
ENV ANALYZER_RESULTS_PATH=${WORKDIR_PATH}/results

# Add PORT environment variable with default
ENV PORT=8080

# Initial system setup and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    git \
    curl \
    apt-transport-https \
    software-properties-common \
    patch \
    vim \
    nano \
    python3.11 \
    python3.11-dev \
    python3-pip \
    tar \
    libc6-i386 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3.11 /usr/bin/python

# First copy the JDK files
COPY bins/j2sdk-1_4_2_19-linux-i586.bin /tmp/jdk4.bin
COPY bins/jdk-1_5_0_22-linux-i586.bin /tmp/jdk5.bin
COPY bins/jdk-6u45-linux-i586.bin /tmp/jdk6.bin

# Then use RUN for the installation steps
RUN mkdir -p /usr/lib/jvm && \
    mkdir -p /usr/java && \
    # Install Java 1.4
    cd /tmp && \
    if [ -f jdk4.bin ]; then \
        chmod +x jdk4.bin && \
        (echo yes | ./jdk4.bin || true) && \
        if [ -d j2sdk1.4.2_19 ]; then \
            mv j2sdk1.4.2_19 /usr/java/ ; \
        fi && \
        rm -f jdk4.bin ; \
    fi && \
    # Install Java 5
    if [ -f jdk5.bin ]; then \
        chmod +x jdk5.bin && \
        (echo yes | ./jdk5.bin || true) && \
        if [ -d jdk1.5.0_22 ]; then \
            mv jdk1.5.0_22 /usr/java/ ; \
        fi && \
        rm -f jdk5.bin ; \
    fi && \
    # Install Java 6
    if [ -f jdk6.bin ]; then \
        chmod +x jdk6.bin && \
        (echo yes | ./jdk6.bin || true) && \
        if [ -d jdk1.6.0_45 ]; then \
            mv jdk1.6.0_45 /usr/java/ ; \
        fi && \
        rm -f jdk6.bin ; \
    fi && \
    # Set Java environment variables
    if [ -d /usr/java/j2sdk1.4.2_19 ]; then \
        export JAVA_HOME=/usr/java/j2sdk1.4.2_19 && \
        export PATH=$JAVA_HOME/bin:$PATH && \
        java -version || true ; \
    fi && \
    # Install Java 8
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then \
        JDK8_URL="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_x64_linux_hotspot_8u392b08.tar.gz" && \
        JDK11_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.21%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.21_9.tar.gz"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        JDK8_URL="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_aarch64_linux_hotspot_8u392b08.tar.gz" && \
        JDK11_URL="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.21%2B9/OpenJDK11U-jdk_aarch64_linux_hotspot_11.0.21_9.tar.gz"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget $JDK8_URL -O /tmp/java8.tar.gz || true && \
    if [ -f /tmp/java8.tar.gz ]; then \
        tar -xzf /tmp/java8.tar.gz -C /usr/lib/jvm || true ; \
    fi && \
    wget $JDK11_URL -O /tmp/java11.tar.gz || true && \
    if [ -f /tmp/java11.tar.gz ]; then \
        tar -xzf /tmp/java11.tar.gz -C /usr/lib/jvm || true ; \
    fi && \
    rm -f /tmp/java*.*

# Configure Java alternatives for all tools
RUN for tool in java javac javadoc jar; do \
        if [ -f /usr/lib/jvm/jdk8u392-b08/bin/$tool ]; then \
            update-alternatives --install /usr/bin/$tool $tool /usr/lib/jvm/jdk8u392-b08/bin/$tool 100 || true ; \
        fi && \
        if [ -f /usr/lib/jvm/jdk-11.0.21+9/bin/$tool ]; then \
            update-alternatives --install /usr/bin/$tool $tool /usr/lib/jvm/jdk-11.0.21+9/bin/$tool 200 || true ; \
        fi \
    done && \
    if [ -f /usr/lib/jvm/jdk-11.0.21+9/bin/java ]; then \
        update-alternatives --set java /usr/lib/jvm/jdk-11.0.21+9/bin/java || true ; \
        update-alternatives --set javac /usr/lib/jvm/jdk-11.0.21+9/bin/javac || true ; \
    fi && \
    # Java 1.4, 1.5 and 1.6 have a different directory structure
    if [ -f /usr/java/j2sdk1.4.2_19/bin/java ]; then \
        update-alternatives --install /usr/bin/java java /usr/java/j2sdk1.4.2_19/bin/java 50 || true ; \
        update-alternatives --install /usr/bin/javac javac /usr/java/j2sdk1.4.2_19/bin/javac 50 || true ; \
    fi && \
    if [ -f /usr/java/jdk1.5.0_22/bin/java ]; then \
        update-alternatives --install /usr/bin/java java /usr/java/jdk1.5.0_22/bin/java 75 || true ; \
        update-alternatives --install /usr/bin/javac javac /usr/java/jdk1.5.0_22/bin/javac 75 || true ; \
    fi && \
    if [ -f /usr/java/jdk1.6.0_45/bin/java ]; then \
        update-alternatives --install /usr/bin/java java /usr/java/jdk1.6.0_45/bin/java 85 || true ; \
        update-alternatives --install /usr/bin/javac javac /usr/java/jdk1.6.0_45/bin/javac 85 || true ; \
    fi

# Add script to switch Java versions
RUN echo '#!/bin/bash\n\
case $1 in\n\
    4)\n\
        if [ -d "/usr/java/j2sdk1.4.2_19" ]; then\n\
            update-alternatives --set java /usr/java/j2sdk1.4.2_19/bin/java\n\
            update-alternatives --set javac /usr/java/j2sdk1.4.2_19/bin/javac\n\
            echo "export JAVA_HOME=/usr/java/j2sdk1.4.2_19" > /etc/profile.d/javapath.sh\n\
        else\n\
            echo "Java 4 is not installed - Oracle did not release a version for your architecture"\n\
            exit 1\n\
        fi\n\
        ;;\n\
    5)\n\
        if [ -d "/usr/java/jdk1.5.0_22" ]; then\n\
            update-alternatives --set java /usr/java/jdk1.5.0_22/bin/java\n\
            update-alternatives --set javac /usr/java/jdk1.5.0_22/bin/javac\n\
            echo "export JAVA_HOME=/usr/java/jdk1.5.0_22" > /etc/profile.d/javapath.sh\n\
        else\n\
            echo "Java 5 is not installed - Oracle did not release a version for your architecture"\n\
            exit 1\n\
        fi\n\
        ;;\n\
    6)\n\
        if [ -d "/usr/java/jdk1.6.0_45" ]; then\n\
            update-alternatives --set java /usr/java/jdk1.6.0_45/bin/java\n\
            update-alternatives --set javac /usr/java/jdk1.6.0_45/bin/javac\n\
            echo "export JAVA_HOME=/usr/java/jdk1.6.0_45" > /etc/profile.d/javapath.sh\n\
        else\n\
            echo "Java 6 is not installed - Oracle did not release a version for your architecture"\n\
            exit 1\n\
        fi\n\
        ;;\n\
    8)\n\
        if [ -d "/usr/lib/jvm/jdk8u392-b08" ]; then\n\
            update-alternatives --set java /usr/lib/jvm/jdk8u392-b08/bin/java\n\
            update-alternatives --set javac /usr/lib/jvm/jdk8u392-b08/bin/javac\n\
            echo "export JAVA_HOME=/usr/lib/jvm/jdk8u392-b08" > /etc/profile.d/javapath.sh\n\
        else\n\
            echo "Java 8 is not installed - Oracle did not release a version for your architecture"\n\
            exit 1\n\
        fi\n\
        ;;\n\
    11)\n\
        if [ -d "/usr/lib/jvm/jdk-11.0.21+9" ]; then\n\
            update-alternatives --set java /usr/lib/jvm/jdk-11.0.21+9/bin/java\n\
            update-alternatives --set javac /usr/lib/jvm/jdk-11.0.21+9/bin/javac\n\
            echo "export JAVA_HOME=/usr/lib/jvm/jdk-11.0.21+9" > /etc/profile.d/javapath.sh\n\
        else\n\
            echo "Java 11 is not installed"\n\
            exit 1\n\
        fi\n\
        ;;\n\
    *)\n\
        echo "Usage: switch-java {4|5|6|8|11}"\n\
        exit 1\n\
        ;;\n\
esac\n\
echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/javapath.sh\n\
source /etc/profile.d/javapath.sh\n\
echo "Switched to Java $1: JAVA_HOME=\${JAVA_HOME}"\n\
java -version' > /usr/local/bin/switch-java && \
    chmod +x /usr/local/bin/switch-java

# Install Maven
RUN wget https://archive.apache.org/dist/maven/binaries/apache-maven-${MAVEN_VERSION}-bin.zip -O /tmp/maven.zip || \
    wget https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip -O /tmp/maven.zip && \
    unzip /tmp/maven.zip -d /opt && \
    mv /opt/apache-maven-${MAVEN_VERSION} /opt/maven && \
    rm /tmp/maven.zip

# Install Gradle
RUN wget https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -O /tmp/gradle.zip && \
    unzip /tmp/gradle.zip -d /opt && \
    mv /opt/gradle-${GRADLE_VERSION} /opt/gradle && \
    rm /tmp/gradle.zip

# Create wrapper scripts that source JAVA_HOME
RUN mv /opt/maven/bin/mvn /opt/maven/bin/mvn.real && \
    echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
/opt/maven/bin/mvn.real "$@"' > /opt/maven/bin/mvn && \
    chmod +x /opt/maven/bin/mvn && \
    ln -sf /opt/maven/bin/mvn /usr/local/bin/mvn

RUN mv /opt/gradle/bin/gradle /opt/gradle/bin/gradle.real && \
    echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
/opt/gradle/bin/gradle.real "$@"' > /opt/gradle/bin/gradle && \
    chmod +x /opt/gradle/bin/gradle && \
    ln -sf /opt/gradle/bin/gradle /usr/local/bin/gradle

# Set initial Java environment
RUN echo "export JAVA_HOME=/usr/lib/jvm/jdk-11.0.21+9" > /etc/profile.d/javapath.sh && \
    echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/javapath.sh && \
    echo "source /etc/profile.d/javapath.sh" >> /root/.bashrc

# Add after Java environment setup and before COPY requirements.txt
# Create Maven local repository directory and add default settings
RUN mkdir -p /root/.m2 && \
    echo '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">\n\
</settings>' > /root/.m2/settings.xml

# Add volume mount point for Maven repository
VOLUME ["/root/.m2"]

COPY requirements.txt ${WORKDIR_PATH}/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r ${WORKDIR_PATH}/requirements.txt

# Install PMD
RUN wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip -O /tmp/pmd.zip && \
    unzip /tmp/pmd.zip -d /opt && rm /tmp/pmd.zip

# Install SpotBugs with FindSecBugs
RUN wget https://github.com/spotbugs/spotbugs/releases/download/${SPOTBUGS_VERSION}/spotbugs-${SPOTBUGS_VERSION}.tgz -O /tmp/spotbugs.tgz && \
    tar -xzf /tmp/spotbugs.tgz -C /opt && rm /tmp/spotbugs.tgz && \
    chmod +x /opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs && \
    wget https://repo1.maven.org/maven2/com/h3xstream/findsecbugs/findsecbugs-plugin/${FINDSECBUGS_PLUGIN_VERSION}/findsecbugs-plugin-${FINDSECBUGS_PLUGIN_VERSION}.jar -O /opt/spotbugs-${SPOTBUGS_VERSION}/plugin/findsecbugs-plugin.jar

# Install code-server
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Setup AI4VULN analyzer
COPY slab-9.19-d45fdf7b5.tgz /opt/
RUN tar -xvzf /opt/slab-9.19-d45fdf7b5.tgz -C /opt/ && \
    rm /opt/slab-9.19-d45fdf7b5.tgz && \
    mv /opt/slab-9.19-d45fdf7b5 /opt/AI4VULN

# Configure code-server
RUN mkdir -p /root/.local/share/code-server/User && \
    echo '{ "files.autoSave": "off" }' > /root/.local/share/code-server/User/settings.json

COPY . ${WORKDIR_PATH}

COPY aifix4seccode-vscode-1.0.39.vsix /opt/
RUN code-server --install-extension /opt/aifix4seccode-vscode-1.0.39.vsix

EXPOSE ${PORT}

ENV PROJECT_PATH=''
ENV USER=user
ENV USERNAME=user
# Entrypoint setup
RUN echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
code-server --bind-addr 0.0.0.0:${PORT} --auth none /' > /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

CMD ["/usr/local/bin/docker-entrypoint.sh"]
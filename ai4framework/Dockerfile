FROM azul/zulu-openjdk-debian:11-latest

ENV WORKDIR_PATH=/app
WORKDIR ${WORKDIR_PATH}

# Java versions
ENV JAVA_8_VERSION="8.0.392"
ENV JAVA_11_VERSION="11.0.21"

# Other version definitions
ARG MAVEN_VERSION=3.9.5
ARG GRADLE_VERSION=7.6
ENV PMD_VERSION=7.4.0
ENV SPOTBUGS_VERSION=4.8.6
ENV FINDSECBUGS_PLUGIN_VERSION=1.12.0
ENV MAVEN_HOME=/opt/maven
ENV GRADLE_HOME=/opt/gradle
ENV PMD_BIN=/opt/pmd-bin-${PMD_VERSION}/bin/pmd
ENV SPOTBUGS_BIN=/opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs
ENV ANALYZER_PATH=/opt/AI4VULN
ENV ANALYZER_BIN=/opt/AI4VULN/Java/AnalyzerJava
ENV ANALYZER_RESULTS_PATH=${WORKDIR_PATH}/results

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
    python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3.11 /usr/bin/python

# Install multiple Java versions
RUN mkdir -p /usr/lib/jvm && \
    wget https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u392-b08/OpenJDK8U-jdk_x64_linux_hotspot_8u392b08.tar.gz -O /tmp/java8.tar.gz && \
    tar -xzf /tmp/java8.tar.gz -C /usr/lib/jvm && \
    wget https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.21%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.21_9.tar.gz -O /tmp/java11.tar.gz && \
    tar -xzf /tmp/java11.tar.gz -C /usr/lib/jvm && \
    rm -f /tmp/java*.*

# Configure Java alternatives
RUN update-alternatives --install /usr/bin/java java /usr/lib/jvm/jdk8u392-b08/bin/java 1 && \
    update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/jdk8u392-b08/bin/javac 1 && \
    update-alternatives --install /usr/bin/java java /usr/lib/jvm/jdk-11.0.21+9/bin/java 2 && \
    update-alternatives --install /usr/bin/javac javac /usr/lib/jvm/jdk-11.0.21+9/bin/javac 2 && \
    update-alternatives --set java /usr/lib/jvm/jdk-11.0.21+9/bin/java && \
    update-alternatives --set javac /usr/lib/jvm/jdk-11.0.21+9/bin/javac

# Add script to switch Java versions
RUN echo '#!/bin/bash\n\
case $1 in\n\
    8) update-alternatives --set java /usr/lib/jvm/jdk8u392-b08/bin/java && \
       update-alternatives --set javac /usr/lib/jvm/jdk8u392-b08/bin/javac && \
       echo "export JAVA_HOME=/usr/lib/jvm/jdk8u392-b08" > /etc/profile.d/javapath.sh && \
       echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/javapath.sh ;;\n\
    11) update-alternatives --set java /usr/lib/jvm/jdk-11.0.21+9/bin/java && \
        update-alternatives --set javac /usr/lib/jvm/jdk-11.0.21+9/bin/javac && \
        echo "export JAVA_HOME=/usr/lib/jvm/jdk-11.0.21+9" > /etc/profile.d/javapath.sh && \
        echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/javapath.sh ;;\n\
    *) echo "Usage: switch-java {8|11}" ;;\n\
esac\n\
source /etc/profile.d/javapath.sh\n\
echo "JAVA_HOME=$JAVA_HOME"\n\
java -version' > /usr/local/bin/switch-java && \
    chmod +x /usr/local/bin/switch-java

# Install Maven first
RUN wget https://archive.apache.org/dist/maven/binaries/apache-maven-${MAVEN_VERSION}-bin.zip -O /tmp/maven.zip && \
    unzip /tmp/maven.zip -d /opt && \
    mv /opt/apache-maven-${MAVEN_VERSION} /opt/maven && \
    rm /tmp/maven.zip && \
    ln -s /opt/maven/bin/mvn /usr/local/bin/mvn && \
    mvn -version

# Install Gradle
RUN wget https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -O /tmp/gradle.zip && \
    mkdir -p /opt/gradle && \
    unzip /tmp/gradle.zip -d /opt/gradle && \
    mv /opt/gradle/gradle-${GRADLE_VERSION}/* /opt/gradle/ && \
    rm -rf /tmp/gradle.zip /opt/gradle/gradle-${GRADLE_VERSION} && \
    ln -s /opt/gradle/bin/gradle /usr/local/bin/gradle && \
    gradle --version

ENV PATH="$MAVEN_HOME/bin:$GRADLE_HOME/bin:$PATH"

# Now create the wrapper scripts after Maven and Gradle are installed
RUN mv /usr/local/bin/mvn /usr/local/bin/mvn.real && \
    echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
/usr/local/bin/mvn.real "$@"' > /usr/local/bin/mvn && \
    chmod +x /usr/local/bin/mvn

RUN mv /usr/local/bin/gradle /usr/local/bin/gradle.real && \
    echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
/usr/local/bin/gradle.real "$@"' > /usr/local/bin/gradle && \
    chmod +x /usr/local/bin/gradle

# Create initial Java environment file
RUN echo "export JAVA_HOME=/usr/lib/jvm/jdk-11.0.21+9" > /etc/profile.d/javapath.sh && \
    echo "export PATH=\${JAVA_HOME}/bin:\${PATH}" >> /etc/profile.d/javapath.sh && \
    echo "export MAVEN_OPTS=\"-Dmaven.ext.class.path=\${JAVA_HOME}/lib\"" >> /etc/profile.d/javapath.sh

# Set initial JAVA_HOME and add to bashrc for persistence
ENV JAVA_HOME=/usr/lib/jvm/jdk-11.0.21+9
RUN echo "source /etc/profile.d/javapath.sh" >> /root/.bashrc

COPY requirements.txt ${WORKDIR_PATH}/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r ${WORKDIR_PATH}/requirements.txt

RUN wget https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip -O /tmp/pmd.zip && \
    unzip /tmp/pmd.zip -d /opt && rm /tmp/pmd.zip

RUN wget https://github.com/spotbugs/spotbugs/releases/download/${SPOTBUGS_VERSION}/spotbugs-${SPOTBUGS_VERSION}.tgz -O /tmp/spotbugs.tgz && \
    tar -xzf /tmp/spotbugs.tgz -C /opt && rm /tmp/spotbugs.tgz && \
    chmod +x /opt/spotbugs-${SPOTBUGS_VERSION}/bin/spotbugs && \
    wget https://repo1.maven.org/maven2/com/h3xstream/findsecbugs/findsecbugs-plugin/${FINDSECBUGS_PLUGIN_VERSION}/findsecbugs-plugin-${FINDSECBUGS_PLUGIN_VERSION}.jar -O /opt/spotbugs-${SPOTBUGS_VERSION}/plugin/findsecbugs-plugin.jar

RUN curl -fsSL https://code-server.dev/install.sh | sh

COPY slab-9.19-d45fdf7b5.tgz /opt/
RUN tar -xvzf /opt/slab-9.19-d45fdf7b5.tgz -C /opt/ && \
    rm /opt/slab-9.19-d45fdf7b5.tgz && \
    mv /opt/slab-9.19-d45fdf7b5 /opt/AI4VULN

RUN mkdir -p /root/.local/share/code-server/User

RUN echo '{ "files.autoSave": "off" }' \
    > /root/.local/share/code-server/User/settings.json

COPY . ${WORKDIR_PATH}

COPY aifix4seccode-vscode-1.0.39.vsix /opt/
RUN code-server --install-extension /opt/aifix4seccode-vscode-1.0.39.vsix

EXPOSE 8080

ENV PROJECT_PATH=''
ENV USER=user
ENV USERNAME=user

# Create an entrypoint script
RUN echo '#!/bin/bash\n\
source /etc/profile.d/javapath.sh\n\
code-server --bind-addr 0.0.0.0:8080 --auth none /' > /usr/local/bin/docker-entrypoint.sh && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

# Use the entrypoint script
CMD ["/usr/local/bin/docker-entrypoint.sh"]
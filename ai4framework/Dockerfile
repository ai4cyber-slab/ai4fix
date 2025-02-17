FROM eclipse-temurin:11-jdk-jammy

ENV WORKDIR_PATH=/app
WORKDIR ${WORKDIR_PATH}

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
    python3.10 \
    python3.10-dev \
    python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3.10 /usr/bin/python

COPY requirements.txt ${WORKDIR_PATH}/requirements.txt
RUN pip3 install --no-cache-dir -r ${WORKDIR_PATH}/requirements.txt

RUN wget https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip -O /tmp/maven.zip && \
    unzip /tmp/maven.zip -d /opt && \
    mv /opt/apache-maven-${MAVEN_VERSION} /opt/maven && \
    rm /tmp/maven.zip && \
    ln -s /opt/maven/bin/mvn /usr/local/bin/mvn && \
    mvn -version

RUN wget https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip -O /tmp/gradle.zip && \
    mkdir -p /opt/gradle && \
    unzip /tmp/gradle.zip -d /opt/gradle && \
    mv /opt/gradle/gradle-${GRADLE_VERSION}/* /opt/gradle/ && \
    rm -rf /tmp/gradle.zip /opt/gradle/gradle-${GRADLE_VERSION} && \
    ln -s /opt/gradle/bin/gradle /usr/local/bin/gradle && \
    gradle --version

ENV PATH="$MAVEN_HOME/bin:$GRADLE_HOME/bin:$PATH"

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

CMD ["sh", "-c", "code-server --bind-addr 0.0.0.0:8080 --auth none /"]
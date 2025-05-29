FROM ubuntu:24.04


### set the most important environment variables
ENV SERVER_DIR=/app
WORKDIR ${SERVER_DIR}
ENV USER=root
ENV PROJECT_NAME=stoilo


### install dependencies, time-consuming, so runs in the beginning (caches)
# to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    # human convenience
    less nano net-tools tree git iputils-ping curl \
    # database client side
    mysql-client libmysqlclient-dev \
    # php & apache
    php php-cli php-mysql php-gd php-curl php-xml php-mysqli libapache2-mod-php \
    apache2 subversion \
    # python
    python3 python3-dev python3-pip python-is-python3 \
    # build
    build-essential make g++ pkg-config \
    autoconf automake libtool \
    # OpenSSL
    libssl-dev libcurl4-openssl-dev \
    # deploy
    supervisor cron && \
    # clean apt cache
    apt-get clean
COPY server/deploy/requirements.txt ${SERVER_DIR}/deploy/requirements.txt
# to install python dependencies directly into the docker image (no venv)
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip install --no-cache-dir -r ${SERVER_DIR}/deploy/requirements.txt


### copy and compile boinc, time-consuming, so runs in the beginning (caches)
ENV BOINC_SRC_DIR=${SERVER_DIR}/boinc
COPY boinc/ ${BOINC_SRC_DIR}
RUN cd ${BOINC_SRC_DIR} && \
    ./_autosetup && \
    ./configure --disable-client --disable-manager && \
    make


### declaring env for convenience and copy components
ENV PROJECTS_DIR=${SERVER_DIR}/projects
RUN mkdir -p ${PROJECTS_DIR}
ENV PROJECT_DIR=${PROJECTS_DIR}/${PROJECT_NAME}

ENV WORKERS_DIR=${SERVER_DIR}/workers
COPY workers/apps/ ${WORKERS_DIR}/apps
COPY workers/templates/ ${WORKERS_DIR}/templates
COPY workers/project.xml ${WORKERS_DIR}/project.xml

ENV DEPLOY_DIR=${SERVER_DIR}/deploy
COPY server/deploy/ ${DEPLOY_DIR}

ENV DAEMONS_DIR=${SERVER_DIR}/daemons
COPY server/daemons/ ${DAEMONS_DIR}


### expose ports
EXPOSE 80
EXPOSE ${TASK_SERVICE_PORT}


### start entrypoint
RUN chmod +x ${DEPLOY_DIR}/entrypoint.sh
ENTRYPOINT ["/bin/sh", "-c", "exec \"$DEPLOY_DIR/entrypoint.sh\""]

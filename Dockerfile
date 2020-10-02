FROM python:3.8

LABEL maintainer="Michael Fessenden <michael@mikefez.com>"


ENV RUNNING_IN_DOCKER=true

ENV USERNAME=dev
ENV PUID=1000
ENV PGID=1000
ENV LOGURU_LEVEL=INFO
ENV ENTER=

RUN apt-get update && \
    apt-get -y install cron nano && \
    rm -rf /var/lib/apt/lists/* && \
    crontab -l 2>/dev/null; \
    echo "" | crontab - && \
    touch /var/log/cron.log

RUN groupadd -g ${PGID} ${USERNAME} \
    && useradd -u ${PUID} -g ${USERNAME} -d /home/${USERNAME} ${USERNAME} \
    && mkdir /home/${USERNAME} \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

ADD BackupConductor /opt/BackupConductor

RUN cd /opt/BackupConductor && pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bin/sh", "-c", "cd /opt/BackupConductor \
    && if [ ! -d '/config' ]; then \
        echo '/config directory was not mounted!'; \
    elif [ ! -d '/ssh' ]; then \
        echo '/ssh directory was not mounted!'; \
    else \
        cp -r /ssh ~/.ssh && \
        chown -R $(id -u):$(id -g) ~/.ssh && \
        chown -R $(id -u):$(id -g) ~/.ssh/* && \
        service cron start && \
        pip3 install --no-cache-dir -r requirements.txt && \
        if ! [ -z $ENTER ]; then \
            python3 app.py & \
            /bin/bash; \ 
        else \
            python3 app.py;  \
        fi; \
    fi"]
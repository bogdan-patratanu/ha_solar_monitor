ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    python3 \
    python3-dev \
    openssh \
    openrc \
    rsync

RUN adduser -D app -s /bin/sh -h /app
RUN chown -R app:app /app
RUN rc-update add sshd
RUN rc-status

WORKDIR /app

COPY app /app
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

CMD ["sh", "-c", "touch /run/openrc/softlevel && rc-service sshd start && tail -f /dev/null"]

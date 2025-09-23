# Multi-process container: Telegram Bot API server + Python bot
# Base on image that already contains telegram-bot-api binary
FROM aiogram/telegram-bot-api:latest

# Install Python & build tools (plus xz for extracting static ffmpeg)
RUN apk add --no-cache python3 py3-pip bash curl xz build-base openssl-dev libffi-dev python3-dev \
    && python3 -m venv /opt/venv

# Ensure venv Python & pip are used
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# Install ffmpeg: prefer bundled static archive if present, otherwise install via apk
RUN set -eux; \
    if [ -f /app/ffmpeg-release-amd64-static.tar.xz ]; then \
      mkdir -p /opt/ffmpeg; \
      cd /opt/ffmpeg; \
      xz -d -c /app/ffmpeg-release-amd64-static.tar.xz | tar -x; \
      FF_DIR="$(find /opt/ffmpeg -maxdepth 1 -type d -name 'ffmpeg*amd64*' | head -n1)"; \
      ln -sf "$FF_DIR/ffmpeg" /usr/local/bin/ffmpeg; \
      ln -sf "$FF_DIR/ffprobe" /usr/local/bin/ffprobe; \
    else \
      apk add --no-cache ffmpeg; \
    fi

# Default environment
ENV PYTHONUNBUFFERED=1 \
    HEALTH_PORT=10000

# Start both the Bot API server and the Python bot
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]

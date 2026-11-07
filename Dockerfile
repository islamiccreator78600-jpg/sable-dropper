# Python ka base image (Debian Bookworm)
FROM python:3.11-slim-bookworm

# System dependencies install kar (Java, wget, unzip)
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk-headless \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Apktool install kar
RUN wget -q https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar -O /usr/local/bin/apktool.jar \
    && printf '#!/bin/sh\nexec java -jar /usr/local/bin/apktool.jar "$@"\n' > /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

# Android build-tools (zipalign aur apksigner) install kar
RUN wget -q https://dl.google.com/android/repository/build-tools_r34-linux.zip \
    && unzip -q build-tools_r34-linux.zip -d /opt/android \
    && cp /opt/android/android-14/zipalign /usr/local/bin/ \
    && cp /opt/android/android-14/apksigner /usr/local/bin/ \
    && cp /opt/android/android-14/lib/apksigner.jar /usr/local/bin/ \
    && rm -rf build-tools_r34-linux.zip /opt/android

# Working directory set kar
WORKDIR /app

# Pehle requirements.txt copy kar aur usko install kar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saari files copy kar
COPY . .

# Bot run kar
CMD ["python", "bot.py"]

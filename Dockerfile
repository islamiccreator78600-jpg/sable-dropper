FROM python:3.11-slim-bookworm

# Cache buster
ARG CACHEBUST=1
RUN echo "Cache bust: $CACHEBUST"

# Java aur zaroori tools install kar
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk-headless \
    wget unzip \
    && rm -rf /var/lib/apt/lists/*

# Apktool ko official Bitbucket se download kar (100% reliable)
RUN wget -q https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar -O /usr/local/bin/apktool.jar \
    && wget -q https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool -O /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

# Android build-tools (zipalign & apksigner)
RUN wget -q https://dl.google.com/android/repository/build-tools_r34-linux.zip \
    && unzip -q build-tools_r34-linux.zip -d /opt/android \
    && cp /opt/android/android-14/zipalign /usr/local/bin/ \
    && cp /opt/android/android-14/apksigner /usr/local/bin/ \
    && cp /opt/android/android-14/lib/apksigner.jar /usr/local/bin/ \
    && rm -rf build-tools_r34-linux.zip /opt/android

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "bot.py"]

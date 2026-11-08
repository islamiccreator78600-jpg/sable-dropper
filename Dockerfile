FROM python:3.11-slim-bookworm

# Cache buster
ARG CACHEBUST=1
RUN echo "Cache bust: $CACHEBUST"

# Java, Apktool aur Android tools install kar
RUN apt-get update && apt-get install -y \
    openjdk-17-jdk-headless \
    wget unzip \
    zipalign \
    apksigner \
    && rm -rf /var/lib/apt/lists/*

# Apktool ko official Bitbucket se download kar
RUN wget -q https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.10.0.jar -O /usr/local/bin/apktool.jar \
    && wget -q https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool -O /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "bot.py"]

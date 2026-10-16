FROM python:3.12-slim
LABEL org.opencontainers.image.title="MediaDB" \
      org.opencontainers.image.description="Private Mediendatenbank fürs Heimnetz (Musik, Filme, Serien und Bücher)" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
ENV PYTHONUNBUFFERED=1 PORT=8000 DATA_DIR=/app/data
WORKDIR /app
# ffprobe (aus ffmpeg) liest Aufloesung, Tonspuren und Untertitel aus Filmdateien
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tzdata && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY VERSION LICENSE CHANGELOG.md ./
# Hilfe in der App (/hilfe) zeigt diese Texte an
COPY docs/ANLEITUNG.md docs/MANUAL.md docs/BETRIEB.md docs/DATENQUELLEN_UND_RECHT.md ./docs/
COPY docs/bilder ./docs/bilder
RUN mkdir -p /app/data/covers
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=120s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/healthz'%os.environ.get('PORT','8000'),timeout=4)"
CMD ["sh","-c","exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

#!/bin/sh
# Baut das Docker-Image für amd64 (PC, Server, Proxmox) und arm64 (Raspberry Pi, Mac)
# und lädt es in die Codeberg-Registry hoch. Auf dem Mac im Projektordner ausführen:
#     sh tools/publish.sh
# Einmalig vorher:  docker login codeberg.org   (Benutzername + Zugangstoken, siehe docs/BETRIEB.md)
set -e
cd "$(dirname "$0")/.."
USER_NAME=${CODEBERG_USER:-luro61}
IMAGE=codeberg.org/$USER_NAME/mediadb
V=$(cat VERSION)

echo "Baue $IMAGE:$V (amd64 + arm64). Das dauert beim ersten Mal 5–15 Minuten …"
# Eigener Builder, der mehrere Plattformen kann (wird nur beim ersten Mal angelegt)
docker buildx inspect mediadb-builder >/dev/null 2>&1 || docker buildx create --name mediadb-builder --driver docker-container >/dev/null
docker buildx build --builder mediadb-builder \
  --platform linux/amd64,linux/arm64 \
  -t "$IMAGE:$V" -t "$IMAGE:latest" \
  --push .
echo
echo "Fertig: $IMAGE:$V und $IMAGE:latest sind auf Codeberg."
echo "Im LXC (Dockhand): Stack mediadb → Pull und Redeploy."

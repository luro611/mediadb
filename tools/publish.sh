#!/bin/sh
# Neue Version veröffentlichen. Auf dem Mac im Projektordner ausführen:
#     sh tools/publish.sh            Image bauen und hochladen, Tag pushen, Release anlegen
#     sh tools/publish.sh release    nur Tag und Release (Image ist schon oben)
#
# 1. baut das Docker-Image für amd64 (PC, Server, Proxmox) und arm64 (Raspberry Pi, Mac)
#    und lädt es in die Codeberg-Registry hoch (Tags <Version> und latest)
# 2. legt den Git-Tag v<Version> an und pusht ihn
# 3. legt auf Codeberg das Release an: Text aus CHANGELOG.md, docker-compose.homelab.yml als Anhang
#
# Einmalig vorher (siehe docs/BETRIEB.md):
#   docker login codeberg.org                      (für das Image)
#   für das Release: der Token von docker login (braucht dann auch "repository: Lesen und Schreiben")
#   oder ein eigener Token in ~/.config/mediadb/codeberg-token
set -e
cd "$(dirname "$0")/.."
USER_NAME=${CODEBERG_USER:-luro61}
REPO=$USER_NAME/mediadb
IMAGE=codeberg.org/$REPO
API=https://codeberg.org/api/v1/repos/$REPO
V=$(cat VERSION)
TAG=v$V
TOKEN_FILE=${CODEBERG_TOKEN_FILE:-$HOME/.config/mediadb/codeberg-token}

# Nur veröffentlichen, was auch auf Codeberg liegt: keine offenen Änderungen, alles gepusht
if [ -n "$(git status --porcelain)" ]; then
  echo "Abbruch: Es gibt noch nicht committete Änderungen (git status)."; exit 1
fi
git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "Abbruch: Der aktuelle Stand ist noch nicht zu Codeberg gepusht (git push)."; exit 1
fi
if ! grep -q "^## MediaDB $V " CHANGELOG.md; then
  echo "Abbruch: In CHANGELOG.md fehlt der Abschnitt „## MediaDB $V – …“."; exit 1
fi

# Gibt es den Tag schon für einen anderen Stand, passt das Image nicht dazu (nur Release nachholen ist erlaubt)
if [ "$1" != "release" ] && git rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
   && [ "$(git rev-parse "$TAG^{commit}")" != "$(git rev-parse HEAD)" ]; then
  echo "Abbruch: Den Tag $TAG gibt es schon, aber für einen anderen Stand. VERSION hochzählen?"; exit 1
fi

if [ "$1" != "release" ]; then
  echo "Baue $IMAGE:$V (amd64 + arm64). Das dauert beim ersten Mal 5–15 Minuten …"
  # Eigener Builder, der mehrere Plattformen kann (wird nur beim ersten Mal angelegt)
  docker buildx inspect mediadb-builder >/dev/null 2>&1 || docker buildx create --name mediadb-builder --driver docker-container >/dev/null
  docker buildx build --builder mediadb-builder \
    --platform linux/amd64,linux/arm64 \
    -t "$IMAGE:$V" -t "$IMAGE:latest" \
    --push .
  echo "Image fertig: $IMAGE:$V und $IMAGE:latest sind auf Codeberg."
fi

# Tag
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  git tag -a "$TAG" -m "$(grep -m1 "^## MediaDB $V " CHANGELOG.md | sed 's/^## //')"
fi
git push -q origin "refs/tags/$TAG"
echo "Tag $TAG ist auf Codeberg."

# Release
if [ -n "$CODEBERG_TOKEN" ]; then
  TOKEN=$CODEBERG_TOKEN
elif [ -r "$TOKEN_FILE" ]; then
  TOKEN=$(tr -d ' \r\n' < "$TOKEN_FILE")
elif command -v docker-credential-osxkeychain >/dev/null && \
     TOKEN=$(echo "https://codeberg.org" | docker-credential-osxkeychain get 2>/dev/null \
       | python3 -c 'import json,sys; print(json.load(sys.stdin)["Secret"])' 2>/dev/null) && [ -n "$TOKEN" ]; then
  : # derselbe Token wie bei "docker login codeberg.org" (Schlüsselbund); braucht auch "repository: Lesen und Schreiben"
else
  echo
  echo "Kein Zugangsschlüssel gefunden – das Release bitte von Hand anlegen:"
  echo "https://codeberg.org/$REPO/releases/new?tag=$TAG"
  exit 0
fi
AUTH="Authorization: token $TOKEN"
code=$(curl -s -o /dev/null -w '%{http_code}' -H "$AUTH" "$API/releases/tags/$TAG")
if [ "$code" = "200" ]; then
  echo "Das Release $TAG gibt es schon: https://codeberg.org/$REPO/releases/tag/$TAG"
  exit 0
fi
# Titel und Text aus CHANGELOG.md (Abschnitt dieser Version) als JSON
BODY=$(python3 - "$V" "$TAG" <<'EOF'
import json, re, sys
v, tag = sys.argv[1], sys.argv[2]
text = open('CHANGELOG.md', encoding='utf-8').read()
m = re.search(r'^## (MediaDB ' + re.escape(v) + r' [^\n]*)\n(.*?)(?=^#{1,2} |^---|\Z)', text, re.M | re.S)
print(json.dumps({'tag_name': tag, 'name': m.group(1).strip(), 'body': m.group(2).strip(), 'draft': False, 'prerelease': False}))
EOF
)
OUT=$(mktemp)
code=$(curl -s -o "$OUT" -w '%{http_code}' -X POST -H "$AUTH" -H 'Content-Type: application/json' -d "$BODY" "$API/releases")
if [ "$code" != "201" ]; then
  echo "Das Release konnte nicht angelegt werden (Antwort $code):"; cat "$OUT"; echo
  case "$code" in
    401|403) echo "Der Zugangsschlüssel stimmt nicht oder hat nicht die Berechtigung „repository: Lesen und Schreiben“." ;;
    404) echo "Sind die Releases im Projekt eingeschaltet? Codeberg → mediadb → Einstellungen → Releases." ;;
  esac
  rm -f "$OUT"; exit 1
fi
ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$OUT")
rm -f "$OUT"
curl -s -o /dev/null -f -X POST -H "$AUTH" -F "attachment=@docker-compose.homelab.yml" \
  "$API/releases/$ID/assets?name=docker-compose.homelab.yml" \
  || echo "Hinweis: docker-compose.homelab.yml konnte nicht angehängt werden – bitte von Hand ergänzen."
echo "Release angelegt: https://codeberg.org/$REPO/releases/tag/$TAG"
echo
echo "Im LXC (Dockhand): Stack mediadb → Pull und Redeploy."

#!/bin/sh
# Neue Version veröffentlichen. Auf dem Mac im Projektordner ausführen:
#     sh tools/publish.sh            Image bauen und hochladen, Tag pushen, Release anlegen
#     sh tools/publish.sh release    nur Tag und Release (Image ist schon oben)
#
# 1. baut das Docker-Image für amd64 (PC, Server, Proxmox) und arm64 (Raspberry Pi, Mac)
#    und lädt es in die GitHub-Registry ghcr.io hoch (Tags <Version> und latest)
# 2. legt den Git-Tag v<Version> an und pusht ihn
# 3. legt auf GitHub das Release an: Text aus CHANGELOG.md, docker-compose.homelab.yml als Anhang
#
# Einmalig vorher (siehe docs/BETRIEB.md): GitHub-Programm gh installieren und anmelden,
#   gh auth login  und  gh auth refresh --scopes write:packages
# Die Anmeldung bei ghcr.io für Docker erledigt das Skript selbst mit dem Schlüssel von gh.
set -e
cd "$(dirname "$0")/.."
USER_NAME=${GITHUB_USER:-luro611}
REPO=$USER_NAME/mediadb
IMAGE=ghcr.io/$REPO
V=$(cat VERSION)
TAG=v$V

command -v gh >/dev/null || { echo "Abbruch: Das GitHub-Programm gh fehlt (brew install gh, dann gh auth login)."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Abbruch: gh ist nicht bei GitHub angemeldet (gh auth login)."; exit 1; }

# Nur veröffentlichen, was auch auf GitHub liegt: keine offenen Änderungen, alles gepusht
if [ -n "$(git status --porcelain)" ]; then
  echo "Abbruch: Es gibt noch nicht committete Änderungen (git status)."; exit 1
fi
git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "Abbruch: Der aktuelle Stand ist noch nicht zu GitHub gepusht (git push)."; exit 1
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
  gh auth token | docker login ghcr.io -u "$USER_NAME" --password-stdin >/dev/null \
    || { echo "Abbruch: Anmeldung bei ghcr.io fehlgeschlagen. Fehlt die Berechtigung? gh auth refresh --scopes write:packages"; exit 1; }
  echo "Baue $IMAGE:$V (amd64 + arm64). Das dauert beim ersten Mal 5–15 Minuten …"
  # Eigener Builder, der mehrere Plattformen kann (wird nur beim ersten Mal angelegt)
  docker buildx inspect mediadb-builder >/dev/null 2>&1 || docker buildx create --name mediadb-builder --driver docker-container >/dev/null
  docker buildx build --builder mediadb-builder \
    --platform linux/amd64,linux/arm64 \
    --label "org.opencontainers.image.source=https://github.com/$REPO" \
    --label "org.opencontainers.image.version=$V" \
    -t "$IMAGE:$V" -t "$IMAGE:latest" \
    --push .
  echo "Image fertig: $IMAGE:$V und $IMAGE:latest sind auf GitHub."
fi

# Tag
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
  git tag -a "$TAG" -m "$(grep -m1 "^## MediaDB $V " CHANGELOG.md | sed 's/^## //')"
fi
git push -q origin "refs/tags/$TAG"
echo "Tag $TAG ist auf GitHub."

# Release
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "Das Release $TAG gibt es schon: https://github.com/$REPO/releases/tag/$TAG"
  exit 0
fi
# Titel und Text aus CHANGELOG.md (Abschnitt dieser Version)
NOTES=$(mktemp)
TITLE=$(python3 - "$V" "$NOTES" <<'EOF'
import re, sys
v, out = sys.argv[1], sys.argv[2]
text = open('CHANGELOG.md', encoding='utf-8').read()
m = re.search(r'^## (MediaDB ' + re.escape(v) + r' [^\n]*)\n(.*?)(?=^#{1,2} |^---|\Z)', text, re.M | re.S)
open(out, 'w', encoding='utf-8').write(m.group(2).strip() + '\n')
print(m.group(1).strip())
EOF
)
gh release create "$TAG" -R "$REPO" --verify-tag --latest --title "$TITLE" --notes-file "$NOTES" docker-compose.homelab.yml
rm -f "$NOTES"
echo "Release angelegt: https://github.com/$REPO/releases/tag/$TAG"
echo
echo "Im LXC (Dockhand): Stack mediadb → Pull und Redeploy."

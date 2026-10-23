#!/usr/bin/env bash
# Downloads the public datasets used to build data/verses.json and data/lexicon_brief.json
# into scripts/sources/ (git-ignored). Requires Node/npm and curl.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p sources && cd sources
[ -f package.json ] || npm init -y >/dev/null
npm install --silent --save-exact \
  es-kjv@1.0.2 \
  @metaxia/scriptures-source-crosswire-kjv@2.0.2 \
  @metaxia/scriptures-source-stepbible-lexicon@2.0.3
# World English Bible (public domain), one JSON file
curl -fsSL -o web.json \
  https://raw.githubusercontent.com/midvash/bible-data/main/versions/en/web/web.json
echo "Sources ready in $(pwd)"

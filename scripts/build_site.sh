#!/bin/sh
# Assembles the static dashboard: web/ files at the root, data/*.json under /data.
set -e
rm -rf _site
mkdir -p _site/data
cp web/* _site/
for f in data/*.json; do
  [ -e "$f" ] && cp "$f" _site/data/
done
echo "built _site: $(ls _site | tr '\n' ' ')"

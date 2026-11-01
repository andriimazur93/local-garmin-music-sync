#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
: "${CIQ_SDK_HOME:?Set CIQ_SDK_HOME to the installed Connect IQ SDK}"
: "${GARMIN_SIGNING_KEY:?Set GARMIN_SIGNING_KEY to the existing Store signing key}"
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
    echo 'Release builds require a clean tracked and untracked working tree.' >&2
    exit 1
fi
if [[ ! -f "$GARMIN_SIGNING_KEY" || ! -x "$CIQ_SDK_HOME/bin/monkeyc" ]]; then
    echo 'Connect IQ compiler or signing key is unavailable.' >&2
    exit 1
fi
output="$root/dist/watch-release"
if [[ -e "$output" ]]; then
    echo 'Release output already exists; move it before building again.' >&2
    exit 1
fi
mkdir -p "$root/dist"
temp=$(mktemp -d "$root/dist/.watch-release.XXXXXXXX")
trap 'rm -rf -- "$temp"' EXIT
mkdir "$temp/source" "$temp/output"
git archive HEAD | tar -x -C "$temp/source"
python3 "$temp/source/scripts/generate-watch-version.py" "$temp/source/watch/manifest.xml" "$temp/source/watch/resources/strings/version.xml"
revision=$(git rev-parse HEAD)
version=$(python3 -c 'import sys,xml.etree.ElementTree as E; print(E.parse(sys.argv[1]).getroot()[0].attrib["version"])' "$temp/source/watch/manifest.xml")
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} -Djava.awt.headless=true"
cd "$temp/source/watch"
"$CIQ_SDK_HOME/bin/monkeyc" -f monkey.jungle -d fr955 -y "$GARMIN_SIGNING_KEY" -o "$temp/output/garmin-sync-fr955.prg" -w
"$CIQ_SDK_HOME/bin/monkeyc" -e -f monkey.jungle -d fr955 -y "$GARMIN_SIGNING_KEY" -o "$temp/output/garmin-sync-fr955.iq" -w
cd "$temp/output"
sha256sum garmin-sync-fr955.prg > garmin-sync-fr955.prg.sha256
sha256sum garmin-sync-fr955.iq > garmin-sync-fr955.iq.sha256
printf 'Source commit: %s\nApp version: %s\nTarget: fr955\n' "$revision" "$version" > build-info.txt
mv -- "$temp/output" "$output"
printf 'Prepared watch release in %s\n' "$output"

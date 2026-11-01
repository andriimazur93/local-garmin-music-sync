#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
runner="$root/.local/actions-runner"
if [[ ! -x "$runner/config.sh" || ! -f "$runner/release.env" ]]; then
    echo 'Install the runner and prepare its private release.env first; see README.' >&2
    exit 1
fi
cd "$runner"
repo=$(cd "$root" && gh repo view --json nameWithOwner --jq .nameWithOwner)
if [[ -f .runner ]]; then
    runner_id=$(python3 -c 'import json; print(json.load(open(".runner", encoding="utf-8-sig"))["agentId"])')
    if ! response=$(gh api "repos/$repo/actions/runners/$runner_id" 2>&1); then
        if [[ "$response" == *'HTTP 404'* ]]; then
            echo 'Runner registration is no longer available; re-registering.'
            rm -- .runner
        else
            echo 'Could not check runner registration; leaving it unchanged.' >&2
            exit 1
        fi
    fi
fi
if [[ ! -f .runner ]]; then
    token=$(gh api -X POST "repos/$repo/actions/runners/registration-token" --jq .token)
    ./config.sh --unattended --url "https://github.com/$repo" --token "$token" --name garmin-release-local --labels garmin-release --ephemeral
    unset token
fi
exec ./run.sh

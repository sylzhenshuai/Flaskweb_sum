#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "update aborted: tracked files are not clean" >&2
    exit 1
fi

if [[ ! -f .env && -z "${MYSQL_PASSWORD:-}" ]]; then
    echo "update aborted: copy .env.example to .env and set MYSQL_PASSWORD" >&2
    exit 1
fi

git pull --ff-only
docker compose config --quiet
docker compose up --build -d
docker compose ps

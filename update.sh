#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

create_env() {
    local db_password="${MYSQL_PASSWORD:-}"
    local secret_key

    if [[ -z "$db_password" ]]; then
        if [[ ! -t 0 ]]; then
            echo "update aborted: set MYSQL_PASSWORD or run interactively" >&2
            exit 1
        fi
        read -r -s -p "MySQL password for test_user: " db_password
        printf '\n'
    fi

    if [[ -z "$db_password" || "$db_password" == *"'"* || "$db_password" == *$'\n'* || "$db_password" == *$'\r'* ]]; then
        echo "update aborted: MYSQL_PASSWORD is empty or contains unsupported characters" >&2
        exit 1
    fi

    secret_key="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
    umask 077
    printf '%s\n' \
        "SECRET_KEY=$secret_key" \
        "MYSQL_HOST=mysql-server" \
        "MYSQL_PORT=3306" \
        "MYSQL_DATABASE=test_db" \
        "MYSQL_USER=test_user" \
        "MYSQL_PASSWORD='$db_password'" \
        "CONTAINER_TZ=Asia/Shanghai" > .env
    unset db_password
    echo "created local deployment config: .env"
}

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "update aborted: tracked files are not clean" >&2
    exit 1
fi

git pull --ff-only

if [[ ! -f .env ]]; then
    create_env
fi

docker compose config --quiet
docker compose up --build -d
docker compose ps

#!/usr/bin/env bash
# Run on the Ubuntu server after `docker compose up -d --build` and Nginx
# configuration. Fails fast on any unhealthy service or unexpected response.
set -euo pipefail

domain="${1:-acewin-group.top}"

docker compose ps
test "$(docker compose ps --status running --services | wc -l | tr -d ' ')" -ge 3
curl --fail --silent --show-error http://127.0.0.1:8000/api/health >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8000/api/ready >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8080/ >/dev/null
curl --fail --silent --show-error --location "https://${domain}/" >/dev/null
curl --fail --silent --show-error "https://${domain}/api/ready" >/dev/null

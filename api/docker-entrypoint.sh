#!/bin/sh
# Hosts like Render mount the data disk owned by root. Start as root, hand the data folder to
# appuser, then drop privileges so the app itself never runs as root.
set -e
DATA="${DATA_DIR:-/srv/data}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA" /srv/mlruns
  find "$DATA" /srv/mlruns ! -user appuser -exec chown appuser:appuser {} +
  exec setpriv --reuid=1000 --regid=1000 --init-groups "$@"
fi
exec "$@"

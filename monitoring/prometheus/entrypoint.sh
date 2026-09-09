#!/bin/sh
set -eu
umask 077
printf '%s' "$METRICS_TOKEN" > /tmp/metrics-token
exec /bin/prometheus --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/prometheus --storage.tsdb.retention.time=15d

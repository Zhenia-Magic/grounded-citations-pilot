#!/usr/bin/env bash
# Pull (once) and start GROBID with the light CRF models, then wait until it answers.
#
# WSL stops Ubuntu after a short idle spell when no WSL window or command is attached, and
# that stops every container. --restart unless-stopped makes Docker bring GROBID back on the
# next start of WSL; `docker stop grobid` keeps it off (it uses about 2-4 GB of RAM).
set -euo pipefail
IMAGE=grobid/grobid:0.9.1-crf

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "pulling $IMAGE (about 0.5 GB compressed)..."
  docker pull -q "$IMAGE"
fi
if [ -n "$(docker ps -aq -f name=^grobid$)" ]; then
  docker start grobid >/dev/null
else
  docker run -d --init --ulimit core=0 --restart unless-stopped --name grobid -p 8070:8070 "$IMAGE" >/dev/null
fi
for i in $(seq 1 60); do
  if curl -s localhost:8070/api/isalive | grep -q true; then
    echo "GROBID alive after $((i * 5))s"
    docker ps --filter name=grobid --format '{{.Names}}  {{.Image}}  {{.Status}}'
    exit 0
  fi
  sleep 5
done
echo "GROBID did not come up within 5 minutes; container logs:" >&2
docker logs --tail 40 grobid >&2
exit 1

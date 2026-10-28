#!/usr/bin/env bash
# Isolated smoke test: production entrypoint, empty PostgreSQL, retained levels.
set -euo pipefail
fluilet_image=${1:-fluilet-backend:ci}
fluilet_id="fluilet-smoke-${GITHUB_RUN_ID:-local}-$$"
fluilet_api="${fluilet_id}-api"
fluilet_db="${fluilet_id}-db"
fluilet_tmp=$(mktemp -d)
cleanup() {
  docker rm -fv "$fluilet_api" "$fluilet_db" >/dev/null 2>&1 || true
  docker network rm "$fluilet_id" >/dev/null 2>&1 || true
  rm -rf "$fluilet_tmp"
}
trap cleanup EXIT
umask 077
cat > "$fluilet_tmp/env" <<'ENV'
SECRET_KEY=ci-container-key-000000000000000000000000000000000000
POSTGRES_PASSWORD=ContainerDb2026!
DATABASE_URL=postgresql+psycopg://fluilet:ContainerDb2026%21@db:5432/fluilet
DEPLOYMENT_ENV=production
DEMO_ACCOUNTS_ENABLED=true
DEMO_TUTOR_PASSWORD=ContainerTutor2026!
DEMO_MASTER_PASSWORD=ContainerMaster2026!
MT5_ENABLED=false
WIKIPEDIA_ENABLED=false
ENV
FLUILET_ENV_FILE="$fluilet_tmp/env" docker compose --env-file "$fluilet_tmp/env" config --quiet
docker network create "$fluilet_id" >/dev/null
docker run -d --name "$fluilet_db" --network "$fluilet_id" --network-alias db \
  --tmpfs /var/lib/postgresql:rw -e POSTGRES_USER=fluilet -e POSTGRES_DB=fluilet \
  -e 'POSTGRES_PASSWORD=ContainerDb2026!' postgres:18 >/dev/null
for fluilet_attempt in $(seq 1 60); do
  if docker exec "$fluilet_db" pg_isready -h 127.0.0.1 -U fluilet -d fluilet >/dev/null 2>&1; then break; fi
  sleep 1
done
docker run -d --name "$fluilet_api" --network "$fluilet_id" --env-file "$fluilet_tmp/env" \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m --cap-drop ALL \
  --security-opt no-new-privileges:true -p 127.0.0.1::8000 "$fluilet_image" >/dev/null
fluilet_address=$(docker port "$fluilet_api" 8000/tcp)
fluilet_ready=false
for fluilet_attempt in $(seq 1 90); do
  if curl --silent --fail "http://$fluilet_address/health/ready" > "$fluilet_tmp/ready"; then fluilet_ready=true; break; fi
  sleep 1
done
if [ "$fluilet_ready" != true ]; then docker logs "$fluilet_api"; exit 1; fi
fluilet_token=$(curl --silent --show-error --fail -X POST "http://$fluilet_address/api/v1/auth/login" \
  --data-urlencode 'username=tutor@fluilet.com' --data-urlencode 'password=ContainerTutor2026!' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl --silent --show-error --fail "http://$fluilet_address/api/v1/adaptations/model-info" \
  -H "Authorization: Bearer $fluilet_token" > "$fluilet_tmp/model.json"
for fluilet_level in 5 1; do
  curl --silent --show-error --fail -X POST "http://$fluilet_address/api/v1/adaptations/generate" \
    -H "Authorization: Bearer $fluilet_token" -H 'Content-Type: application/json' \
    --data "{\"category\":\"deportes\",\"custom_topic\":\"Real Madrid\",\"level\":$fluilet_level}" \
    > "$fluilet_tmp/level-$fluilet_level.json"
done
fluilet_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$fluilet_tmp/level-5.json")
curl --silent --show-error --fail "http://$fluilet_address/api/v1/adaptations/$fluilet_version" \
  -H "Authorization: Bearer $fluilet_token" > "$fluilet_tmp/retained.json"
python3 - "$fluilet_tmp" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); model=json.loads((root/'model.json').read_text())
assert model['model_version']=='context-ranker-es-v2.2' and model['active']
expected=json.loads(Path('checkpoints/retraining_metrics.json').read_text())
assert model['artifact_sha256']==expected['artifact_sha256']
for level in (1,5):
    data=json.loads((root/f'level-{level}.json').read_text())
    preview=data['level_previews'][level-1]
    assert data['target_level']==level
    assert data['adapted_text']==preview['adapted_text']
    assert data['readability_score']==preview['readability_score']
assert json.loads((root/'retained.json').read_text())==json.loads((root/'level-5.json').read_text())
print('Production container: migrations, demo login, checkpoint and retained levels PASS')
PY
docker exec "$fluilet_api" python -m alembic check

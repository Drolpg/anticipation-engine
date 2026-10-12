#!/usr/bin/env bash
# Roda NA INSTANCIA (enviado pelo deploy.sh via SSM). Gera o .env, sobe o compose e espera a API ficar saudavel.
# Variaveis esperadas: AWS_REGION e POSTGRES_PASSWORD_PARAMETER.
set -euo pipefail

cd /opt/app

senha="$(aws ssm get-parameter --region "${AWS_REGION}" --name "${POSTGRES_PASSWORD_PARAMETER}" \
  --with-decryption --query Parameter.Value --output text)"

umask 077
cat > .env <<ENV
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${senha}
POSTGRES_DB=anticipation
APP_ENV=production
LOG_LEVEL=INFO
API_BIND=0.0.0.0
API_PORT=80
ENV
umask 022

docker compose up -d --build --remove-orphans

echo "Aguardando a API ficar saudavel..."
for _ in $(seq 1 60); do
  if curl -fsS http://localhost/health > /dev/null 2>&1; then
    echo "API no ar:"
    curl -fsS http://localhost/health
    echo
    docker image prune -f > /dev/null
    docker compose ps
    exit 0
  fi
  sleep 5
done

echo "A API nao ficou saudavel em 5 minutos. Ultimos logs:" >&2
docker compose logs --tail 80 >&2
exit 1

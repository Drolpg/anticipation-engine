#!/usr/bin/env bash
# Deploy da demo na AWS (CloudFormation + EC2 via SSM). Rode a partir de qualquer pasta do projeto.
#
#   deploy/aws/deploy.sh up         cria a infraestrutura e publica a versao atual do codigo
#   deploy/aws/deploy.sh deploy     publica o codigo de novo (infraestrutura ja existe)
#   deploy/aws/deploy.sh status     estado da stack, da instancia e da API
#   deploy/aws/deploy.sh url        mostra a URL publica
#   deploy/aws/deploy.sh logs [svc] ultimos logs (api, worker, db, redis)
#   deploy/aws/deploy.sh stop       para a instancia (deixa de pagar computacao)
#   deploy/aws/deploy.sh start      liga de novo (os containers sobem sozinhos)
#   deploy/aws/deploy.sh destroy    apaga TUDO (pede confirmacao; --yes pula)
#
# Variaveis opcionais: AWS_REGION (padrao us-east-1), STACK_NAME, INSTANCE_TYPE, ALLOWED_CIDR,
# ou a flag --my-ip em "up" para liberar a porta 80 so para o seu IP.
set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash no Windows: nao reescrever argumentos que parecem caminhos

STACK="${STACK_NAME:-anticipation-engine}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t4g.small}"
ALLOWED_CIDR="${ALLOWED_CIDR:-0.0.0.0/0}"
PASSWORD_PARAMETER="${STACK}-postgres-password"
BUNDLE=".deploy-bundle.tgz"
SSM_INPUT=".deploy-ssm.json"

aws_() { aws --region "${REGION}" "$@"; }
log() { printf '\n==> %s\n' "$*"; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
trap 'rm -f "${BUNDLE}" "${SSM_INPUT}"' EXIT

preflight() {
  command -v aws > /dev/null || die "AWS CLI nao encontrada. Veja o passo a passo (instalacao)."
  command -v tar > /dev/null || die "tar nao encontrado (no Windows use o Git Bash)."
  aws_ sts get-caller-identity > /dev/null 2>&1 || die "Credenciais AWS invalidas. Rode 'aws configure'."
}

stack_output() {
  aws_ cloudformation describe-stacks --stack-name "${STACK}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

ensure_password() {
  if aws_ ssm get-parameter --name "${PASSWORD_PARAMETER}" > /dev/null 2>&1; then
    return
  fi
  log "Gerando a senha do banco (Parameter Store, SecureString)"
  local senha
  senha="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" # hexadecimal: seguro dentro da URL do banco
  aws_ ssm put-parameter --name "${PASSWORD_PARAMETER}" --type SecureString --value "${senha}" > /dev/null
}

wait_for_ssm() {
  local id="$1" estado=""
  log "Aguardando a instancia ficar acessivel pelo SSM (primeira vez leva alguns minutos)"
  for _ in $(seq 1 60); do
    estado="$(aws_ ssm describe-instance-information --filters "Key=InstanceIds,Values=${id}" \
      --query 'InstanceInformationList[0].PingStatus' --output text 2> /dev/null || true)"
    [ "${estado}" = "Online" ] && return
    sleep 10
  done
  die "A instancia nao ficou Online no SSM em 10 minutos."
}

# Executa um script na instancia e imprime a saida. Uso: run_remote "<comandos em bash>"
run_remote() {
  local id comando_id estado
  id="$(stack_output InstanceId)"
  wait_for_ssm "${id}"
  printf '{"InstanceIds":["%s"],"DocumentName":"AWS-RunShellScript","TimeoutSeconds":1800,' "${id}" > "${SSM_INPUT}"
  printf '"Parameters":{"executionTimeout":["1800"],"commands":[%s]}}' "$1" >> "${SSM_INPUT}"
  comando_id="$(aws_ ssm send-command --cli-input-json "file://${SSM_INPUT}" --query Command.CommandId --output text)"
  for _ in $(seq 1 180); do
    estado="$(aws_ ssm get-command-invocation --command-id "${comando_id}" --instance-id "${id}" \
      --query Status --output text 2> /dev/null || echo Pending)"
    case "${estado}" in
      Pending | InProgress | Delayed) sleep 10 ;;
      *) break ;;
    esac
  done
  aws_ ssm get-command-invocation --command-id "${comando_id}" --instance-id "${id}" \
    --query StandardOutputContent --output text
  if [ "${estado}" != "Success" ]; then
    aws_ ssm get-command-invocation --command-id "${comando_id}" --instance-id "${id}" \
      --query StandardErrorContent --output text >&2
    die "O comando remoto terminou com estado ${estado}."
  fi
}

publish() {
  local bucket
  bucket="$(stack_output PackageBucket)"
  log "Empacotando o codigo (sem .git, .venv e .env)"
  tar --exclude=.git --exclude=.venv --exclude=.env --exclude='.deploy-*' --exclude=docs/local \
    --exclude=__pycache__ --exclude=.pytest_cache --exclude=.ruff_cache --exclude=.coverage \
    -czf "${BUNDLE}" . || [ $? -eq 1 ] # codigo 1 = apenas aviso (o proprio pacote cresce dentro da pasta)
  aws_ s3 cp "${BUNDLE}" "s3://${bucket}/app.tgz" --only-show-errors

  log "Publicando na instancia (build da imagem + docker compose up)"
  run_remote "\"export HOME=/root AWS_REGION=${REGION} POSTGRES_PASSWORD_PARAMETER=${PASSWORD_PARAMETER}\",\
\"cloud-init status --wait || true\",\
\"aws s3 cp s3://${bucket}/app.tgz /tmp/app.tgz --region ${REGION} --only-show-errors\",\
\"find /opt/app -mindepth 1 -maxdepth 1 -exec rm -rf {} +\",\
\"tar xzf /tmp/app.tgz -C /opt/app\",\
\"sed -i 's/\\\\r\$//' /opt/app/deploy/aws/remote-deploy.sh\",\
\"bash /opt/app/deploy/aws/remote-deploy.sh\""
  echo
  echo "Pronto. API:  $(stack_output ApiUrl)"
  echo "      Docs: $(stack_output DocsUrl)"
}

confirm_destroy() {
  [ "${1:-}" = "--yes" ] && return
  local resposta
  printf 'Isto apaga a instancia, o banco e todos os dados da stack "%s" em %s. Digite o nome da stack para confirmar: ' "${STACK}" "${REGION}"
  read -r resposta
  [ "${resposta}" = "${STACK}" ] || die "Cancelado."
}

comando="${1:-}"
[ -n "${comando}" ] && shift
case "${comando}" in
  up)
    preflight
    if [ "${1:-}" = "--my-ip" ]; then
      ALLOWED_CIDR="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')/32"
      echo "Porta 80 liberada apenas para ${ALLOWED_CIDR}"
    fi
    ensure_password
    log "Criando/atualizando a stack ${STACK} em ${REGION}"
    aws_ cloudformation deploy --stack-name "${STACK}" --template-file deploy/aws/template.yaml \
      --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset \
      --parameter-overrides "ProjectName=${STACK}" "InstanceType=${INSTANCE_TYPE}" \
      "AllowedCidr=${ALLOWED_CIDR}" "PostgresPasswordParameter=${PASSWORD_PARAMETER}"
    publish
    ;;
  deploy)
    preflight
    publish
    ;;
  status)
    preflight
    aws_ cloudformation describe-stacks --stack-name "${STACK}" --query 'Stacks[0].StackStatus' --output text
    aws_ ec2 describe-instances --instance-ids "$(stack_output InstanceId)" \
      --query 'Reservations[0].Instances[0].State.Name' --output text
    curl -fsS --max-time 10 "$(stack_output ApiUrl)/health" && echo || echo "API nao respondeu."
    ;;
  url)
    preflight
    stack_output ApiUrl
    stack_output DocsUrl
    ;;
  logs)
    preflight
    run_remote "\"cd /opt/app && docker compose logs --tail 100 ${1:-}\""
    ;;
  stop)
    preflight
    aws_ ec2 stop-instances --instance-ids "$(stack_output InstanceId)" --query 'StoppingInstances[0].CurrentState.Name' --output text
    ;;
  start)
    preflight
    aws_ ec2 start-instances --instance-ids "$(stack_output InstanceId)" --query 'StartingInstances[0].CurrentState.Name' --output text
    echo "Em 1-2 minutos a API volta sozinha em $(stack_output ApiUrl)"
    ;;
  destroy)
    preflight
    confirm_destroy "${1:-}"
    bucket="$(stack_output PackageBucket)"
    log "Esvaziando o bucket e apagando a stack"
    aws_ s3 rm "s3://${bucket}" --recursive --only-show-errors || true
    aws_ cloudformation delete-stack --stack-name "${STACK}"
    aws_ cloudformation wait stack-delete-complete --stack-name "${STACK}"
    aws_ ssm delete-parameter --name "${PASSWORD_PARAMETER}" > /dev/null 2>&1 || true
    echo "Tudo removido."
    ;;
  *)
    sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac

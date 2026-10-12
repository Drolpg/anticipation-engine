"""RNF-10 — contrato do IaC de deploy na AWS (deploy/aws). Lê arquivos; não precisa de conta AWS nem de Docker."""

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
AWS = RAIZ / "deploy" / "aws"


class _Loader(yaml.SafeLoader):
    """Entende as tags do CloudFormation (!Ref, !Sub, !GetAtt...) sem resolvê-las."""


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node)}
    return {suffix: loader.construct_mapping(node)}


_Loader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template():
    return yaml.load((AWS / "template.yaml").read_text(encoding="utf-8"), Loader=_Loader)


def _recursos(template, tipo):
    return {nome: r for nome, r in template["Resources"].items() if r["Type"] == tipo}


def test_arquivos_do_deploy_existem():
    for nome in ("template.yaml", "deploy.sh", "remote-deploy.sh"):
        assert (AWS / nome).is_file(), nome


def test_template_cria_o_necessario_para_a_demo(template):
    tipos = {r["Type"] for r in template["Resources"].values()}

    assert {
        "AWS::EC2::Instance",
        "AWS::EC2::SecurityGroup",
        "AWS::EC2::EIP",
        "AWS::IAM::Role",
        "AWS::IAM::InstanceProfile",
        "AWS::S3::Bucket",
    } <= tipos


def test_custo_minimo_uma_instancia_pequena_arm(template):
    permitidos = template["Parameters"]["InstanceType"]["AllowedValues"]

    assert template["Parameters"]["InstanceType"]["Default"] == "t4g.small"
    assert all(t.startswith("t4g.") for t in permitidos)  # Graviton: mais barato e a AMI é arm64
    assert len(_recursos(template, "AWS::EC2::Instance")) == 1
    for tipo_caro in ("AWS::RDS::DBInstance", "AWS::ElastiCache::CacheCluster", "AWS::EC2::NatGateway"):
        assert not _recursos(template, tipo_caro), f"{tipo_caro} custa caro para uma demo"


def test_security_group_so_abre_a_porta_80(template):
    (sg,) = _recursos(template, "AWS::EC2::SecurityGroup").values()
    regras = sg["Properties"]["SecurityGroupIngress"]

    assert [(r["FromPort"], r["ToPort"]) for r in regras] == [(80, 80)]  # sem SSH (22): acesso por SSM
    assert regras[0]["CidrIp"] == {"Ref": "AllowedCidr"}


def test_acesso_administrativo_e_por_ssm_sem_chave_ssh(template):
    (instancia,) = _recursos(template, "AWS::EC2::Instance").values()
    (papel,) = _recursos(template, "AWS::IAM::Role").values()

    assert "KeyName" not in instancia["Properties"]
    assert "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" in papel["Properties"]["ManagedPolicyArns"]


def test_instancia_com_imdsv2_e_disco_criptografado(template):
    (instancia,) = _recursos(template, "AWS::EC2::Instance").values()
    props = instancia["Properties"]

    assert props["MetadataOptions"]["HttpTokens"] == "required"
    assert props["BlockDeviceMappings"][0]["Ebs"]["Encrypted"] is True


def test_bucket_do_pacote_e_privado(template):
    (bucket,) = _recursos(template, "AWS::S3::Bucket").values()
    bloqueio = bucket["Properties"]["PublicAccessBlockConfiguration"]

    assert all(bloqueio[k] is True for k in bloqueio) and len(bloqueio) == 4


def test_nenhum_segredo_no_template_nem_nos_scripts():
    padrao_chave_aws = re.compile(r"AKIA[0-9A-Z]{16}|aws_secret_access_key\s*=", re.IGNORECASE)
    for arquivo in AWS.iterdir():
        texto = arquivo.read_text(encoding="utf-8")
        assert not padrao_chave_aws.search(texto), arquivo.name
        assert "POSTGRES_PASSWORD=" not in texto.replace("POSTGRES_PASSWORD=${", ""), arquivo.name


def test_senha_do_banco_vem_do_parameter_store(template):
    (papel,) = _recursos(template, "AWS::IAM::Role").values()
    politicas = str(papel["Properties"]["Policies"])

    assert "ssm:GetParameter" in politicas
    assert "NoEcho" not in str(template["Parameters"]), "a senha não passa pelo CloudFormation"


@pytest.mark.parametrize("script", ["deploy.sh", "remote-deploy.sh"])
def test_scripts_param_ao_primeiro_erro(script):
    texto = (AWS / script).read_text(encoding="utf-8")

    assert texto.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in texto
    assert "\r" not in texto, "CRLF quebra scripts bash"


def test_deploy_oferece_os_comandos_do_ciclo_de_vida():
    texto = (AWS / "deploy.sh").read_text(encoding="utf-8")

    for comando in ("up", "deploy", "status", "logs", "stop", "start", "destroy"):
        assert re.search(rf"^\s*{comando}\)", texto, re.MULTILINE), comando


def test_destroy_pede_confirmacao():
    texto = (AWS / "deploy.sh").read_text(encoding="utf-8")

    assert "--yes" in texto and "read -r" in texto


def test_artefatos_temporarios_do_deploy_nao_sao_versionados():
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".deploy-*" in linhas
    assert "docs/local/" in linhas

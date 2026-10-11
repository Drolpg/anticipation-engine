"""Validação e normalização de CNPJ (RN-01).

Implementação pura sem dependências externas utilizando o algoritmo do Módulo 11.
"""

PESOS_PRIMEIRO_DIGITO = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
PESOS_SEGUNDO_DIGITO = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def validar_cnpj(valor: str) -> str:
    """Valida e normaliza um CNPJ para apenas 14 dígitos numéricos.

    Regras (RN-01):
    - Aceita formatado (ex: 11.222.333/0001-81) ou apenas dígitos.
    - Espaços nas extremidades são ignorados.
    - Deve conter exatamente 14 dígitos após remoção dos separadores padrão ('.', '/', '-').
    - Caracteres não numéricos fora dos separadores padrão levantam ValueError.
    - Sequências de dígitos repetidos (ex: 11111111111111, 00000000000000) são inválidas.
    - Os dois dígitos verificadores são calculados via Módulo 11.

    Retorna:
        str: CNPJ normalizado contendo apenas os 14 dígitos.

    Raises:
        ValueError: Se o CNPJ for inválido por formato, tamanho ou dígito verificador.
    """
    if not isinstance(valor, str):
        raise ValueError("CNPJ deve ser uma string.")

    texto = valor.strip()
    if not texto:
        raise ValueError("CNPJ não pode ser vazio.")

    digitos = []
    for caractere in texto:
        if caractere.isdigit():
            digitos.append(caractere)
        elif caractere in {".", "/", "-"}:
            continue
        else:
            raise ValueError(f"Caractere inválido no CNPJ: '{caractere}'.")

    cnpj_limpo = "".join(digitos)

    if len(cnpj_limpo) != 14:
        raise ValueError("CNPJ deve conter exatamente 14 dígitos numéricos.")

    if len(set(cnpj_limpo)) == 1:
        raise ValueError("CNPJ não pode conter todos os dígitos iguais.")

    # Cálculo do 1º dígito verificador (Módulo 11)
    soma_d1 = sum(int(d) * p for d, p in zip(cnpj_limpo[:12], PESOS_PRIMEIRO_DIGITO, strict=True))
    resto_d1 = soma_d1 % 11
    d1 = 0 if resto_d1 < 2 else 11 - resto_d1

    if int(cnpj_limpo[12]) != d1:
        raise ValueError("Dígito verificador do CNPJ inválido.")

    # Cálculo do 2º dígito verificador (Módulo 11)
    soma_d2 = sum(int(d) * p for d, p in zip(cnpj_limpo[:13], PESOS_SEGUNDO_DIGITO, strict=True))
    resto_d2 = soma_d2 % 11
    d2 = 0 if resto_d2 < 2 else 11 - resto_d2

    if int(cnpj_limpo[13]) != d2:
        raise ValueError("Dígito verificador do CNPJ inválido.")

    return cnpj_limpo

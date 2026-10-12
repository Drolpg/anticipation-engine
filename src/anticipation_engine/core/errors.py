"""Exceções de negócio e aplicação padronizadas para a API."""

from typing import Any


class AppError(Exception):
    """Exceção base para erros previstos da aplicação com envelope estável.

    Attributes:
        status_code: Código de status HTTP retornado ao cliente.
        code: Identificador textual estável do erro (ex: TITULO_NAO_ENCONTRADO).
        message: Mensagem amigável para o cliente (sem detalhes internos).
        details: Lista opcional de detalhes específicos (ex: campos inválidos).
    """

    def __init__(
        self,
        message: str = "Erro na aplicação.",
        code: str = "APP_ERROR",
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class TituloNaoEncontrado(AppError):
    """Lançada quando uma consulta de título por ID não encontra registros."""

    def __init__(self, message: str = "Título não encontrado.") -> None:
        super().__init__(
            message=message,
            code="TITULO_NAO_ENCONTRADO",
            status_code=404,
        )


class FilaIndisponivel(AppError):
    """Lançada quando o enfileiramento falha após o título ter sido persistido."""

    def __init__(self, message: str = "Serviço de mensageria temporariamente indisponível.") -> None:
        super().__init__(
            message=message,
            code="FILA_INDISPONIVEL",
            status_code=503,
        )

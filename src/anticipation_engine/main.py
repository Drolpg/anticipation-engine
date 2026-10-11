from fastapi import FastAPI

app = FastAPI(title="Motor de Antecipação de Recebíveis")


@app.get("/")
def status_engine() -> dict[str, str]:
    return {"status": "Motor Online e aguardando requisições"}

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Ledger API", version="0.2.0")

@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ledger_app.api.routes_accounts import router as accounts_router

app = FastAPI(title="Ledger API", version="0.1.0")

@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    """Simple health endpoint. Extend later to check DB connectivity."""
    return JSONResponse({"status": "ok"})

# Mount routers
app.include_router(accounts_router)

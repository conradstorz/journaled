from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.exc import SQLAlchemyError
from ledger_app.db import SessionLocal
from ledger_app.api.routes_accounts import router as accounts_router

app = FastAPI(title="Journaled API", version="0.2.0")

@app.get("/", response_class=HTMLResponse, tags=["system"])
def landing_page():
    """
    Landing page for the Journaled API.
    """
    return """
    <html>
        <head>
            <title>Journaled API</title>
        </head>
        <body>
            <h1>Welcome to the Journaled API</h1>
            <p>See <a href="/docs">/docs</a> for interactive API documentation.</p>
            <p>Health check: <a href="/health">/health</a></p>
        </body>
    </html>
    """

@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    """
    Health endpoint that checks database connectivity.
    """
    db_status = "ok"
    try:
        db = SessionLocal()
        # Try a simple query (e.g., SELECT 1)
        db.execute("SELECT 1")
    except SQLAlchemyError as e:
        db_status = f"error: {str(e)}"
    finally:
        if 'db' in locals():
            db.close()
    return JSONResponse({"status": "ok", "database": db_status})

# Mount routers
app.include_router(accounts_router)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from journaled_app.db import SessionLocal
from sqlalchemy import text
from journaled_app.api.routes_accounts import router as accounts_router
from journaled_app.api.routes_transactions import router as transactions_router
from journaled_app.services.posting import UnbalancedTransactionError

app = FastAPI(title="Journaled API", version="0.2.0")

@app.get("/", response_class=HTMLResponse, tags=["system"])
def landing_page():
    """
    Landing page for the Journaled API.
    """
    return """
    <html>
      <head>
        <title>Journaled - MVP Landing</title>
                <meta name='viewport' content='width=device-width, initial-scale=1'>
                <style>
                    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; margin: 0; padding: 0; }
                    .container { max-width: 600px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }
                    h1 { color: #2c3e50; margin-top: 0; }
                    nav { margin: 24px 0; }
                    nav a { display: inline-block; margin: 0 12px 12px 0; padding: 10px 18px; background: #2c3e50; color: #fff; border-radius: 4px; text-decoration: none; font-weight: 500; transition: background 0.2s; }
                    nav a:hover { background: #34495e; }
                    .desc { color: #555; margin-bottom: 24px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Welcome to Journaled</h1>
                    <div class="desc">This is the MVP landing page for your accounting API.<br>Navigate below to explore features and documentation.</div>
                    <nav>
                        <a href="/docs">API Docs</a>
                        <a href="/health">Health Check</a>
                        <a href="/accounts">Accounts</a>
                        <a href="/transactions">Transactions</a>
                    </nav>
                    <p style="font-size:0.95em;color:#888;">Journaled &copy; 2025 &mdash; MVP Demo</p>
                </div>
            </body>
        </html>
        """

@app.get("/health", tags=["system"])
def health() -> JSONResponse:
    """
    Health endpoint that checks database connectivity.
    """
    db_status = "ok"
    db = None
    try:
        db = SessionLocal()
        # Try a simple query (e.g., SELECT 1)
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        db_status = f"error: {str(e)}"
    finally:
            if db is not None:
                db.close()
    return JSONResponse({"status": "ok", "database": db_status})

@app.exception_handler(UnbalancedTransactionError)
def unbalanced_transaction_exception_handler(request: Request, exc: UnbalancedTransactionError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.exception_handler(IntegrityError)
def integrity_error_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Database integrity error: " + str(exc.orig)}
    )

# Mount routers
app.include_router(accounts_router)
app.include_router(transactions_router)

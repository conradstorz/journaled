from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from journaled_app.db import SessionLocal
from sqlalchemy import text
from journaled_app.api.routes_accounts import router as accounts_router
from journaled_app.api.routes_transactions import router as transactions_router
from journaled_app.services.posting import UnbalancedTransactionError


from fastapi import Form, status
from fastapi.responses import RedirectResponse
from journaled_app.models import User
from sqlalchemy.orm import Session
import hashlib

app = FastAPI(title="Journaled API", version="0.2.0")

@app.get("/", response_class=HTMLResponse, tags=["system"])
def landing_page():
    """
    Landing page for the Journaled API.
    """
    return """
        <html>
            <head>
                <title>Journaled - Login</title>
                <meta name='viewport' content='width=device-width, initial-scale=1'>
                <style>
                    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; margin: 0; padding: 0; }
                    .container { max-width: 400px; margin: 60px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }
                    h1 { color: #2c3e50; margin-top: 0; }
                    form { margin-top: 24px; }
                    label { display: block; margin-bottom: 8px; color: #555; }
                    input[type=text], input[type=password] { width: 100%; padding: 10px; margin-bottom: 16px; border-radius: 4px; border: 1px solid #ccc; }
                    button { background: #2c3e50; color: #fff; border: none; padding: 10px 18px; border-radius: 4px; font-weight: 500; cursor: pointer; }
                    button:hover { background: #34495e; }
                    .desc { color: #555; margin-bottom: 24px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Login to Journaled</h1>
                    <div class="desc">Sign in to access your accounting dashboard.</div>
                    <form method="post" action="/login">
                        <label for="username">Username</label>
                        <input type="text" id="username" name="username" required>
                        <label for="password">Password</label>
                        <input type="password" id="password" name="password" required>
                        <button type="submit">Login</button>
                    </form>
                    <p style="font-size:0.95em;color:#888;">Journaled &copy; 2025 &mdash; MVP Demo</p>
                </div>
            </body>
        </html>
        """
# --- Login endpoint ---
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()
    user = db.query(User).filter_by(username=username).first()
    db.close()
    if not user:
        return HTMLResponse("<h2>Invalid username or password</h2><a href='/'>Back</a>", status_code=status.HTTP_401_UNAUTHORIZED)
    # Simple password check (hash for MVP)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user.password_hash != password_hash:
        return HTMLResponse("<h2>Invalid username or password</h2><a href='/'>Back</a>", status_code=status.HTTP_401_UNAUTHORIZED)
    # On success, redirect to dashboard (for MVP, /accounts)
    response = RedirectResponse(url="/accounts", status_code=status.HTTP_302_FOUND)
    # TODO: Set session/cookie for persistent login
    return response

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

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from journaled_app.db import SessionLocal
from sqlalchemy import text
from journaled_app.api.routes_accounts import router as accounts_router
from journaled_app.api.routes_transactions import router as transactions_router
from journaled_app.api.routes_auth import router as auth_router
from journaled_app.services.posting import UnbalancedTransactionError
from journaled_app.api.deps import get_current_active_user
from journaled_app.models import User

app = FastAPI(title="Journaled API", version="0.2.0")

@app.get("/login", response_class=HTMLResponse, tags=["system"])
def login_page():
    """
    Public login page for unauthenticated users.
    """
    return """
    <html>
      <head>
        <title>Journaled - Login</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
            .container { max-width: 400px; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }
            h1 { color: #2c3e50; margin-top: 0; text-align: center; }
            form { display: flex; flex-direction: column; }
            input { margin-bottom: 16px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
            button { padding: 12px; background: #2c3e50; color: #fff; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; transition: background 0.2s; }
            button:hover { background: #34495e; }
            .register-link { text-align: center; margin-top: 16px; }
            .register-link a { color: #2c3e50; text-decoration: none; }
            .register-link a:hover { text-decoration: underline; }
            .error { color: #e74c3c; margin-bottom: 16px; text-align: center; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Login to Journaled</h1>
          <div id="error" class="error" style="display: none;"></div>
          <form id="loginForm">
            <input type="text" id="username" placeholder="Username" required>
            <input type="password" id="password" placeholder="Password" required>
            <button type="submit">Login</button>
          </form>
          <div class="register-link">
            Don't have an account? <a href="/register">Register here</a>
          </div>
        </div>
        <script>
          document.getElementById('loginForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            try {{
              const response = await fetch('/auth/login', {{
                method: 'POST',
                headers: {{
                  'Content-Type': 'application/x-www-form-urlencoded',
                }},
                body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
              }});
              
              if (response.ok) {{
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                window.location.href = '/';
              }} else {{
                const error = await response.json();
                document.getElementById('error').textContent = error.detail || 'Login failed';
                document.getElementById('error').style.display = 'block';
              }}
            }} catch (error) {{
              document.getElementById('error').textContent = 'Network error. Please try again.';
              document.getElementById('error').style.display = 'block';
            }}
          }});
        </script>
      </body>
    </html>
    """

@app.get("/register", response_class=HTMLResponse, tags=["system"])
def register_page():
    """
    Public registration page for new users.
    """
    return """
    <html>
      <head>
        <title>Journaled - Register</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
            .container { max-width: 400px; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }
            h1 { color: #2c3e50; margin-top: 0; text-align: center; }
            form { display: flex; flex-direction: column; }
            input { margin-bottom: 16px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px; }
            button { padding: 12px; background: #27ae60; color: #fff; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; transition: background 0.2s; }
            button:hover { background: #229954; }
            .login-link { text-align: center; margin-top: 16px; }
            .login-link a { color: #2c3e50; text-decoration: none; }
            .login-link a:hover { text-decoration: underline; }
            .error { color: #e74c3c; margin-bottom: 16px; text-align: center; }
            .success { color: #27ae60; margin-bottom: 16px; text-align: center; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Register for Journaled</h1>
          <div id="error" class="error" style="display: none;"></div>
          <div id="success" class="success" style="display: none;"></div>
          <form id="registerForm">
            <input type="text" id="username" placeholder="Username" required>
            <input type="email" id="email" placeholder="Email" required>
            <input type="password" id="password" placeholder="Password" required>
            <button type="submit">Register</button>
          </form>
          <div class="login-link">
            Already have an account? <a href="/login">Login here</a>
          </div>
        </div>
        <script>
          document.getElementById('registerForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            try {{
              const response = await fetch('/auth/register', {{
                method: 'POST',
                headers: {{
                  'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ username, email, password }})
              }});
              
              if (response.ok) {{
                document.getElementById('success').textContent = 'Registration successful! You can now login.';
                document.getElementById('success').style.display = 'block';
                document.getElementById('error').style.display = 'none';
                setTimeout(() => {{
                  window.location.href = '/login';
                }}, 2000);
              }} else {{
                const error = await response.json();
                document.getElementById('error').textContent = error.detail || 'Registration failed';
                document.getElementById('error').style.display = 'block';
                document.getElementById('success').style.display = 'none';
              }}
            }} catch (error) {{
              document.getElementById('error').textContent = 'Network error. Please try again.';
              document.getElementById('error').style.display = 'block';
              document.getElementById('success').style.display = 'none';
            }}
          }});
        </script>
      </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse, tags=["system"])
def landing_page(current_user: User = Depends(get_current_active_user)):
    """
    Landing page for the Journaled API - requires authentication.
    """
    return f"""
    <html>
      <head>
        <title>Journaled - Dashboard</title>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f7f7fa; margin: 0; padding: 0; }}
            .container {{ max-width: 800px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #0001; padding: 32px; }}
            h1 {{ color: #2c3e50; margin-top: 0; }}
            nav {{ margin: 24px 0; }}
            nav a {{ display: inline-block; margin: 0 12px 12px 0; padding: 10px 18px; background: #2c3e50; color: #fff; border-radius: 4px; text-decoration: none; font-weight: 500; transition: background 0.2s; }}
            nav a:hover {{ background: #34495e; }}
            .desc {{ color: #555; margin-bottom: 24px; }}
            .user-info {{ background: #ecf0f1; padding: 16px; border-radius: 4px; margin-bottom: 24px; }}
            .logout {{ background: #e74c3c; }}
            .logout:hover {{ background: #c0392b; }}
        </style>
      </head>
      <body>
        <div class="container">
          <h1>Welcome to Journaled</h1>
          <div class="user-info">
            <strong>Logged in as:</strong> {current_user.username} ({current_user.email})
          </div>
          <div class="desc">Your personal accounting dashboard. Access your financial data and manage your accounts.</div>
          <nav>
            <a href="/docs">API Docs</a>
            <a href="/health">Health Check</a>
            <a href="/accounts">Manage Accounts</a>
            <a href="/transactions">View Transactions</a>
            <a href="/auth/me">My Profile</a>
            <a href="/auth/logout" class="logout" onclick="logout()">Logout</a>
          </nav>
          <p style="font-size:0.95em;color:#888;">Journaled &copy; 2025 &mdash; Secure Accounting Platform</p>
        </div>
        <script>
          function logout() {{
            // Clear any stored tokens and redirect to login
            localStorage.removeItem('token');
            window.location.href = '/auth/login';
          }}
        </script>
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

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "text/html" in request.headers.get("accept", ""):
        # Redirect to login page for HTML requests
        return RedirectResponse(url="/login", status_code=302)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(IntegrityError)
def integrity_error_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Database integrity error: " + str(exc.orig)}
    )

# Mount routers
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(transactions_router)

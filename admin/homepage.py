from fastapi import APIRouter, Response

router = APIRouter()

@router.get("/")
async def home():
    """
    Simple homepage with links to Dev Dashboard and Upload page.
    """
    html = """
    <html>
      <head>
        <title>Grace Admin Home</title>
        <style>
          body { font-family: system-ui, sans-serif; background: #f8fafc; color: #222; margin: 0; padding: 0; }
          .center { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
          .card { background: #fff; border-radius: 1rem; box-shadow: 0 4px 24px #0001; padding: 2.5rem 2rem; min-width: 320px; }
          h1 { color: #6366f1; font-size: 2rem; margin-bottom: 1.5rem; }
          a { display: block; margin: 1rem 0; font-size: 1.1rem; color: #6366f1; text-decoration: none; font-weight: 600; border-radius: 0.5rem; padding: 0.75rem 1.5rem; background: #f1f5ff; transition: background 0.15s; text-align: center;}
          a:hover { background: #6366f1; color: #fff; }
        </style>
      </head>
      <body>
        <div class="center">
          <div class="card">
            <h1>Grace Admin Panel</h1>
            <a href="/dev">🚀 Dev Dashboard</a>
            <a href="/admin/upload">⬆️ Upload Config</a>
          </div>
        </div>
      </body>
    </html>
    """
    return Response(content=html, media_type="text/html")
import asyncio
import threading
import time
import uvicorn
from fastapi import FastAPI, Response


def create_health_server(port: int = 8080) -> FastAPI:
    """Create FastAPI health check server."""
    app = FastAPI()

    @app.get("/")
    def health_check_get():
        # bot.is_ready() can only be used in an async context,
        # so we return a simple static response here.
        return {"status": "ok"}

    @app.head("/")
    def health_check_head():
        """
        Health check for HEAD requests.
        Responds to monitoring services like UptimeRobot.
        Returns only status code 200 OK without response body.
        """
        return Response(status_code=200)
    
    return app


def run_fastapi_server(app: FastAPI, port: int):
    """Function to run the FastAPI server using Uvicorn."""
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


def start_health_server(port: int = 8080) -> threading.Thread:
    """
    Start the FastAPI health server in a background thread.
    
    DESIGN PRINCIPLE: The health check server must not block the main bot process.
    Using a daemon thread is crucial. A daemon thread will exit automatically
    when the main thread (the bot) exits. This prevents a "zombie process"
    where the health check server stays alive after the bot has crashed.
    """
    app = create_health_server(port)
    api_thread = threading.Thread(target=run_fastapi_server, args=(app, port), daemon=True)
    api_thread.start()
    
    time.sleep(2)  # Allow time for the server to start
    
    return api_thread


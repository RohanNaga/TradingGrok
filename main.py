import asyncio
import uvicorn
import signal
import sys
from contextlib import asynccontextmanager
from src.trading_bot import TradingBot
from src.web_dashboard import WebDashboard
from src.config import Config
from src.logger import setup_logger

logger = setup_logger("main")

# Global trading bot instance
trading_bot = None
shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app):
    global trading_bot, shutdown_event
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Startup
    logger.info("Starting TradingGrok application...")
    trading_bot = TradingBot()
    
    # Start trading bot in background
    trading_task = asyncio.create_task(trading_bot.start())
    
    yield
    
    # Shutdown
    logger.info("Shutting down TradingGrok application...")
    shutdown_event.set()
    if trading_bot:
        await trading_bot.stop()
    
    # Cancel the trading task
    trading_task.cancel()
    try:
        await trading_task
    except asyncio.CancelledError:
        pass

def create_app():
    global trading_bot
    
    # Initialize trading bot for dashboard
    if not trading_bot:
        trading_bot = TradingBot()
    
    # Create dashboard with lifespan
    dashboard = WebDashboard(trading_bot)
    dashboard.app.router.lifespan_context = lifespan
    
    return dashboard.app

def run_bot_only():
    """Run just the trading bot without web interface"""
    async def main():
        bot = TradingBot()
        await bot.start()
    
    asyncio.run(main())

def run_web_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server with dashboard"""
    config = Config()
    
    uvicorn.run(
        "main:create_app",
        host=host,
        port=port,
        reload=False,
        factory=True,
        log_level=config.LOG_LEVEL.lower()
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "bot-only":
        # Run bot without web interface
        run_bot_only()
    else:
        # Run with web dashboard (default)
        port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
        run_web_server(port=port)
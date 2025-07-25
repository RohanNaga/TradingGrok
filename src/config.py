import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
    PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
    DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")
    MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "0.40"))
    MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "4"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        if not cls.GROK_API_KEY:
            missing.append("GROK_API_KEY")
        if not cls.ALPACA_API_KEY:
            missing.append("ALPACA_API_KEY")
        if not cls.ALPACA_SECRET_KEY:
            missing.append("ALPACA_SECRET_KEY")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    ALPACA_BASE_URL = "https://paper-api.alpaca.markets" if PAPER_TRADING else "https://api.alpaca.markets"
    
    TRADING_HOURS = {
        "start": {"hour": 7, "minute": 50},  # 7:50 AM EST
        "end": {"hour": 16, "minute": 10}    # 4:10 PM EST
    }
    
    ANALYSIS_INTERVAL = 600  # 10 minutes in seconds
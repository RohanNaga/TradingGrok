import pandas_market_calendars as mcal
from datetime import datetime, time
import pytz
from typing import Tuple, Optional
from .logger import setup_logger

logger = setup_logger("market_calendar")

class MarketCalendar:
    def __init__(self):
        self.nyse = mcal.get_calendar('NYSE')
        self.est = pytz.timezone('US/Eastern')
        
    def is_trading_day(self, date: Optional[datetime] = None) -> bool:
        """Check if the given date is a trading day"""
        if date is None:
            date = datetime.now(self.est)
        
        # Get schedule for the date
        schedule = self.nyse.schedule(
            start_date=date.date(),
            end_date=date.date()
        )
        
        return len(schedule) > 0
    
    def get_market_hours(self, date: Optional[datetime] = None) -> Optional[Tuple[datetime, datetime]]:
        """Get market open and close times for a given date"""
        if date is None:
            date = datetime.now(self.est)
        
        if not self.is_trading_day(date):
            return None
        
        schedule = self.nyse.schedule(
            start_date=date.date(),
            end_date=date.date()
        )
        
        if len(schedule) > 0:
            market_open = schedule.iloc[0]['market_open'].to_pydatetime()
            market_close = schedule.iloc[0]['market_close'].to_pydatetime()
            
            # Convert to EST if needed
            if market_open.tzinfo != self.est:
                market_open = market_open.astimezone(self.est)
            if market_close.tzinfo != self.est:
                market_close = market_close.astimezone(self.est)
            
            return market_open, market_close
        
        return None
    
    def minutes_until_close(self) -> Optional[int]:
        """Get minutes until market close, or None if market is closed"""
        now = datetime.now(self.est)
        hours = self.get_market_hours(now)
        
        if not hours:
            return None
        
        market_open, market_close = hours
        
        if now < market_open:
            logger.info(f"Market hasn't opened yet. Opens at {market_open.strftime('%H:%M %Z')}")
            return None
        
        if now > market_close:
            logger.info(f"Market is closed. Closed at {market_close.strftime('%H:%M %Z')}")
            return None
        
        minutes_left = int((market_close - now).total_seconds() / 60)
        return minutes_left
    
    def should_run_today(self) -> bool:
        """Check if the bot should run today"""
        now = datetime.now(self.est)
        
        if not self.is_trading_day(now):
            logger.info(f"Today ({now.strftime('%Y-%m-%d')}) is not a trading day")
            return False
        
        hours = self.get_market_hours(now)
        if not hours:
            return False
        
        market_open, market_close = hours
        
        # Add 10 minutes buffer before open and after close
        start_time = market_open.replace(hour=7, minute=50)  # 7:50 AM EST
        end_time = market_close.replace(minute=market_close.minute + 10)  # 10 min after close
        
        if now < start_time:
            logger.info(f"Too early. Bot should start at {start_time.strftime('%H:%M %Z')}")
            return False
        
        if now > end_time:
            logger.info(f"Too late. Market closed at {market_close.strftime('%H:%M %Z')}")
            return False
        
        logger.info(f"Market is open from {market_open.strftime('%H:%M')} to {market_close.strftime('%H:%M')} {market_close.strftime('%Z')}")
        return True
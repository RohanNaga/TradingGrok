"""
Scheduler module for efficient market-hours-only operation
"""
import asyncio
from datetime import datetime, timedelta
import pytz
import sys
from .market_calendar import MarketCalendar
from .trading_bot import TradingBot
from .logger import setup_logger

logger = setup_logger("scheduler")

class TradingScheduler:
    def __init__(self):
        self.market_calendar = MarketCalendar()
        self.est = pytz.timezone('US/Eastern')
        
    async def run(self):
        """Main entry point for scheduled runs"""
        start_time = datetime.now(self.est)
        logger.info(f"=== TradingGrok Scheduler Started at {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')} ===")
        
        # Check if today is a trading day
        if not self.market_calendar.is_trading_day():
            logger.info("Today is not a trading day (weekend or holiday). Exiting.")
            return
        
        # Get market hours
        market_hours = self.market_calendar.get_market_hours()
        if not market_hours:
            logger.error("Could not determine market hours. Exiting.")
            return
        
        market_open, market_close = market_hours
        now = datetime.now(self.est)
        
        logger.info(f"Market hours: {market_open.strftime('%H:%M')} - {market_close.strftime('%H:%M')} {market_close.strftime('%Z')}")
        
        # Calculate wait time until market open
        if now < market_open:
            wait_seconds = (market_open - now).total_seconds()
            if wait_seconds > 0:
                logger.info(f"Market opens in {int(wait_seconds/60)} minutes. Waiting...")
                await asyncio.sleep(wait_seconds)
        
        # Check if we're past market close + buffer
        close_buffer = market_close + timedelta(minutes=10)
        if now > close_buffer:
            logger.info(f"Market closed at {market_close.strftime('%H:%M')}. Too late to start. Exiting.")
            return
        
        # Start the trading bot
        logger.info("Starting trading bot...")
        bot = TradingBot()
        
        try:
            await bot.start()
        except Exception as e:
            logger.error(f"Trading bot error: {e}")
        finally:
            # Log session summary
            end_time = datetime.now(self.est)
            duration = (end_time - start_time).total_seconds() / 60
            logger.info(f"=== Session ended at {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')} ===")
            logger.info(f"Total runtime: {duration:.1f} minutes")
            
            # Calculate cost savings
            if duration < 60:
                logger.info(f"Efficient scheduling saved ~{(480 - duration):.0f} minutes of server time today!")

async def main():
    """Entry point for scheduled runs"""
    scheduler = TradingScheduler()
    await scheduler.run()

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from datetime import datetime, time
import pytz
from typing import Dict, Optional
from .grok_analyzer import GrokAnalyzer
from .alpaca_trader import AlpacaTrader
from .config import Config
from .logger import setup_logger

logger = setup_logger("trading_bot")

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.grok_analyzer = GrokAnalyzer(self.config.GROK_API_KEY)
        self.alpaca_trader = AlpacaTrader(
            self.config.ALPACA_API_KEY,
            self.config.ALPACA_SECRET_KEY,
            self.config.ALPACA_BASE_URL
        )
        self.trading_active = False
        self.last_analysis = None
        self.est = pytz.timezone('US/Eastern')
        
    async def start(self):
        """Start the trading bot"""
        logger.info("Starting TradingGrok AI Trading Bot")
        logger.info(f"Paper Trading Mode: {self.config.PAPER_TRADING}")
        
        self.trading_active = True
        
        try:
            await self.run_trading_loop()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the trading bot"""
        logger.info("Stopping trading bot...")
        self.trading_active = False
        await self.grok_analyzer.close()
        
    async def run_trading_loop(self):
        """Main trading loop"""
        while self.trading_active:
            try:
                if self.is_trading_window():
                    logger.info("In trading window - executing trading cycle")
                    await self.execute_trading_cycle()
                else:
                    logger.debug("Outside trading window - sleeping")
                
                await asyncio.sleep(self.config.ANALYSIS_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(60)
    
    def is_trading_window(self) -> bool:
        """Check if current time is within trading hours"""
        try:
            now = datetime.now(self.est)
            
            if now.weekday() > 4:  # Saturday = 5, Sunday = 6
                return False
            
            start_time = time(
                self.config.TRADING_HOURS["start"]["hour"],
                self.config.TRADING_HOURS["start"]["minute"]
            )
            end_time = time(
                self.config.TRADING_HOURS["end"]["hour"],
                self.config.TRADING_HOURS["end"]["minute"]
            )
            
            current_time = now.time()
            return start_time <= current_time <= end_time
            
        except Exception as e:
            logger.error(f"Error checking trading window: {e}")
            return False
    
    async def execute_trading_cycle(self):
        """Execute one complete trading cycle"""
        try:
            logger.info("Starting trading cycle")
            
            if not self.alpaca_trader.check_market_open():
                logger.info("Market is closed - skipping cycle")
                return
            
            analysis = await self.grok_analyzer.analyze_market()
            if not analysis:
                logger.warning("No analysis received from Grok")
                return
            
            self.last_analysis = analysis
            logger.info(f"Received {len(analysis.get('trades', []))} trade recommendations")
            
            account_info = self.alpaca_trader.get_account_info()
            if not account_info:
                logger.error("Could not get account information")
                return
            
            current_positions = self.alpaca_trader.get_positions()
            logger.info(f"Current positions: {len(current_positions)}")
            
            for trade in analysis.get("trades", []):
                if await self.should_execute_trade(trade, current_positions, account_info):
                    success = self.alpaca_trader.execute_trade(trade)
                    if success:
                        logger.info(f"Successfully executed trade: {trade['symbol']} {trade['side']} {trade['qty']}")
                    else:
                        logger.warning(f"Failed to execute trade: {trade['symbol']}")
            
            await self.manage_existing_positions(current_positions)
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
    async def should_execute_trade(self, trade: Dict, positions: list, account: Dict) -> bool:
        """Determine if a trade should be executed"""
        try:
            symbol = trade["symbol"]
            confidence = trade.get("confidence", 0.5)
            
            if confidence < 0.6:
                logger.info(f"Skipping {symbol} - low confidence: {confidence}")
                return False
            
            existing_position = next((p for p in positions if p["symbol"] == symbol), None)
            if existing_position:
                logger.info(f"Already have position in {symbol}")
                return False
            
            if len(positions) >= self.config.MAX_POSITIONS:
                logger.info(f"Max positions ({self.config.MAX_POSITIONS}) reached")
                return False
            
            position_size = trade.get("qty", 1) * trade.get("limit_price", 100)
            max_position_value = account["account_value"] * self.config.MAX_POSITION_SIZE
            
            if position_size > max_position_value:
                logger.info(f"Position size too large for {symbol}: ${position_size} > ${max_position_value}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating trade: {e}")
            return False
    
    async def manage_existing_positions(self, positions: list):
        """Manage existing positions - check for exits"""
        try:
            for position in positions:
                symbol = position["symbol"]
                unrealized_pl_pct = position.get("unrealized_plpc", 0)
                
                should_exit = False
                exit_reason = ""
                
                if unrealized_pl_pct <= -0.05:  # 5% loss
                    should_exit = True
                    exit_reason = "Stop loss triggered"
                elif unrealized_pl_pct >= 0.15:  # 15% gain
                    should_exit = True
                    exit_reason = "Take profit"
                
                if should_exit:
                    exit_trade = {
                        "symbol": symbol,
                        "side": "sell" if position["side"] == "long" else "buy",
                        "qty": abs(int(position["qty"])),
                        "type": "market",
                        "time_in_force": "day"
                    }
                    
                    success = self.alpaca_trader.execute_trade(exit_trade)
                    if success:
                        logger.info(f"Exited position {symbol}: {exit_reason} (P&L: {unrealized_pl_pct:.2%})")
                    
        except Exception as e:
            logger.error(f"Error managing positions: {e}")
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        try:
            account_info = self.alpaca_trader.get_account_info()
            positions = self.alpaca_trader.get_positions()
            open_orders = self.alpaca_trader.get_open_orders()
            
            return {
                "active": self.trading_active,
                "in_trading_window": self.is_trading_window(),
                "account_value": account_info.get("account_value", 0),
                "positions_count": len(positions),
                "open_orders_count": len(open_orders),
                "last_analysis_time": self.last_analysis.get("timestamp") if self.last_analysis else None,
                "paper_trading": self.config.PAPER_TRADING
            }
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {"error": str(e)}
    
    def get_detailed_status(self) -> Dict:
        """Get detailed status including positions and orders"""
        try:
            status = self.get_status()
            status.update({
                "positions": self.alpaca_trader.get_positions(),
                "open_orders": self.alpaca_trader.get_open_orders(),
                "last_analysis": self.last_analysis
            })
            return status
            
        except Exception as e:
            logger.error(f"Error getting detailed status: {e}")
            return {"error": str(e)}
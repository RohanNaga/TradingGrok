import asyncio
from datetime import datetime, time
import pytz
from typing import Dict, Optional
from .grok_analyzer import GrokAnalyzer
from .alpaca_trader import AlpacaTrader
from .config import Config
from .logger import setup_logger
from .market_calendar import MarketCalendar

logger = setup_logger("trading_bot")

class TradingBot:
    def __init__(self):
        self.config = Config()
        
        # Validate configuration before starting
        try:
            self.config.validate()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise
            
        self.alpaca_trader = AlpacaTrader(
            self.config.ALPACA_API_KEY,
            self.config.ALPACA_SECRET_KEY,
            self.config.ALPACA_BASE_URL
        )
        self.grok_analyzer = GrokAnalyzer(self.config.GROK_API_KEY, self.alpaca_trader)
        self.trading_active = False
        self.last_analysis = None
        self.est = pytz.timezone('US/Eastern')
        self.market_calendar = MarketCalendar()
        
    async def start(self):
        """Start the trading bot"""
        logger.info("Starting TradingGrok AI Trading Bot")
        logger.info(f"Paper Trading Mode: {self.config.PAPER_TRADING}")
        
        # Check if we should run today
        if not self.market_calendar.should_run_today():
            logger.info("Market is closed or outside trading hours. Shutting down.")
            return
        
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
        # Wait a bit before starting the first cycle to allow services to initialize
        await asyncio.sleep(5)
        
        while self.trading_active:
            try:
                # Check if market is still open
                minutes_left = self.market_calendar.minutes_until_close()
                if minutes_left is None:
                    logger.info("Market is closed. Shutting down.")
                    self.trading_active = False
                    break
                
                logger.info(f"Market closes in {minutes_left} minutes")
                
                # Stop trading 5 minutes before market close
                if minutes_left <= 5:
                    logger.info("Less than 5 minutes until market close. Stopping trading.")
                    self.trading_active = False
                    break
                
                if self.is_trading_window():
                    logger.info("In trading window - executing trading cycle")
                    await self.execute_trading_cycle()
                else:
                    logger.debug("Outside trading window - sleeping")
                
                # Sleep for the analysis interval or until 5 min before close, whichever is shorter
                sleep_minutes = min(self.config.ANALYSIS_INTERVAL / 60, minutes_left - 5)
                await asyncio.sleep(sleep_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info("Trading loop cancelled")
                break
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
            
            # Get account info and current positions to pass to analyzer
            account_info = self.alpaca_trader.get_account_info()
            current_positions = self.alpaca_trader.get_positions()
            open_orders = self.alpaca_trader.get_open_orders()
            
            # Collect market data for all relevant symbols
            market_data = {}
            symbols_to_check = set()
            
            # Add symbols from current positions
            for pos in current_positions:
                symbols_to_check.add(pos['symbol'])
            
            # Add common tech stocks for monitoring
            tech_stocks = ['NVDA', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'AMD', 
                          'PLTR', 'SNOW', 'UBER', 'SQ', 'SHOP', 'SNAP', 'CRWD', 'NET']
            symbols_to_check.update(tech_stocks)
            
            # Get latest prices for all symbols
            for symbol in symbols_to_check:
                try:
                    latest_trade = self.alpaca_trader.api.get_latest_trade(symbol)
                    if latest_trade and latest_trade.price:
                        market_data[symbol] = {
                            'price': float(latest_trade.price),
                            'timestamp': latest_trade.timestamp.isoformat() if hasattr(latest_trade.timestamp, 'isoformat') else str(latest_trade.timestamp)
                        }
                except Exception as e:
                    logger.warning(f"Could not get price for {symbol}: {e}")
            
            # Log current state for debugging
            logger.info(f"📊 Portfolio State - Positions: {len(current_positions)}, Open Orders: {len(open_orders)}")
            for pos in current_positions:
                logger.info(f"   - {pos['symbol']}: {pos['qty']} shares")
            for order in open_orders:
                logger.info(f"   - Order: {order['side']} {order['qty']} {order['symbol']} ({order['order_type']})")
            logger.info(f"📈 Market Data collected for {len(market_data)} symbols")
            
            analysis = await self.grok_analyzer.analyze_market(account_info, current_positions, open_orders, market_data)
            if not analysis:
                logger.warning("No analysis received from Grok")
                return
            
            self.last_analysis = analysis
            logger.info(f"Received {len(analysis.get('trades', []))} trade recommendations")
            if not account_info:
                logger.error("Could not get account information")
                return
            
            logger.info(f"Current positions: {len(current_positions)}")
            
            for trade in analysis.get("trades", []):
                if await self.should_execute_trade(trade, current_positions, account_info):
                    success, error_msg = self.alpaca_trader.execute_trade(trade)
                    if success:
                        logger.info(f"Successfully executed trade: {trade['symbol']} {trade['side']} {trade['qty']}")
                    else:
                        # Add trade error to Grok analyzer for feedback
                        self.grok_analyzer.add_trade_error(
                            trade['symbol'], 
                            trade.get('action_type', 'UNKNOWN'), 
                            error_msg
                        )
                        logger.warning(f"Failed to execute trade: {trade['symbol']}")
            
            await self.manage_existing_positions(current_positions)
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
    
    async def should_execute_trade(self, trade: Dict, positions: list, account: Dict) -> bool:
        """Execute whatever Grok recommends - Grok has full authority over portfolio decisions"""
        try:
            symbol = trade.get("symbol", "")
            action_type = trade.get("action_type", "OPEN")
            confidence = trade.get("confidence", 0.5)
            urgency = trade.get("urgency", "MEDIUM")
            
            logger.info(f"🤖 GROK'S DECISION: {action_type} {symbol}")
            logger.info(f"   📊 Confidence: {confidence*100:.1f}%")
            logger.info(f"   ⏱️  Urgency: {urgency}")
            logger.info(f"   🎯 Side: {trade.get('side', 'N/A').upper()}")
            logger.info(f"   📦 Quantity: {trade.get('qty', 0)} shares")
            
            # Only basic sanity checks - trust Grok's judgment completely  
            if trade.get("qty", 0) <= 0:
                logger.error(f"❌ Invalid quantity for {symbol}: {trade.get('qty', 0)}")
                return False
            
            if not symbol:
                logger.error(f"❌ No symbol provided in trade")
                return False
                
            # Log portfolio impact
            if action_type in ["OPEN", "ADD"]:
                logger.info(f"📈 INCREASING exposure to {symbol}")
            elif action_type in ["REDUCE", "CLOSE"]:
                logger.info(f"📉 REDUCING exposure to {symbol}")
            
            # Show position change details if available
            if trade.get("current_qty") is not None and trade.get("target_qty") is not None:
                logger.info(f"   🔄 Position Change: {trade['current_qty']} → {trade['target_qty']} shares")
            
            logger.info(f"✅ EXECUTING GROK'S RECOMMENDATION - NO ARTIFICIAL LIMITS")
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating trade: {e}")
            return False
    
    async def manage_existing_positions(self, positions: list):
        """Manage existing positions - Grok now handles all position decisions"""
        try:
            # Grok now makes all position management decisions through its actions
            # This method is kept for compatibility but doesn't auto-exit positions
            logger.debug(f"Position management delegated to Grok. Current positions: {len(positions)}")
            for position in positions:
                symbol = position["symbol"]
                unrealized_pl_pct = position.get("unrealized_plpc", 0)
                logger.debug(f"{symbol}: {unrealized_pl_pct:.2%} P&L")
                    
        except Exception as e:
            logger.error(f"Error in position management: {e}")
    
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
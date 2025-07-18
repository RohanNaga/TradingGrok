import alpaca_trade_api as tradeapi
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .logger import setup_logger

logger = setup_logger("alpaca_trader")

class AlpacaTrader:
    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self.api = tradeapi.REST(
            api_key, 
            secret_key, 
            base_url=base_url,
            api_version='v2'
        )
        self.positions = {}
        self.pending_orders = {}
        
    def get_account_info(self) -> Dict:
        """Get account information"""
        try:
            account = self.api.get_account()
            return {
                "account_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "day_trade_buying_power": float(getattr(account, 'day_trade_buying_power', account.buying_power)),
                "pattern_day_trader": getattr(account, 'pattern_day_trader', False)
            }
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            positions = self.api.list_positions()
            position_list = []
            
            for pos in positions:
                position_data = {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "side": pos.side,
                    "avg_entry_price": float(pos.avg_entry_price)
                }
                position_list.append(position_data)
                
            return position_list
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def execute_trade(self, trade_signal: Dict) -> bool:
        """Execute a trade based on the signal"""
        try:
            symbol = trade_signal["symbol"]
            side = trade_signal["side"]
            qty = trade_signal["qty"]
            
            if self._can_execute_trade(symbol, side, qty):
                order = self.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type=trade_signal.get("type", "market"),
                    time_in_force=trade_signal.get("time_in_force", "day"),
                    limit_price=trade_signal.get("limit_price") if trade_signal.get("type") == "limit" else None
                )
                
                logger.info(f"Order submitted: {symbol} {side} {qty} shares")
                
                if "stop_loss" in trade_signal:
                    self._set_stop_loss(symbol, qty, trade_signal["stop_loss"], side)
                
                return True
                
        except Exception as e:
            logger.error(f"Error executing trade for {trade_signal.get('symbol', 'unknown')}: {e}")
            return False
        
        return False
    
    def _can_execute_trade(self, symbol: str, side: str, qty: int) -> bool:
        """Check if we can execute the trade"""
        try:
            current_positions = len(self.get_positions())
            max_positions = 4
            
            if side == "buy" and current_positions >= max_positions:
                position_exists = any(pos["symbol"] == symbol for pos in self.get_positions())
                if not position_exists:
                    logger.warning(f"Cannot open new position for {symbol}: Max positions ({max_positions}) reached")
                    return False
            
            account = self.get_account_info()
            if not account:
                return False
            
            if side == "buy":
                latest_trade = self.api.get_latest_trade(symbol)
                if latest_trade and latest_trade.price:
                    estimated_cost = float(latest_trade.price) * qty
                    if estimated_cost > account["buying_power"]:
                        logger.warning(f"Insufficient buying power for {symbol}: need ${estimated_cost}, have ${account['buying_power']}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking trade eligibility: {e}")
            return False
    
    def _set_stop_loss(self, symbol: str, qty: int, stop_price: float, original_side: str):
        """Set stop loss order"""
        try:
            stop_side = "sell" if original_side == "buy" else "buy"
            
            stop_order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=stop_side,
                type="stop",
                time_in_force="gtc",
                stop_price=stop_price
            )
            
            logger.info(f"Stop loss set for {symbol}: {stop_side} {qty} shares at ${stop_price}")
            
        except Exception as e:
            logger.error(f"Error setting stop loss for {symbol}: {e}")
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        try:
            orders = self.api.list_orders(status='open')
            order_list = []
            
            for order in orders:
                order_data = {
                    "id": order.id,
                    "symbol": order.symbol,
                    "qty": float(order.qty),
                    "side": order.side,
                    "type": order.order_type,
                    "status": order.status,
                    "limit_price": float(order.limit_price) if order.limit_price else None,
                    "stop_price": float(order.stop_price) if order.stop_price else None,
                    "submitted_at": order.submitted_at
                }
                order_list.append(order_data)
                
            return order_list
            
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.api.cancel_order(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_portfolio_history(self, period: str = "1D") -> Dict:
        """Get portfolio history"""
        try:
            history = self.api.get_portfolio_history(period=period)
            return {
                "timestamp": [t.isoformat() for t in history.timestamp],
                "equity": history.equity,
                "profit_loss": history.profit_loss,
                "profit_loss_pct": history.profit_loss_pct
            }
        except Exception as e:
            logger.error(f"Error getting portfolio history: {e}")
            return {}
    
    def check_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            clock = self.api.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Error checking market status: {e}")
            return False
    
    def get_market_calendar(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get market calendar"""
        try:
            if not start_date:
                start_date = datetime.now().strftime("%Y-%m-%d")
            if not end_date:
                end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                
            calendar = self.api.get_calendar(start_date, end_date)
            return [{"date": str(day.date), "open": str(day.open), "close": str(day.close)} for day in calendar]
        except Exception as e:
            logger.error(f"Error getting market calendar: {e}")
            return []
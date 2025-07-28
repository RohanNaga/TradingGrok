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
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "day_trade_buying_power": float(getattr(account, 'day_trade_buying_power', account.buying_power)),
                "pattern_day_trader": getattr(account, 'pattern_day_trader', False),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "long_market_value": float(account.long_market_value),
                "short_market_value": float(account.short_market_value),
                "initial_margin": float(getattr(account, 'initial_margin', 0)),
                "maintenance_margin": float(getattr(account, 'maintenance_margin', 0)),
                "sma": float(getattr(account, 'sma', 0)),  # Special Memorandum Account
                "daytrade_count": int(getattr(account, 'daytrade_count', 0)),
                "status": account.status,
                "account_blocked": account.account_blocked,
                "trade_suspended_by_user": account.trade_suspended_by_user,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked
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
    
    def execute_trade(self, trade_signal: Dict) -> tuple[bool, str]:
        """Execute a trade based on the signal - supports long and short positions"""
        try:
            symbol = trade_signal["symbol"]
            side = trade_signal["side"]
            qty = trade_signal["qty"]
            action_type = trade_signal.get("action_type", "OPEN")
            
            logger.info(f"🎯 Executing {action_type}: {side.upper()} {qty} shares of {symbol}")
            
            if self._can_execute_trade(symbol, side, qty):
                # Use bracket orders for entries with stop loss (both long and short)
                if action_type in ["OPEN", "ADD"] and "stop_loss" in trade_signal:
                    order_params = {
                        "symbol": symbol,
                        "qty": qty,
                        "side": side,  # 'buy' for long, 'sell' for short
                        "type": trade_signal.get("type", "market"),
                        "time_in_force": trade_signal.get("time_in_force", "day"),
                        "order_class": "bracket",
                        "stop_loss": {"stop_price": trade_signal["stop_loss"]}
                    }
                    
                    # Add limit price if it's a limit order
                    if trade_signal.get("type") == "limit":
                        order_params["limit_price"] = trade_signal.get("limit_price")
                    
                    # Add take profit if provided
                    if "target_price" in trade_signal:
                        order_params["take_profit"] = {"limit_price": trade_signal["target_price"]}
                    
                    order = self.api.submit_order(**order_params)
                    position_type = "LONG" if side == "buy" else "SHORT"
                    logger.info(f"📈 Bracket {position_type} order: {symbol} {side} {qty} shares, stop: ${trade_signal['stop_loss']}")
                else:
                    # Regular order without bracket (for exits or simple entries)
                    order_params = {
                        "symbol": symbol,
                        "qty": qty,
                        "side": side,
                        "type": trade_signal.get("type", "market"),
                        "time_in_force": trade_signal.get("time_in_force", "day")
                    }
                    
                    if trade_signal.get("type") == "limit":
                        order_params["limit_price"] = trade_signal.get("limit_price")
                    
                    order = self.api.submit_order(**order_params)
                    position_type = "LONG" if side == "buy" else "SHORT"
                    logger.info(f"📊 {position_type} order submitted: {symbol} {side} {qty} shares")
                
                return True, "Success"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing trade for {trade_signal.get('symbol', 'unknown')}: {error_msg}")
            return False, error_msg
        
        return False, "Trade execution failed: unknown error"
    
    def _can_execute_trade(self, symbol: str, side: str, qty: int) -> bool:
        """Check if we can execute the trade - minimal safety checks only"""
        try:
            account = self.get_account_info()
            if not account:
                return False
            
            # Check position availability for sell orders
            if side == "sell":
                current_positions = self.get_positions()
                available_qty = 0
                
                for pos in current_positions:
                    if pos["symbol"] == symbol:
                        available_qty = int(abs(float(pos["qty"])))
                        break
                
                if qty > available_qty:
                    logger.error(f"Insufficient quantity for {symbol}: requested {qty}, available {available_qty}")
                    return False
            
            # Check buying power for buy orders
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
        """
        Set stop loss order - DEPRECATED
        Note: This method is deprecated due to wash trade detection issues.
        Use bracket orders instead when placing buy orders with stop loss.
        """
        # Suppress unused parameter warnings - method is deprecated
        _ = qty, stop_price, original_side
        logger.warning(f"_set_stop_loss is deprecated. Use bracket orders for {symbol} to avoid wash trade issues.")
    
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
                    "order_type": order.order_type,  # Changed from "type" to "order_type"
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
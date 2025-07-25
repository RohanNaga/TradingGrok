import httpx
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from .logger import setup_logger

logger = setup_logger("grok_analyzer")

class GrokAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.client = None
        
        if not self.api_key:
            logger.error("Grok API key is missing!")
        
    async def analyze_market(self, account_info: Optional[Dict] = None, current_positions: Optional[List] = None) -> Optional[Dict]:
        """
        Queries Grok for market analysis and trading recommendations
        """
        try:
            prompt = self._build_analysis_prompt(account_info, current_positions)
            
            response = await self._call_grok_api(prompt)
            if not response:
                return None
                
            return await self.format_trades(response, account_info)
            
        except Exception as e:
            logger.error(f"Error in market analysis: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _build_analysis_prompt(self, account_info: Optional[Dict] = None, current_positions: Optional[List] = None) -> str:
        """
        Build comprehensive prompt for Grok analysis
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
        
        # Format account info
        account_summary = "No account info provided"
        if account_info:
            account_summary = f"""
ACCOUNT VALUE: ${account_info.get('account_value', 0):,.2f}
BUYING POWER: ${account_info.get('buying_power', 0):,.2f}
CASH: ${account_info.get('cash', 0):,.2f}
DAY TRADE BUYING POWER: ${account_info.get('day_trade_buying_power', 0):,.2f}
PORTFOLIO VALUE: ${account_info.get('portfolio_value', 0):,.2f}"""

        # Format current positions
        positions_summary = "NO CURRENT POSITIONS - STARTING FRESH"
        total_position_value = 0
        if current_positions and len(current_positions) > 0:
            positions_list = []
            for pos in current_positions:
                qty = int(pos.get('qty', 0))
                market_value = float(pos.get('market_value', 0))
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                unrealized_plpc = float(pos.get('unrealized_plpc', 0)) * 100
                total_position_value += market_value
                
                positions_list.append(f"""
  {pos['symbol']}: {qty} shares, ${market_value:,.2f} value, P&L: ${unrealized_pl:+,.2f} ({unrealized_plpc:+.1f}%)""")
            
            positions_summary = f"""
CURRENT POSITIONS ({len(current_positions)} total, ${total_position_value:,.2f} deployed):
{"".join(positions_list)}"""

        return f"""
        You are an AGGRESSIVE portfolio manager with complete authority over a ${account_info.get('account_value', 100000):,.0f} trading account.
        Current time: {current_time}
        
        {account_summary}
        
        {positions_summary}
        
        🎯 PORTFOLIO MANAGEMENT INSTRUCTIONS:
        
        1. ANALYZE CURRENT POSITIONS: Look at each existing position's P&L and performance
        2. MAKE SPECIFIC ACTIONS: For each stock, decide OPEN/ADD/REDUCE/CLOSE
        3. USE EXACT QUANTITIES: Always specify current_qty (from positions above) and target_qty
        4. BE AGGRESSIVE: Use full buying power for high-conviction plays
        5. SCALE INTELLIGENTLY: Add to winners, trim losers, rotate based on catalysts
        
        TRADING PHILOSOPHY: Act decisively on breaking news, earnings momentum, and fundamental catalysts. 
        Take concentrated positions in high-conviction opportunities. Risk big to win big.
        
        ANALYSIS PRIORITIES (in order):
        1. BREAKING NEWS & VIRAL CATALYSTS (Last 24-48 hours):
        - Earnings surprises, guidance updates, analyst upgrades/downgrades
        - Product launches, partnerships, regulatory changes
        - SOCIAL MEDIA EXPLOSIONS: Influencer endorsements, viral campaigns, celebrity partnerships
        - CULTURAL MOMENTUM: Meme stocks, GenZ trends, social media buzz (TikTok, Instagram, Twitter/X)
        - CULTURAL CATALYSTS: Celebrity endorsements, viral campaigns, social media explosions
        - Sector rotation triggers, Fed policy, geopolitical events
        
        2. CULTURAL & SOCIAL MOMENTUM PATTERNS:
        - INFLUENCER/CELEBRITY PARTNERSHIPS: Track high-profile endorsement deals and brand associations
        - VIRAL MARKETING BREAKOUTS: Companies achieving massive social media reach/engagement
        - GENERATIONAL SHIFTS: Brands capturing younger demographics or changing consumer behavior
        - CULTURAL ZEITGEIST PLAYS: Companies aligned with trending topics, movements, or viral moments
        - SOCIAL MEDIA AMPLIFICATION: Stocks getting unusual attention across platforms (Twitter, TikTok, Reddit)
        
        3. FUNDAMENTAL MOMENTUM:
        - Revenue/earnings acceleration trends  
        - Market share gains, competitive moats
        - AI/Tech disruption opportunities
        - Valuation gaps vs growth potential
        
        4. TECHNICAL SETUPS:
        - Breakouts from consolidation patterns
        - Volume surge confirmations
        - Momentum indicator alignment
        - Key support/resistance levels
        
        POSITION SIZING STRATEGY:
        - HIGH CONVICTION (90%+ confidence): 35-40% of portfolio
        - MEDIUM CONVICTION (75-89% confidence): 25-30% of portfolio  
        - SPECULATIVE (60-74% confidence): 15-20% of portfolio
        - Never go below 15% - if not worth 15%, don't trade it
        
        STOCK RECOMMENDATIONS (provide 2-4 stocks with AGGRESSIVE sizing):
        
        PRIORITY TARGETS:
        - MEGA-CAPS: NVDA, AAPL, GOOGL, MSFT, AMZN, TSLA, META, AMD
        - GROWTH/MOMENTUM: CRM, NFLX, ADBE, UBER, SHOP, SQ, PLTR, SNOW, SNAP, PINS
        - CONSUMER/RETAIL: NKE, LULU, AEO, ANF, URBN, COST, TGT, HD, LOW
        - MEME/SOCIAL MOMENTUM: Previous runners with new catalysts
        
        PATTERN RECOGNITION FRAMEWORK:
        - NEWS MOMENTUM: How do similar companies react to comparable catalysts?
        - CULTURAL CYCLES: Which trends are accelerating vs fading?
        - CROSS-PLATFORM AMPLIFICATION: Stories gaining traction across multiple channels
        - DEMOGRAPHIC SHIFTS: Consumer behavior changes driving sector rotation
        - EVENT-DRIVEN OPPORTUNITIES: Earnings, launches, partnerships creating momentum
        
        YOUR PORTFOLIO MANAGEMENT ACTIONS:
        You have FOUR action types available for each stock:
        
        1. OPEN: Start a new position (current_qty=0, target_qty>0)
        2. ADD: Increase existing position (target_qty > current_qty) 
        3. REDUCE: Decrease existing position (target_qty < current_qty but > 0)
        4. CLOSE: Exit entire position (target_qty=0)
        
        For each action, specify:
        - EXACT quantities (current_qty and target_qty)
        - Entry/exit price ranges
        - Stop loss and target prices
        - Position size as % of total portfolio
        - Specific catalyst driving this action
        - Confidence level and urgency
        
        Format as JSON:
        {{
            "market_overview": {{
                "sentiment": "EXTREMELY_BULLISH/BULLISH/BEARISH/EXTREMELY_BEARISH",
                "key_catalysts": ["specific recent news/events"],
                "dominant_theme": "AI boom/Fed pivot/Earnings season/etc",
                "risk_level": "AGGRESSIVE/MODERATE/CONSERVATIVE",
                "portfolio_analysis": "Assessment of current positions and overall strategy"
            }},
            "actions": [
                {{
                    "symbol": "STOCK_SYMBOL",
                    "action": "OPEN/ADD/REDUCE/CLOSE",
                    "current_qty": 0,
                    "target_qty": 100,
                    "qty_change": 100,
                    "entry_price_min": 100.00,
                    "entry_price_max": 102.00,
                    "target_price": 125.00,
                    "stop_loss": 92.00,
                    "position_size_pct": 0.35,
                    "holding_period_days": 10,
                    "news_catalyst": "Specific breaking news in last 48hrs",
                    "fundamental_thesis": "Why this position/adjustment makes sense",
                    "technical_setup": "Chart pattern/momentum confirmation",
                    "confidence": 0.85,
                    "urgency": "IMMEDIATE/HIGH/MEDIUM/LOW",
                    "reasoning": "Detailed explanation of this specific action"
                }}
            ]
        }}
        
        EXAMPLE ACTIONS:
        
        📈 OPEN: Start new TSLA position
        {"symbol": "TSLA", "action": "OPEN", "current_qty": 0, "target_qty": 50, "qty_change": 50}
        
        🔥 ADD: Increase existing NVDA position  
        {"symbol": "NVDA", "action": "ADD", "current_qty": 45, "target_qty": 70, "qty_change": 25}
        
        📉 REDUCE: Trim AAPL position
        {"symbol": "AAPL", "action": "REDUCE", "current_qty": 78, "target_qty": 40, "qty_change": -38}
        
        🚪 CLOSE: Exit entire META position
        {"symbol": "META", "action": "CLOSE", "current_qty": 25, "target_qty": 0, "qty_change": -25}
        
        ⚠️  CRITICAL: Always include current_qty, target_qty, and qty_change for each action!
        
        URGENCY CLASSIFICATION:
        - IMMEDIATE: Breaking news/viral moments happening RIGHT NOW (trade within 1-2 hours)
        - HIGH: Major catalyst within 24hrs, earnings reactions, upgrade/downgrades  
        - MEDIUM: Strong setup, no immediate catalyst, swing trade opportunity
        - LOW: Longer-term positioning, market conditions unfavorable for aggression
        
        EXECUTE WITH CONVICTION: Only recommend trades you'd bet serious money on. 
        If market conditions don't warrant aggressive positions, recommend cash/wait.
        Focus on liquid mega-caps and high-volume growth stocks only.
        
        REMEMBER: Stay alert for breaking news, cultural shifts, and viral moments that create trading opportunities!
        """
    
    async def _call_grok_api(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """
        Make API call to Grok with retry logic and exponential backoff
        """
        if not self.api_key:
            logger.error("Cannot call Grok API - API key is missing")
            return None
            
        if not self.client:
            self.client = httpx.AsyncClient(timeout=120.0)
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Grok, an expert AI trading analyst specializing in tech stock swing trading."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "model": "grok-4-latest",
            "stream": False,
            "temperature": 0.3
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Grok API call attempt {attempt + 1}/{max_retries}")
                
                response = await self.client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    grok_response = result["choices"][0]["message"]["content"]
                    logger.info("Grok API call successful")
                    logger.info("=== GROK RESPONSE ===")
                    logger.info(grok_response)
                    logger.info("=== END GROK RESPONSE ===")
                    return grok_response
                else:
                    logger.error(f"Grok API error: {response.status_code} - {response.text}")
                    if response.status_code >= 500 and attempt < max_retries - 1:
                        # Server error, retry with backoff
                        backoff_time = 2 ** attempt
                        logger.info(f"Server error, retrying in {backoff_time} seconds...")
                        await asyncio.sleep(backoff_time)
                        continue
                    return None
                    
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                logger.warning(f"Timeout error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error("All retry attempts failed due to timeout")
                return None
                
            except Exception as e:
                logger.error(f"Error calling Grok API on attempt {attempt + 1}: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.info(f"Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
                    continue
                import traceback
                logger.error(f"Final attempt failed. Traceback: {traceback.format_exc()}")
                return None
        
        return None
    
    async def format_trades(self, grok_response: str, account_info: Optional[Dict] = None) -> Optional[Dict]:
        """
        Convert Grok response to structured trade format
        """
        try:
            json_start = grok_response.find('{')
            json_end = grok_response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                logger.error("No JSON found in Grok response")
                return None
                
            json_str = grok_response[json_start:json_end]
            analysis = json.loads(json_str)
            
            formatted_actions = []
            for action in analysis.get("actions", []):
                action_type = action.get("action", "OPEN")
                symbol = action["symbol"]
                current_qty = action.get("current_qty", 0)
                target_qty = action.get("target_qty", 0)
                qty_change = action.get("qty_change", target_qty - current_qty)
                
                # Determine the trade side and quantity based on action
                if action_type in ["OPEN", "ADD"] and qty_change > 0:
                    side = "buy"
                    trade_qty = abs(qty_change)
                elif action_type in ["REDUCE", "CLOSE"] and qty_change < 0:
                    side = "sell"  
                    trade_qty = abs(qty_change)
                else:
                    logger.warning(f"Skipping invalid action for {symbol}: {action_type} with qty_change {qty_change}")
                    continue
                
                trade = {
                    "symbol": symbol,
                    "side": side,
                    "qty": trade_qty,
                    "type": "limit",
                    "limit_price": action.get("entry_price_max", action.get("entry_price_min", 100)),
                    "time_in_force": "day",
                    "stop_loss": action.get("stop_loss"),
                    "target_price": action.get("target_price"),
                    "reasoning": action.get("reasoning", action.get("fundamental_thesis", "N/A")),
                    "confidence": action.get("confidence", 0.5),
                    "holding_period": action.get("holding_period_days", 14),
                    "action_type": action_type,
                    "current_qty": current_qty,
                    "target_qty": target_qty,
                    "urgency": action.get("urgency", "MEDIUM")
                }
                
                # Log detailed action reasoning
                logger.info(f"=== PORTFOLIO ACTION: {action_type} {symbol} ===")
                logger.info(f"🔄 POSITION CHANGE: {current_qty} → {target_qty} shares ({qty_change:+d})")
                logger.info(f"📈 CATALYST: {action.get('news_catalyst', 'N/A')}")
                logger.info(f"💡 THESIS: {action.get('fundamental_thesis', 'N/A')}")
                logger.info(f"📊 TECHNICAL: {action.get('technical_setup', 'N/A')}")
                logger.info(f"💰 Price: ${action.get('entry_price_min', 'N/A')} - ${action.get('entry_price_max', 'N/A')}")
                if action.get('target_price') and action.get('entry_price_max'):
                    logger.info(f"🎯 Target: ${action['target_price']} ({((action['target_price']/action['entry_price_max']-1)*100):+.1f}%)")
                if action.get('stop_loss') and action.get('entry_price_max'):
                    logger.info(f"🛑 Stop: ${action['stop_loss']} ({((action['stop_loss']/action['entry_price_max']-1)*100):+.1f}%)")
                logger.info(f"📊 Target Position Size: {action.get('position_size_pct', 0)*100:.1f}%")
                logger.info(f"🔥 Confidence: {action.get('confidence', 0.5)*100:.1f}%")
                logger.info(f"⏱️  Urgency: {action.get('urgency', 'MEDIUM')}")
                logger.info(f"📦 Trade Quantity: {side.upper()} {trade_qty} shares")
                logger.info(f"💭 Reasoning: {action.get('reasoning', 'N/A')}")
                logger.info("=" * 70)
                
                formatted_actions.append(trade)
            
            return {
                "market_overview": analysis.get("market_overview", {}),
                "trades": formatted_actions,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting trades: {e}")
            return None
    
    def _calculate_quantity(self, recommendation: Dict, account_info: Optional[Dict] = None) -> int:
        """
        Calculate quantity based on position size and price using actual account value
        """
        position_size = recommendation.get("position_size", 0.10)
        entry_price = recommendation.get("entry_price_max", 100)
        
        # Use actual account value from Alpaca, fallback to conservative default
        if account_info and "account_value" in account_info:
            account_value = float(account_info["account_value"])
            logger.info(f"Using account value: ${account_value:,.2f}")
        else:
            account_value = 10000.0  # Conservative fallback
            logger.warning(f"No account info provided, using fallback: ${account_value:,.2f}")
        
        position_value = account_value * position_size
        quantity = int(position_value / entry_price)
        
        logger.info(f"Position calculation: {position_size*100:.1f}% of ${account_value:,.2f} = ${position_value:,.2f} ÷ ${entry_price} = {quantity} shares")
        
        return max(1, quantity)
    
    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
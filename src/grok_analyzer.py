import httpx
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from .logger import setup_logger

logger = setup_logger("grok_analyzer")

class GrokAnalyzer:
    def __init__(self, api_key: str, alpaca_trader=None):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.client = None
        self.trade_errors = []  # Track recent trade errors for feedback
        self.alpaca_trader = alpaca_trader  # For market data access
        
        if not self.api_key:
            logger.error("Grok API key is missing!")
    
    def add_trade_error(self, symbol: str, action: str, error_message: str):
        """Add a trade error to be included in the next Grok prompt"""
        error_data = {
            "symbol": symbol,
            "action": action,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        self.trade_errors.append(error_data)
        # Keep only the last 10 errors to avoid prompt bloat
        self.trade_errors = self.trade_errors[-10:]
        logger.info(f"Added trade error for Grok feedback: {symbol} {action} - {error_message}")
    
    def clear_trade_errors(self):
        """Clear trade errors after they've been sent to Grok"""
        self.trade_errors.clear()
        
    async def analyze_market(self, account_info: Optional[Dict] = None, current_positions: Optional[List] = None, open_orders: Optional[List] = None, market_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Queries Grok for market analysis and trading recommendations
        """
        try:
            prompt = self._build_analysis_prompt(account_info, current_positions, open_orders, market_data)
            
            response = await self._call_grok_api(prompt)
            if not response:
                logger.warning("🔄 First attempt failed - trying with reduced search mode")
                # Try once more with auto search mode instead of forced search
                response = await self._call_grok_api(prompt, use_reduced_search=True)
                if not response:
                    return None
            
            # Clear trade errors after sending them to Grok
            self.clear_trade_errors()
                
            return await self.format_trades(response, account_info)
            
        except Exception as e:
            logger.error(f"Error in market analysis: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _build_analysis_prompt(self, account_info: Optional[Dict] = None, current_positions: Optional[List] = None, open_orders: Optional[List] = None, market_data: Optional[Dict] = None) -> str:
        """
        Build comprehensive prompt for Grok analysis
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
        
        # Format account info
        account_summary = "No account info provided"
        if account_info:
            account_summary = f"""
ACCOUNT STATUS: {account_info.get('status', 'UNKNOWN')}
ACCOUNT VALUE: ${account_info.get('account_value', 0):,.2f}
EQUITY: ${account_info.get('equity', 0):,.2f}
BUYING POWER: ${account_info.get('buying_power', 0):,.2f} (Available for new trades)
CASH: ${account_info.get('cash', 0):,.2f} (Settled funds)
DAY TRADE BUYING POWER: ${account_info.get('day_trade_buying_power', 0):,.2f}
LONG MARKET VALUE: ${account_info.get('long_market_value', 0):,.2f}
SHORT MARKET VALUE: ${account_info.get('short_market_value', 0):,.2f}
INITIAL MARGIN: ${account_info.get('initial_margin', 0):,.2f}
MAINTENANCE MARGIN: ${account_info.get('maintenance_margin', 0):,.2f}
SMA (Special Memorandum Account): ${account_info.get('sma', 0):,.2f}
DAY TRADES COUNT: {account_info.get('daytrade_count', 0)}/3 (Pattern day trader: {account_info.get('pattern_day_trader', False)})

⚠️ TRADING RESTRICTIONS:
- Account Blocked: {account_info.get('account_blocked', False)}
- Trading Blocked: {account_info.get('trading_blocked', False)}
- Transfers Blocked: {account_info.get('transfers_blocked', False)}"""

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

        # Format open orders
        orders_summary = ""
        if open_orders:
            orders_list = []
            locked_shares = {}  # Track shares locked in open orders
            for order in open_orders:
                symbol = order.get('symbol', 'UNKNOWN')
                side = order.get('side', 'unknown')
                qty = int(order.get('qty', 0))
                order_type = order.get('order_type', 'unknown')
                
                # Track locked shares for sell orders
                if side == 'sell':
                    locked_shares[symbol] = locked_shares.get(symbol, 0) + qty
                
                orders_list.append(f"""
  {symbol}: {side.upper()} {qty} shares ({order_type})""")
            
            orders_summary = f"""

OPEN ORDERS ({len(open_orders)} pending):
{"".join(orders_list)}

⚠️  LOCKED SHARES IN SELL ORDERS:"""
            for symbol, locked_qty in locked_shares.items():
                orders_summary += f"\n  {symbol}: {locked_qty} shares locked (unavailable for new sell orders)"

        # Format trade errors for feedback
        errors_summary = ""
        if self.trade_errors:
            errors_list = []
            for error in self.trade_errors:
                errors_list.append(f"""
  ❌ {error['symbol']} {error['action']}: {error['error']} (at {error['timestamp']})""")
            
            errors_summary = f"""
        
⚠️  RECENT TRADE EXECUTION ERRORS (CRITICAL - ADJUST YOUR STRATEGY):
{"".join(errors_list)}

🚨 ERROR RESOLUTION GUIDANCE:
- "Insufficient quantity for SYMBOL: requested X, available 0" → You tried to SELL/SHORT a stock you don't own. Either:
  a) Switch to LONG (buy) if bullish
  b) Skip this trade entirely
  c) For shorts, ensure margin account is enabled
  
- "Insufficient buying power" → Reduce position sizes or close existing positions first
- "Available quantity" in errors accounts for LOCKED shares in open orders
- Check the OPEN ORDERS section above to see what shares are already committed

ADJUST YOUR NEXT RECOMMENDATIONS TO AVOID THESE ERRORS!"""

        # Format market data for real-time prices
        market_data_summary = ""
        if market_data:
            market_data_summary = """
📊 REAL-TIME MARKET DATA:
"""
            for symbol, data in market_data.items():
                market_data_summary += f"  {symbol}: ${data.get('price', 'N/A'):.2f} (Last updated: {data.get('timestamp', 'N/A')})\n"

        return f"""
        You are an EXPERT AGGRESSIVE portfolio manager with complete authority over a ${account_info.get('account_value', 100000):,.0f} trading account.
        Current time: {current_time}
        
        🚀 PRIMARY OBJECTIVE: MAXIMIZE PROFITS AS FAST AS POSSIBLE WITHOUT MASSIVE LOSSES
        - Your ONLY goal is to make as much money as possible as quickly as possible
        - Take calculated risks that maximize returns while avoiding catastrophic losses
        - Prioritize speed of profit generation over conservative approaches
        - Use aggressive position sizing on high-conviction opportunities
        - Exit long-term losing positions quickly to preserve capital for better opportunities
        
        🔍 LIVE SEARCH ENABLED: You have real-time access to:
        - Current market prices and trading data
        - Breaking news and market developments
        - Social media sentiment and trending topics on X (Twitter)
        - Company announcements and earnings reports
        USE THIS ACCESS to make informed decisions based on the latest information!
        
        {account_summary}
        
        {positions_summary}{orders_summary}{errors_summary}
        {market_data_summary}
        
        🎯 PORTFOLIO MANAGEMENT INSTRUCTIONS:
        
        ⚠️ CRITICAL BUYING POWER CONSTRAINTS:
        - You MUST check available BUYING POWER before recommending any BUY trades
        - If buying power is low, focus on CLOSING or REDUCING positions first
        - Open sell orders lock up shares - check "LOCKED SHARES IN SELL ORDERS" section
        - DO NOT recommend trades that exceed available buying power
        - Consider the total cost of all recommended buys: (price × quantity) must be < buying power
        
        1. ANALYZE CURRENT POSITIONS: Look at each existing position's P&L and performance
        2. MAKE SPECIFIC ACTIONS: For each stock, decide OPEN/ADD/REDUCE/CLOSE
        3. USE EXACT QUANTITIES: Always specify current_qty (from positions above) and target_qty
        4. BE AGGRESSIVE: Use full buying power for high-conviction plays
        5. SCALE INTELLIGENTLY: Add to winners, trim losers, rotate based on catalysts
        6. OPTIMIZE PORTFOLIO: Ensure the portfolio consists of your highest confidence and highest return predictions

        TRADING PHILOSOPHY: MAXIMUM PROFIT SPEED IS EVERYTHING. Act decisively on breaking news, earnings momentum, and fundamental catalysts. 
        Take concentrated positions in high-conviction opportunities. Risk big to win big, but be strategic about risk management.
        Every trade should maximize profit velocity while protecting against only truly massive losses that could destroy the account.
        
        🔥 AGGRESSIVE LONG/SHORT STRATEGY:
        - LONG overperforming stocks with strong catalysts and momentum (any size tech)
        - SHORT overvalued stocks with negative catalysts, earnings misses, or declining fundamentals  
        - Use cultural momentum for both directions (fade viral hype, short meme crashes)
        - Leverage market inefficiencies and social sentiment extremes
        - EXPLORE smaller tech companies with breakthrough technologies or viral adoption
        - Consider non-tech only for extraordinary opportunities (85%+ confidence required)
        
        📰 MANDATORY WEB SEARCH REQUIREMENTS:
        YOU MUST USE YOUR LIVE SEARCH CAPABILITIES TO:
        1. DISCOVER NEW TRADING OPPORTUNITIES: Search for "stocks surging today", "trending stocks", "biggest movers"
        2. Find EMERGING COMPANIES: Search for "hot IPOs", "small cap tech breakouts", "viral stock picks"
        3. Search for breaking news on ALL stocks you're considering
        4. Check current market sentiment and analyst ratings 
        5. Find earnings announcements, product launches, and company updates
        6. Monitor social media buzz: "stocks trending on Reddit", "WallStreetBets favorites", "FinTwit momentum"
        7. Verify current stock prices and market conditions
        
        🚀 ACTIVELY HUNT FOR NEW OPPORTUNITIES - Don't just analyze the provided list!
        ⚠️ DO NOT make any trading decisions without first searching for the latest information!
        
        ANALYSIS PRIORITIES (in order):
        1. BREAKING NEWS & VIRAL CATALYSTS (USE WEB SEARCH - Last 24-48 hours):
        - Search for: "[stock symbol] news today", "[company] earnings", "[stock] analyst upgrade"
        - Earnings surprises, guidance updates, analyst upgrades/downgrades
        - Product launches, partnerships, regulatory changes
        - SOCIAL MEDIA EXPLOSIONS: Search X/Twitter for trending stocks and sentiment
        - CULTURAL MOMENTUM: Meme stocks, GenZ trends, social media buzz
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
        
        PRIMARY FOCUS - TECH SECTOR (Any Size):
        - LARGE-CAP TECH: NVDA, AAPL, GOOGL, MSFT, AMZN, TSLA, META, AMD, CRM, NFLX, ADBE
        - MID-CAP TECH: PLTR, SNOW, UBER, SQ, SHOP, SNAP, PINS, ZM, DOCU, OKTA, NET, CRWD
        - SMALL-CAP TECH: Emerging AI, cybersecurity, cloud, fintech, biotech companies
        - TECH MOMENTUM: Any tech stock with strong catalysts regardless of market cap
        
        SECONDARY - NON-TECH (High Confidence Only 85%+):
        - Only venture outside tech for exceptional opportunities with strong conviction
        - Consumer brands with viral momentum, healthcare breakthroughs, energy transitions
        - Must have compelling catalyst and 85%+ confidence to justify non-tech exposure
        
        PATTERN RECOGNITION FRAMEWORK:
        - NEWS MOMENTUM: How do similar companies react to comparable catalysts?
        - CULTURAL CYCLES: Which trends are accelerating vs fading?
        - CROSS-PLATFORM AMPLIFICATION: Stories gaining traction across multiple channels
        - DEMOGRAPHIC SHIFTS: Consumer behavior changes driving sector rotation
        - EVENT-DRIVEN OPPORTUNITIES: Earnings, launches, partnerships creating momentum
        
        🔎 EXAMPLE WEB SEARCHES TO PERFORM:
        
        OPPORTUNITY DISCOVERY SEARCHES (DO THESE FIRST):
        - "stocks up 10% today tech sector"
        - "trending stocks X Twitter Reddit"
        - "unusual options activity tech stocks"
        - "stocks hitting 52 week highs technology"
        - "momentum stocks breaking out today"
        - "small cap tech stocks surging"
        - "IPO stocks gaining momentum"
        - "viral stocks social media"
        
        SPECIFIC STOCK RESEARCH:
        - "NVDA earnings results latest"
        - "Tesla news today Elon Musk"  
        - "PLTR stock analyst upgrades"
        - "[New stock you found] news catalyst"
        - "AI stocks news breakthrough"
        - "semiconductor sector movers today"
        - "biotech stocks FDA approval"
        - "[Company] product launch announcement"
        
        YOUR PORTFOLIO MANAGEMENT ACTIONS:
        You have SIX action types available for each stock:
        
        LONG POSITIONS:
        1. OPEN: Start a new LONG position (buy stock, current_qty=0, target_qty>0)
        2. ADD: Increase existing LONG position (buy more shares)
        3. REDUCE: Decrease LONG position (sell some shares, target_qty < current_qty but > 0)
        4. CLOSE: Exit entire LONG position (sell all shares, target_qty=0)
        
        SHORT POSITIONS:
        5. SHORT: Start a new SHORT position (sell short, current_qty=0, target_qty<0)
        6. COVER: Close SHORT position (buy to cover, target_qty=0 from negative)
        
        For each action, specify:
        - EXACT quantities (current_qty and target_qty - negative for short positions)
        - Entry/exit price ranges
        - Stop loss and target prices (inverted logic for shorts)
        - Position size as % of total portfolio
        - Specific catalyst driving this action
        - Confidence level and urgency
        
        IMPORTANT NOTES:
        - Long positions: target_qty > 0 (you own shares)  
        - Short positions: target_qty < 0 (you owe shares)
        - For shorts: stop_loss > entry_price (protect against rising prices)
        - For longs: stop_loss < entry_price (protect against falling prices)
        
        Format as JSON:
        {{{{
            "market_overview": {{{{
                "sentiment": "EXTREMELY_BULLISH/BULLISH/BEARISH/EXTREMELY_BEARISH",
                "key_catalysts": ["specific recent news/events"],
                "dominant_theme": "AI boom/Fed pivot/Earnings season/etc",
                "risk_level": "AGGRESSIVE/MODERATE/CONSERVATIVE",
                "portfolio_analysis": "Assessment of current positions and overall strategy"
            }}}},
            "actions": [
                {{{{
                    "symbol": "STOCK_SYMBOL",
                    "action": "OPEN/ADD/REDUCE/CLOSE/SHORT/COVER",
                    "current_qty": 0,
                    "target_qty": 100,
                    "qty_change": 100,
                    "entry_price_min": 100.00,
                    "entry_price_max": 102.00,
                    "target_price": 125.00,
                    "stop_loss": 92.00,
                    "position_size_pct": 0.35,
                    "holding_period_days": 10,
                    "news_catalyst": "MUST BE from your web search results - specific breaking news",
                    "fundamental_thesis": "Based on search findings - why this position makes sense",
                    "technical_setup": "Chart pattern/momentum from your market analysis",
                    "confidence": 0.85,
                    "urgency": "IMMEDIATE/HIGH/MEDIUM/LOW",
                    "web_search_summary": "Key findings from your web searches that support this trade",
                    "reasoning": "Detailed explanation citing specific search results"
                }}}}
            ]
        }}}}
        
        EXAMPLE ACTIONS:
        
        📈 OPEN LONG: Start new TSLA long position
        {{"symbol": "TSLA", "action": "OPEN", "current_qty": 0, "target_qty": 50, "qty_change": 50}}
        
        🔥 ADD LONG: Increase existing NVDA long position  
        {{"symbol": "NVDA", "action": "ADD", "current_qty": 45, "target_qty": 70, "qty_change": 25}}
        
        📉 REDUCE LONG: Trim AAPL long position
        {{"symbol": "AAPL", "action": "REDUCE", "current_qty": 78, "target_qty": 40, "qty_change": -38}}
        
        🚪 CLOSE LONG: Exit entire META long position
        {{"symbol": "META", "action": "CLOSE", "current_qty": 25, "target_qty": 0, "qty_change": -25}}
        
        🔻 SHORT: Start new NFLX short position (bearish)
        {{"symbol": "NFLX", "action": "SHORT", "current_qty": 0, "target_qty": -30, "qty_change": -30}}
        
        📦 COVER: Close ROKU short position (buy to cover)
        {{"symbol": "ROKU", "action": "COVER", "current_qty": -40, "target_qty": 0, "qty_change": 40}}
        
        ⚠️  CRITICAL: Always include current_qty, target_qty, and qty_change for each action!
        
        URGENCY CLASSIFICATION:
        - IMMEDIATE: Breaking news/viral moments happening RIGHT NOW (trade within 1-2 hours)
        - HIGH: Major catalyst within 24hrs, earnings reactions, upgrade/downgrades  
        - MEDIUM: Strong setup, no immediate catalyst, swing trade opportunity
        - LOW: Longer-term positioning, market conditions unfavorable for aggression
        
        ⚡ CRITICAL TRADING RULES:
        1. ALWAYS perform web searches BEFORE recommending any trades
        2. CITE specific news/data from your searches in the reasoning
        3. If you can't find recent catalysts through search, DON'T trade that stock
        4. Base entry/exit prices on CURRENT market data from searches
        5. Your "news_catalyst" MUST come from actual search results, not assumptions
        
        EXECUTE WITH CONVICTION: Only recommend trades backed by real search data. 
        If searches don't reveal opportunities, recommend waiting for better setups.
        
        STOCK SELECTION CRITERIA:
        - DISCOVERY FIRST: Use search to find NEW opportunities beyond the provided watchlist
        - PRIMARY: Any liquid tech stock with SEARCHABLE catalysts (including newly discovered ones)
        - EMERGING PLAYS: Small/mid-cap tech stocks showing unusual momentum in search results
        - SECONDARY: Non-tech only if search reveals exceptional opportunity (85%+ confidence)
        - LIQUIDITY: Verify through search that stock has adequate volume
        - CATALYSTS: Must be validated through web search, not speculation
        
        💡 PORTFOLIO EXPANSION: Your goal is to find the BEST opportunities across the ENTIRE market,
        not just trade the same familiar stocks. Use search to discover hidden gems!
        
        REMEMBER: NO TRADES WITHOUT SEARCH VALIDATION! Hunt aggressively for new opportunities!
        """
    
    async def _call_grok_api(self, prompt: str, max_retries: int = 3, use_reduced_search: bool = False) -> Optional[str]:
        """
        Make API call to Grok with retry logic and exponential backoff
        """
        if not self.api_key:
            logger.error("Cannot call Grok API - API key is missing")
            return None
            
        if not self.client:
            # Increased timeout for live search operations
            self.client = httpx.AsyncClient(timeout=300.0)  # 5 minutes for search-enabled requests
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Grok, an expert AI trading analyst specializing in tech stock swing trading with real-time market access."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "model": "grok-4-latest",
            "stream": False,
            "temperature": 0.3,
            "search_parameters": {
                "mode": "auto" if use_reduced_search else "on",
                "sources": [
                    {"type": "web"},
                    {"type": "x"},
                    {"type": "news"}
                ],
                "return_citations": False,
                "max_search_results": 3 if use_reduced_search else 20
            }
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🤖 Grok API call attempt {attempt + 1}/{max_retries} - Starting request...")
                logger.info(f"⏱️ Using extended timeout of 300s for live search operations")
                
                start_time = datetime.now()
                response = await self.client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                duration = (datetime.now() - start_time).total_seconds()
                
                if response.status_code == 200:
                    result = response.json()
                    grok_response = result["choices"][0]["message"]["content"]
                    logger.info(f"✅ Grok API call SUCCESSFUL in {duration:.1f}s")
                    logger.info("=== GROK RESPONSE ===")
                    logger.info(grok_response)
                    logger.info("=== END GROK RESPONSE ===")
                    return grok_response
                else:
                    logger.error(f"❌ Grok API error {response.status_code} after {duration:.1f}s: {response.text}")
                    if response.status_code >= 500 and attempt < max_retries - 1:
                        # Server error, retry with backoff
                        backoff_time = 2 ** attempt
                        logger.warning(f"🔄 Server error detected - RETRYING in {backoff_time} seconds (attempt {attempt + 2}/{max_retries})")
                        await asyncio.sleep(backoff_time)
                        continue
                    else:
                        logger.error(f"💀 Grok API failed permanently: {response.status_code} - giving up")
                        return None
                    
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as e:
                duration = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
                logger.warning(f"⏰ TIMEOUT on attempt {attempt + 1} after {duration:.1f}s: {type(e).__name__}")
                logger.info("💡 Tip: Live search operations can take 2-4 minutes. Consider patience or reducing search scope.")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.warning(f"🔄 Timeout detected - RETRYING in {backoff_time} seconds (attempt {attempt + 2}/{max_retries})")
                    await asyncio.sleep(backoff_time)
                    continue
                logger.error(f"💀 All {max_retries} retry attempts failed due to timeout - giving up")
                logger.info("📌 Consider running without live search or with fewer search sources if timeouts persist")
                return None
                
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
                logger.error(f"💥 Unexpected error on attempt {attempt + 1} after {duration:.1f}s: {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                if attempt < max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.warning(f"🔄 Unexpected error - RETRYING in {backoff_time} seconds (attempt {attempt + 2}/{max_retries})")
                    await asyncio.sleep(backoff_time)
                    continue
                import traceback
                logger.error(f"💀 Final attempt failed after {max_retries} tries. Traceback: {traceback.format_exc()}")
                return None
        
        logger.error(f"💀 Exhausted all {max_retries} attempts - Grok API completely failed")
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
                
                # Determine the trade side and quantity based on action type
                if action_type == "OPEN" and qty_change > 0:
                    # Opening long position
                    side = "buy"
                    trade_qty = abs(qty_change)
                elif action_type == "ADD" and qty_change > 0:
                    # Adding to long position
                    side = "buy"
                    trade_qty = abs(qty_change)
                elif action_type == "SHORT" and qty_change < 0:
                    # Opening short position (sell short)
                    side = "sell"
                    trade_qty = abs(qty_change)
                elif action_type == "COVER" and qty_change > 0:
                    # Covering short position (buy to cover)
                    side = "buy"
                    trade_qty = abs(qty_change)
                elif action_type in ["REDUCE", "CLOSE"] and qty_change < 0:
                    # Reducing/closing long position
                    side = "sell"  
                    trade_qty = abs(qty_change)
                elif action_type in ["REDUCE", "CLOSE"] and qty_change > 0:
                    # Reducing short position (partial cover)
                    side = "buy"
                    trade_qty = abs(qty_change)
                else:
                    logger.warning(f"Skipping invalid action for {symbol}: {action_type} with qty_change {qty_change} (current: {current_qty}, target: {target_qty})")
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
                
                # Log detailed action reasoning with position type
                position_type = "📈 LONG" if target_qty > 0 else "📉 SHORT" if target_qty < 0 else "💰 FLAT"
                logger.info(f"=== {position_type} PORTFOLIO ACTION: {action_type} {symbol} ===")
                logger.info(f"🔄 POSITION CHANGE: {current_qty} → {target_qty} shares ({qty_change:+d})")
                logger.info(f"📈 CATALYST: {action.get('news_catalyst', 'N/A')}")
                logger.info(f"💡 THESIS: {action.get('fundamental_thesis', 'N/A')}")
                logger.info(f"📊 TECHNICAL: {action.get('technical_setup', 'N/A')}")
                logger.info(f"💰 Price: ${action.get('entry_price_min', 'N/A')} - ${action.get('entry_price_max', 'N/A')}")
                
                # Handle target/stop logic for both long and short positions  
                if action.get('target_price') and action.get('entry_price_max'):
                    if target_qty > 0:  # Long position
                        target_pct = ((action['target_price']/action['entry_price_max']-1)*100)
                        logger.info(f"🎯 Long Target: ${action['target_price']} ({target_pct:+.1f}%)")
                    elif target_qty < 0:  # Short position  
                        target_pct = ((action['entry_price_max']/action['target_price']-1)*100)
                        logger.info(f"🎯 Short Target: ${action['target_price']} ({target_pct:+.1f}% profit)")
                        
                if action.get('stop_loss') and action.get('entry_price_max'):
                    if target_qty > 0:  # Long position
                        stop_pct = ((action['stop_loss']/action['entry_price_max']-1)*100)
                        logger.info(f"🛑 Long Stop: ${action['stop_loss']} ({stop_pct:+.1f}%)")
                    elif target_qty < 0:  # Short position
                        stop_pct = ((action['entry_price_max']/action['stop_loss']-1)*100)
                        logger.info(f"🛑 Short Stop: ${action['stop_loss']} ({stop_pct:+.1f}% loss)")
                        
                logger.info(f"📊 Target Position Size: {action.get('position_size_pct', 0)*100:.1f}%")
                logger.info(f"🔥 Confidence: {action.get('confidence', 0.5)*100:.1f}%")
                logger.info(f"⏱️  Urgency: {action.get('urgency', 'MEDIUM')}")
                logger.info(f"📦 Trade Execution: {side.upper()} {trade_qty} shares")
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
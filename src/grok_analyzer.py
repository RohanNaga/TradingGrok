import httpx
import json
from typing import Dict, List, Optional
from datetime import datetime
from .logger import setup_logger

logger = setup_logger("grok_analyzer")

class GrokAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def analyze_market(self) -> Optional[Dict]:
        """
        Queries Grok for market analysis and trading recommendations
        """
        try:
            prompt = self._build_analysis_prompt()
            
            response = await self._call_grok_api(prompt)
            if not response:
                return None
                
            return await self.format_trades(response)
            
        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
            return None
    
    def _build_analysis_prompt(self) -> str:
        """
        Build comprehensive prompt for Grok analysis
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
        
        return f"""
        You are an expert swing trader analyzing tech stocks for positions lasting 4 days to 3 weeks.
        Current time: {current_time}
        
        Analyze current market conditions and provide specific trading recommendations:
        
        1. MARKET OVERVIEW:
        - Current tech sector sentiment
        - Key market drivers today
        - Risk factors to consider
        
        2. STOCK RECOMMENDATIONS (provide 2-3 specific stocks):
        For each recommended stock, provide:
        - Symbol (e.g., AAPL, GOOGL, MSFT, NVDA, AMD, TSLA, META, etc.)
        - Action (BUY/SELL/HOLD)
        - Entry Price Range
        - Target Price (for swing trade exit)
        - Stop Loss Price
        - Position Size (as percentage of portfolio, max 25%)
        - Holding Period Estimate (4-21 days)
        - Reasoning (technical/fundamental analysis)
        
        3. RISK ASSESSMENT:
        - Overall market risk level (LOW/MEDIUM/HIGH)
        - Specific risks for each recommendation
        
        Format your response as JSON with this structure:
        {{
            "market_overview": {{
                "sentiment": "BULLISH/BEARISH/NEUTRAL",
                "key_drivers": ["driver1", "driver2"],
                "risk_level": "LOW/MEDIUM/HIGH"
            }},
            "recommendations": [
                {{
                    "symbol": "STOCK_SYMBOL",
                    "action": "BUY/SELL/HOLD",
                    "entry_price_min": 100.00,
                    "entry_price_max": 105.00,
                    "target_price": 120.00,
                    "stop_loss": 95.00,
                    "position_size": 0.20,
                    "holding_period_days": 14,
                    "reasoning": "Detailed analysis here",
                    "confidence": 0.75
                }}
            ]
        }}
        
        Only recommend liquid tech stocks with daily volume > 1M shares.
        Focus on swing trading opportunities with clear technical setups.
        """
    
    async def _call_grok_api(self, prompt: str) -> Optional[str]:
        """
        Make API call to Grok
        """
        try:
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
                "model": "grok-beta",
                "stream": False,
                "temperature": 0.3
            }
            
            response = await self.client.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return None
    
    async def format_trades(self, grok_response: str) -> Optional[Dict]:
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
            
            formatted_trades = []
            for rec in analysis.get("recommendations", []):
                if rec.get("action") == "BUY":
                    trade = {
                        "symbol": rec["symbol"],
                        "side": "buy",
                        "qty": self._calculate_quantity(rec),
                        "type": "limit",
                        "limit_price": rec["entry_price_max"],
                        "time_in_force": "day",
                        "stop_loss": rec["stop_loss"],
                        "target_price": rec["target_price"],
                        "reasoning": rec["reasoning"],
                        "confidence": rec.get("confidence", 0.5),
                        "holding_period": rec.get("holding_period_days", 14)
                    }
                    formatted_trades.append(trade)
            
            return {
                "market_overview": analysis.get("market_overview", {}),
                "trades": formatted_trades,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting trades: {e}")
            return None
    
    def _calculate_quantity(self, recommendation: Dict) -> int:
        """
        Calculate quantity based on position size and price
        Note: This will be updated with actual account value from Alpaca
        """
        position_size = recommendation.get("position_size", 0.10)
        entry_price = recommendation.get("entry_price_max", 100)
        
        account_value = 1000.0
        
        position_value = account_value * position_size
        quantity = int(position_value / entry_price)
        
        return max(1, quantity)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
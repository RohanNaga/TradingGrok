from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import secrets
from typing import Dict
from .config import Config
from .logger import setup_logger

logger = setup_logger("web_dashboard")
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    config = Config()
    correct_password = secrets.compare_digest(credentials.password, config.DASHBOARD_PASSWORD)
    correct_username = secrets.compare_digest(credentials.username, "admin")
    
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

class WebDashboard:
    def __init__(self, trading_bot):
        self.trading_bot = trading_bot
        self.app = FastAPI(title="TradingGrok Dashboard", version="1.0.0")
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "service": "TradingGrok"}
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(username: str = Depends(authenticate)):
            return self.get_dashboard_html()
        
        @self.app.get("/api/status")
        async def get_status(username: str = Depends(authenticate)):
            return self.trading_bot.get_detailed_status()
        
        @self.app.get("/api/account")
        async def get_account(username: str = Depends(authenticate)):
            account_info = self.trading_bot.alpaca_trader.get_account_info()
            portfolio_history = self.trading_bot.alpaca_trader.get_portfolio_history("1D")
            return {
                "account": account_info,
                "history": portfolio_history
            }
        
        @self.app.get("/api/positions")
        async def get_positions(username: str = Depends(authenticate)):
            return self.trading_bot.alpaca_trader.get_positions()
        
        @self.app.get("/api/orders")
        async def get_orders(username: str = Depends(authenticate)):
            return self.trading_bot.alpaca_trader.get_open_orders()
        
        @self.app.post("/api/emergency_stop")
        async def emergency_stop(username: str = Depends(authenticate)):
            await self.trading_bot.stop()
            return {"message": "Trading bot stopped"}
    
    def get_dashboard_html(self) -> str:
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TradingGrok Dashboard</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .card {
                    background: white;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    color: #333;
                }
                .status-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }
                .status-item {
                    text-align: center;
                    padding: 15px;
                    background: #f8f9fa;
                    border-radius: 6px;
                }
                .status-value {
                    font-size: 24px;
                    font-weight: bold;
                    color: #28a745;
                }
                .status-label {
                    font-size: 12px;
                    color: #666;
                    text-transform: uppercase;
                }
                .positions-table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }
                .positions-table th,
                .positions-table td {
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }
                .positions-table th {
                    background-color: #f8f9fa;
                }
                .positive { color: #28a745; }
                .negative { color: #dc3545; }
                .neutral { color: #6c757d; }
                .emergency-btn {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 16px;
                    margin: 10px;
                }
                .emergency-btn:hover {
                    background-color: #c82333;
                }
                .loading {
                    text-align: center;
                    padding: 20px;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h1 class="header">🤖 TradingGrok AI Trading Bot</h1>
                    <div id="status-indicator" class="status-grid">
                        <div class="loading">Loading...</div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Account Overview</h2>
                    <div id="account-info" class="loading">Loading account data...</div>
                </div>
                
                <div class="card">
                    <h2>Current Positions</h2>
                    <div id="positions-info" class="loading">Loading positions...</div>
                </div>
                
                <div class="card">
                    <h2>Open Orders</h2>
                    <div id="orders-info" class="loading">Loading orders...</div>
                </div>
                
                <div class="card">
                    <h2>Last Analysis</h2>
                    <div id="analysis-info" class="loading">Loading analysis...</div>
                </div>
                
                <div class="card">
                    <button class="emergency-btn" onclick="emergencyStop()">🛑 Emergency Stop</button>
                    <p style="font-size: 12px; color: #666;">
                        Dashboard auto-refreshes every 30 seconds<br>
                        Last updated: <span id="last-updated"></span>
                    </p>
                </div>
            </div>
            
            <script>
                function updateTimestamp() {
                    document.getElementById('last-updated').textContent = new Date().toLocaleString();
                }
                
                async function loadDashboardData() {
                    try {
                        const [statusRes, accountRes, positionsRes, ordersRes] = await Promise.all([
                            fetch('/api/status'),
                            fetch('/api/account'),
                            fetch('/api/positions'),
                            fetch('/api/orders')
                        ]);
                        
                        const status = await statusRes.json();
                        const account = await accountRes.json();
                        const positions = await positionsRes.json();
                        const orders = await ordersRes.json();
                        
                        updateStatusDisplay(status);
                        updateAccountDisplay(account);
                        updatePositionsDisplay(positions);
                        updateOrdersDisplay(orders);
                        updateAnalysisDisplay(status.last_analysis);
                        updateTimestamp();
                        
                    } catch (error) {
                        console.error('Error loading dashboard data:', error);
                    }
                }
                
                function updateStatusDisplay(status) {
                    const statusHtml = `
                        <div class="status-item">
                            <div class="status-value ${status.active ? 'positive' : 'negative'}">
                                ${status.active ? '🟢 Active' : '🔴 Stopped'}
                            </div>
                            <div class="status-label">Bot Status</div>
                        </div>
                        <div class="status-item">
                            <div class="status-value">$${status.account_value?.toFixed(2) || '0.00'}</div>
                            <div class="status-label">Account Value</div>
                        </div>
                        <div class="status-item">
                            <div class="status-value">${status.positions_count || 0}</div>
                            <div class="status-label">Open Positions</div>
                        </div>
                        <div class="status-item">
                            <div class="status-value">${status.open_orders_count || 0}</div>
                            <div class="status-label">Open Orders</div>
                        </div>
                        <div class="status-item">
                            <div class="status-value ${status.in_trading_window ? 'positive' : 'neutral'}">
                                ${status.in_trading_window ? '📈 Trading' : '⏰ Waiting'}
                            </div>
                            <div class="status-label">Market Status</div>
                        </div>
                        <div class="status-item">
                            <div class="status-value ${status.paper_trading ? 'neutral' : 'positive'}">
                                ${status.paper_trading ? '📄 Paper' : '💰 Live'}
                            </div>
                            <div class="status-label">Trading Mode</div>
                        </div>
                    `;
                    document.getElementById('status-indicator').innerHTML = statusHtml;
                }
                
                function updateAccountDisplay(data) {
                    const account = data.account;
                    const accountHtml = `
                        <div class="status-grid">
                            <div class="status-item">
                                <div class="status-value">$${account.account_value?.toFixed(2) || '0.00'}</div>
                                <div class="status-label">Portfolio Value</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value">$${account.buying_power?.toFixed(2) || '0.00'}</div>
                                <div class="status-label">Buying Power</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value">$${account.cash?.toFixed(2) || '0.00'}</div>
                                <div class="status-label">Cash</div>
                            </div>
                        </div>
                    `;
                    document.getElementById('account-info').innerHTML = accountHtml;
                }
                
                function updatePositionsDisplay(positions) {
                    if (positions.length === 0) {
                        document.getElementById('positions-info').innerHTML = '<p>No open positions</p>';
                        return;
                    }
                    
                    let tableHtml = `
                        <table class="positions-table">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Quantity</th>
                                    <th>Avg Price</th>
                                    <th>Market Value</th>
                                    <th>P&L</th>
                                    <th>P&L %</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    positions.forEach(pos => {
                        const plClass = pos.unrealized_pl > 0 ? 'positive' : pos.unrealized_pl < 0 ? 'negative' : 'neutral';
                        tableHtml += `
                            <tr>
                                <td><strong>${pos.symbol}</strong></td>
                                <td>${pos.qty}</td>
                                <td>$${pos.avg_entry_price?.toFixed(2)}</td>
                                <td>$${pos.market_value?.toFixed(2)}</td>
                                <td class="${plClass}">$${pos.unrealized_pl?.toFixed(2)}</td>
                                <td class="${plClass}">${(pos.unrealized_plpc * 100)?.toFixed(2)}%</td>
                            </tr>
                        `;
                    });
                    
                    tableHtml += '</tbody></table>';
                    document.getElementById('positions-info').innerHTML = tableHtml;
                }
                
                function updateOrdersDisplay(orders) {
                    if (orders.length === 0) {
                        document.getElementById('orders-info').innerHTML = '<p>No open orders</p>';
                        return;
                    }
                    
                    let tableHtml = `
                        <table class="positions-table">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Side</th>
                                    <th>Quantity</th>
                                    <th>Type</th>
                                    <th>Price</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    orders.forEach(order => {
                        tableHtml += `
                            <tr>
                                <td><strong>${order.symbol}</strong></td>
                                <td>${order.side.toUpperCase()}</td>
                                <td>${order.qty}</td>
                                <td>${order.type.toUpperCase()}</td>
                                <td>$${order.limit_price?.toFixed(2) || order.stop_price?.toFixed(2) || 'Market'}</td>
                                <td>${order.status}</td>
                            </tr>
                        `;
                    });
                    
                    tableHtml += '</tbody></table>';
                    document.getElementById('orders-info').innerHTML = tableHtml;
                }
                
                function updateAnalysisDisplay(analysis) {
                    if (!analysis) {
                        document.getElementById('analysis-info').innerHTML = '<p>No recent analysis available</p>';
                        return;
                    }
                    
                    const market = analysis.market_overview || {};
                    const trades = analysis.trades || [];
                    
                    let analysisHtml = `
                        <div class="status-grid">
                            <div class="status-item">
                                <div class="status-value">${market.sentiment || 'N/A'}</div>
                                <div class="status-label">Market Sentiment</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value">${market.risk_level || 'N/A'}</div>
                                <div class="status-label">Risk Level</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value">${trades.length}</div>
                                <div class="status-label">Recommendations</div>
                            </div>
                        </div>
                    `;
                    
                    if (trades.length > 0) {
                        analysisHtml += '<h4>Recent Recommendations:</h4><ul>';
                        trades.forEach(trade => {
                            analysisHtml += `<li><strong>${trade.symbol}</strong> - ${trade.side.toUpperCase()} at $${trade.limit_price?.toFixed(2)} (Confidence: ${(trade.confidence * 100)?.toFixed(0)}%)</li>`;
                        });
                        analysisHtml += '</ul>';
                    }
                    
                    document.getElementById('analysis-info').innerHTML = analysisHtml;
                }
                
                async function emergencyStop() {
                    if (confirm('Are you sure you want to stop the trading bot?')) {
                        try {
                            await fetch('/api/emergency_stop', { method: 'POST' });
                            alert('Trading bot has been stopped');
                            location.reload();
                        } catch (error) {
                            alert('Error stopping bot: ' + error.message);
                        }
                    }
                }
                
                // Load data on page load
                loadDashboardData();
                
                // Auto-refresh every 30 seconds
                setInterval(loadDashboardData, 30000);
            </script>
        </body>
        </html>
        """
# TradingGrok - AI-Powered Trading Bot

An intelligent trading bot that leverages Grok AI for market analysis and Alpaca Markets for trade execution, focusing on swing trading tech stocks.

## Features

- 🤖 **AI-Powered Analysis**: Uses Grok AI for market sentiment and trade recommendations
- 📈 **Swing Trading Strategy**: Optimized for 4-day to 3-week holding periods
- 🎯 **Tech Stock Focus**: Specialized in technology sector opportunities
- 📊 **Real-time Dashboard**: Web interface for monitoring and control
- 🛡️ **Risk Management**: Built-in position sizing and stop-loss mechanisms
- 📋 **Paper Trading**: Safe testing environment before live trading
- 🚀 **Cloud Ready**: Docker containerized for Railway deployment

## Quick Start

### Prerequisites

1. **API Keys Required**:
   - Grok API key (from X.AI)
   - Alpaca Markets API credentials (free paper trading account)

2. **Python 3.11+** installed

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd TradingGrok
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the bot**:
   ```bash
   # With web dashboard (recommended)
   python main.py
   
   # Bot only (no web interface)
   python main.py bot-only
   ```

5. **Access dashboard**:
   Open http://localhost:8000 in your browser
   - Username: `admin`
   - Password: Set in `.env` file (`DASHBOARD_PASSWORD`)

## Configuration

### Environment Variables

Create a `.env` file with:

```env
GROK_API_KEY=your_grok_api_key_here
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
PAPER_TRADING=true
DASHBOARD_PASSWORD=admin123
MAX_POSITION_SIZE=0.25
MAX_POSITIONS=4
LOG_LEVEL=INFO
```

### Trading Parameters

- **MAX_POSITION_SIZE**: Maximum percentage of portfolio per position (default: 25%)
- **MAX_POSITIONS**: Maximum number of concurrent positions (default: 4)
- **Trading Hours**: 7:50 AM - 4:10 PM EST (with 10-minute buffers)
- **Analysis Frequency**: Every 10 minutes during trading hours

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Grok API      │────▶│  Trading Bot    │────▶│  Alpaca API     │
│  (Analysis)     │     │   (FastAPI)     │     │  (Execution)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Web Dashboard  │
                        │    (HTML/JS)    │
                        └─────────────────┘
```

## API Endpoints

- `GET /` - Web dashboard
- `GET /api/status` - Bot status and summary
- `GET /api/account` - Account information and history
- `GET /api/positions` - Current positions
- `GET /api/orders` - Open orders
- `POST /api/emergency_stop` - Emergency stop button

## Risk Management

### Built-in Safety Features

1. **Position Sizing**: Automatic calculation based on account value
2. **Stop Losses**: Implemented for each position (-5% loss trigger)
3. **Take Profits**: Automatic exits at +15% gains
4. **Max Positions**: Prevents over-diversification
5. **Paper Trading**: Default safe mode for testing
6. **Trading Hours**: Restricted to market hours only

### Emergency Controls

- Emergency stop button in dashboard
- Manual position management
- Real-time monitoring and alerts

## Deployment

### Local Development

```bash
python main.py
```

### Docker

```bash
docker build -t tradinggrok .
docker run -p 8000:8000 --env-file .env tradinggrok
```

### Railway (Recommended)

1. **Connect your repository** to Railway
2. **Set environment variables** in Railway dashboard
3. **Deploy automatically** from your main branch

Environment variables to set in Railway:
- `GROK_API_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `PAPER_TRADING=false` (for live trading)
- `DASHBOARD_PASSWORD`

## Monitoring

### Dashboard Features

- Real-time account value tracking
- Position monitoring with P&L
- Trade execution history
- Grok analysis results
- Emergency controls

### Logging

- Comprehensive logging to files and console
- Daily log rotation
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- Structured logging for analysis

## Development

### Project Structure

```
TradingGrok/
├── src/
│   ├── config.py           # Configuration management
│   ├── logger.py           # Logging setup
│   ├── grok_analyzer.py    # Grok AI integration
│   ├── alpaca_trader.py    # Alpaca trading interface
│   ├── trading_bot.py      # Main bot logic
│   └── web_dashboard.py    # Web interface
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── railway.json           # Railway deployment config
└── README.md              # This file
```

### Adding Features

1. **New Trading Strategies**: Extend `trading_bot.py`
2. **Additional APIs**: Create new modules in `src/`
3. **Dashboard Enhancements**: Modify `web_dashboard.py`
4. **Risk Management**: Update position management logic

## Troubleshooting

### Common Issues

1. **API Key Errors**: Verify all API keys are correctly set
2. **Market Hours**: Bot only trades during market hours
3. **Paper Trading**: Ensure you're using paper trading for testing
4. **Network Issues**: Check internet connectivity for API calls

### Debug Mode

```bash
LOG_LEVEL=DEBUG python main.py
```

### Logs Location

- Console output for real-time monitoring
- File logs in `logs/` directory
- Daily rotation with timestamps

## Security

- API keys stored as environment variables
- Basic authentication for dashboard
- No sensitive data in logs
- HTTPS recommended for production
- Regular security updates

## Performance

- Asynchronous processing for API calls
- Efficient polling intervals
- Minimal resource usage
- Scalable architecture

## Disclaimer

⚠️ **Important**: This software is for educational and research purposes. Trading involves significant financial risk. Always:

- Start with paper trading
- Never invest more than you can afford to lose
- Understand the risks involved
- Monitor your positions actively
- Keep up with market conditions

The developers are not responsible for any financial losses incurred while using this software.

## License

This project is provided as-is for educational purposes. See license file for details.

## Support

For issues and questions:
1. Check the logs for error messages
2. Verify API key configuration
3. Ensure proper network connectivity
4. Review the troubleshooting section

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

**Happy Trading! 🚀📈**
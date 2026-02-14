# 📈 SPY Elliott Wave Scanner

> **Automated Elliott Wave detection and alert system for SPY** with Fibonacci mapping, divergence detection, and real-time alerts via GitHub Actions
>
> [![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen)](https://prcasley.github.io/spy-wave-scanner/)
> [![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
> [![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
>
> ---
>
> ## 🎯 What is This?
>
> The SPY Elliott Wave Scanner is a **fully automated**, rules-based Elliott Wave scanning system that runs in the cloud via GitHub Actions. It:
>
> - 🔍 **Detects** 5-wave impulse and ABC corrective patterns on SPY intraday and daily timeframes
> - - 📊 **Maps** Fibonacci retracement and extension levels from detected swing pivots
>   - - 🚨 **Alerts** in real-time when price approaches key wave targets, invalidation levels, or confluence zones
>     - - ✅ **Validates** every wave count against the three cardinal Elliott Wave rules
>       - - 📉 **Visualizes** everything in a dark-themed dashboard (candlesticks, wave labels, fib lines, RSI/MACD panels)
>        
>         - **No more manual chart work** — wave counting, fib drawing, and level-watching happen automatically every 5 minutes during market hours!
>        
>         - ---
>
> ## ✨ Key Features
>
> ### 🤖 Automated Detection
> - Runs every 5 minutes during US market hours (9:30 AM - 4:00 PM ET)
> - - Identifies swing highs/lows using configurable sensitivity
>   - - Enforces Elliott Wave rules: Wave 2 retrace < 100%, Wave 3 not shortest, Wave 4 no overlap
>    
>     - ### 📐 Fibonacci Mapping
>     - - Automatic calculation of retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)
>       - - Extension levels (100%, 127.2%, 138.2%, 161.8%, 200%, 261.8%)
>         - - Confluence zone detection where multiple fib levels cluster
>          
>           - ### 📱 Real-Time Alerts
>           - - Slack webhook integration
>             - - Email notifications
>               - - SMS via Twilio (optional)
>                 - - Alert types: Wave 5 completing, invalidation breached, confluence zones, Wave 4 resistance
>                  
>                   - ### 📊 Visualization Dashboard
>                   - - Dark-themed Streamlit interface
>                     - - Live candlestick charts with wave labels
>                       - - Fibonacci horizontal lines
>                         - - RSI and MACD sub-panels
>                           - - Alert history and projections
>                            
>                             - ### 🔧 Fully Configurable
>                             - - Adjust pivot sensitivity (aggressive/balanced/conservative)
>                               - - Set minimum swing percentages
>                                 - - Configure alert proximity thresholds
>                                   - - Customize indicator periods (RSI, MACD)
>                                    
>                                     - ---
>
> ## 🚀 Quick Start
>
> ### Prerequisites
> - Python 3.11+
> - - Polygon.io API key ([get one free](https://polygon.io/))
>   - - Slack webhook (optional, for alerts)
>    
>     - ### Installation
>    
>     - ```bash
>       # Clone the repository
>       git clone https://github.com/prcasley/spy-wave-scanner.git
>       cd spy-wave-scanner
>
>       # Install dependencies
>       pip install -r requirements.txt
>
>       # Set up environment variables
>       export POLYGON_API_KEY="your_polygon_api_key"
>       export SLACK_WEBHOOK="https://hooks.slack.com/services/..."  # optional
>       ```
>
> ### Running the Scanner
>
> ```bash
> # Run once (CLI)
> python scripts/run_scanner.py
>
> # Run with custom parameters
> python scripts/run_scanner.py --ticker AVGO --timeframe 15min
>
> # Launch the dashboard
> python scripts/run_scanner.py --dashboard
> # or
> streamlit run src/dashboard.py
> ```
>
> ### Running Tests
>
> ```bash
> pip install pytest
> pytest tests/ -v
> ```
>
> ---
>
> ## 🏗️ Project Structure
>
> ```
> spy-wave-scanner/
> ├── .github/workflows/    # GitHub Actions automation
> │   └── scanner.yml       # Runs every 5 min during market hours
> ├── config/              # Configuration files
> │   ├── settings.yaml    # Timeframes, pivot sensitivity, fib levels
> │   └── alert_config.yaml # Slack, email, SMS settings
> ├── src/                 # Core scanner code
> │   ├── models.py        # Data classes (Pivot, WaveCount, Alert)
> │   ├── data_feed.py     # Polygon.io data fetching
> │   ├── pivot_detector.py # Swing high/low identification
> │   ├── fib_mapper.py    # Fibonacci calculations
> │   ├── wave_counter.py  # Elliott Wave pattern matching
> │   ├── divergence.py    # RSI/MACD divergence detection
> │   ├── alert_engine.py  # Notification dispatch
> │   └── dashboard.py     # Streamlit visualization
> ├── scripts/             # Entry points
> │   ├── run_scanner.py   # Main orchestrator
> │   ├── backtest.py      # Historical validation
> │   └── calibrate.py     # Parameter optimization
> └── tests/               # Test suite
> ```
>
> ---
>
> ## 🎨 Architecture
>
> ```
> ┌─────────────────────────────────────────────────────────────┐
> │                     SPY WAVE SCANNER                        │
> ├─────────────────────────────────────────────────────────────┤
> │                                                             │
> │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
> │  │  DATA FEED   │─▶│  WAVE ENGINE │─▶│  ALERT ENGINE  │   │
> │  │  (Polygon)   │  │              │  │                │   │
> │  └──────────────┘  └──────────────┘  └────────────────┘   │
> │         │                 │                    │           │
> │         ▼                 ▼                    ▼           │
> │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
> │  │ OHLCV Data   │  │ Wave Count   │  │ Slack/Email    │   │
> │  │ RSI / MACD   │  │ Fib Levels   │  │ SMS (Twilio)   │   │
> │  │ Volume Prof  │  │ Invalidation │  │ Dashboard      │   │
> │  └──────────────┘  └──────────────┘  └────────────────┘   │
> │                                                             │
> └─────────────────────────────────────────────────────────────┘
> ```
>
> ---
>
> ## ⚙️ Configuration
>
> Edit `config/settings.yaml`:
>
> ```yaml
> ticker: SPY
> timeframes:
>   primary: "5min"
>   confirmation: "15min"
>
> pivot_detection:
>   sensitivity: 5              # 3=aggressive, 5=balanced, 8=conservative
>   min_swing_pct: 0.3         # ~$2 move on SPY at $685
>
> fibonacci:
>   confluence_tolerance: 0.50  # Price range for confluence zones
>
> alerts:
>   proximity_threshold_pct: 0.15  # Alert when within 0.15% of target
>   cooldown_minutes: 15
>
> indicators:
>   rsi_periods: [7, 14]
>   macd_fast: 5
>   macd_slow: 13
>   macd_signal: 8
> ```
>
> ---
>
> ## 🤝 Integration with Options Flow Scanner
>
> This wave scanner is designed to work alongside an Options Flow Scanner for powerful combined signals:
>
> - **Wave targets inform options entries**: Wave 5 target at $680 + unusual put activity = high conviction setup
> - - **Options flow confirms wave counts**: Large blocks at Fibonacci levels validate the count
>   - - **Invalidation levels become triggers**: Price breaching key levels + shift in put/call ratio = early warning
>     - - **Shared data feed**: Both scanners use the same Polygon.io API
>      
>       - ```
>         Options Flow Scanner        Wave Scanner
>         │                           │
>         │ unusual put sweep @ $680  │ Wave 5 target = $680.63
>         │ RSI bullish divergence    │
>         ▼                           ▼
>         ┌──────────────────────────────────────────┐
>         │      COMBINED SIGNAL ENGINE              │
>         │                                          │
>         │  Wave target + options flow = HIGH       │
>         │  conviction setup → ALERT                │
>         └──────────────────────────────────────────┘
>         ```
>
> ---
>
> ## 🧪 Backtesting & Calibration
>
> ```bash
> # Backtest over 30 days of 5-min data
> python scripts/backtest.py --ticker SPY --days 30
>
> # Auto-calibrate pivot sensitivity and swing thresholds
> python scripts/calibrate.py --ticker SPY --days 30
> ```
>
> ---
>
> ## 🌐 GitHub Actions Deployment
>
> The scanner runs automatically via GitHub Actions every 5 minutes during market hours.
>
> **Setup:**
>
> 1. Go to repository **Settings** → **Secrets and variables** → **Actions**
> 2. 2. Add the following secrets:
>    3.    - `POLYGON_API_KEY` - Your Polygon.io API key (required)
>          -    - `SLACK_WEBHOOK` - Slack webhook URL (optional)
>               -    - `ALERT_EMAIL` - Email for alerts (optional)
>                    -    - `SMTP_PASSWORD` - SMTP password (optional)
>                     
>                         - The workflow will automatically:
>                         - - ✅ Fetch latest SPY data
>                           - - ✅ Detect wave patterns
>                             - - ✅ Send alerts on key levels
>                               - - ✅ Run tests on every push
>                                
>                                 - ---
>
> ## 📊 Live Dashboard
>
> Visit the **[Live GitHub Pages Site](https://prcasley.github.io/spy-wave-scanner/)** for documentation and project overview.
>
> To run the dashboard locally:
>
> ```bash
> streamlit run src/dashboard.py
> ```
>
> ---
>
> ## 🛠️ Tech Stack
>
> - **Python 3.11+** - Core language
> - - **Polygon.io API** - Real-time market data
>   - - **GitHub Actions** - Cloud automation
>     - - **Streamlit** - Interactive dashboard
>       - - **Slack/Email/SMS** - Alert notifications
>        
>         - ---
>
> ## 📝 License
>
> MIT License - feel free to use for personal or commercial projects!
>
> ---
>
> ## 🤖 Built with Claude
>
> This project was created with assistance from Claude (Anthropic). The entire scanner implementation, GitHub Actions workflow, and documentation were developed through collaborative AI-assisted coding.
>
> ---
>
> ## 🔗 Links
>
> - 📖 **[Documentation](https://prcasley.github.io/spy-wave-scanner/)**
> - - 🐛 **[Report Issues](https://github.com/prcasley/spy-wave-scanner/issues)**
>   - - 💬 **[Discussions](https://github.com/prcasley/spy-wave-scanner/discussions)**
>    
>     - ---
>
> **⚡ Ready to eliminate manual Elliott Wave analysis? Clone the repo and start scanning!**

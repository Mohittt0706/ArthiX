# ArthiX

**AI-Powered Multi-Agent Market Intelligence for Indian Stocks**

ArthiX is a public, multi-user web application for Indian stock market analysis. It uses a panel of specialized AI agents that analyze evidence, debate bull and bear cases, and produce a final verdict with confidence scoring.

---

## Architecture

```
Frontend (Jinja2 + CSS/JS)
        ↓
   Flask Backend API
        ↓
   Authentication (Flask sessions)
        ↓
   Analysis Service (pipeline orchestrator)
        ↓
   Data Service (evidence collection)
        ↓
   Agent Engine (8 specialized agents)
        ↓
    Scoring Engine (deterministic) + LLM Engine (optional)
         ↓
    MariaDB (via SQLAlchemy ORM)
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `app.py` | Flask application factory and routes |
| `config.py` | Environment-based configuration |
| `backend/api/` | REST API endpoints (auth, analysis, watchlist, settings) |
| `backend/auth/` | User registration, login, password hashing, session middleware |
| `backend/services/` | Analysis pipeline, caching, rate limiting |
| `agents/` | 8 specialized AI agents |
| `data/` | Data sources (demo + live via yfinance), evidence normalization |
| `engine/` | Scoring engine, LLM provider abstraction, grounding verifier |
| `frontend/` | HTML templates and static CSS/JS |
| `database/` | SQLAlchemy models, session factory, MariaDB/PostgreSQL abstraction |
| `tests/` | Unit and integration tests |

---

## How Analysis Works

1. **User searches** for an Indian stock (e.g., TCS, INFY, RELIANCE)
2. **Scout** screens the stock and identifies its profile
3. **Evidence is collected** — price data, technicals, analyst info, news
4. **Technician** analyzes price action, volume, trend, and moving averages
5. **Fundamentalist** weighs valuation, analyst targets, and buy/hold/sell ratios
6. **Newsdesk** scores news sentiment and highlights recent headlines
7. **Bull** argues the case to buy based on bullish signals
8. **Bear** argues the case against buying based on bearish risks
9. **Judge** weighs the debate and issues a verdict:
   - **BUY** — strong bullish conviction
   - **WATCH** — mixed signals, wait for clarity
   - **AVOID** — bearish dominance
10. **Messenger** optionally sends Telegram notifications for BUY signals

### Deterministic Scoring

The scoring engine works **without any LLM API key**. It uses rule-based logic:

**Bull factors**: High RVOL, 52-week position, uptrend, strong close, analyst upside, positive news

**Bear factors**: Low RVOL, near 52-week low, downtrend, weak close, high sell %, negative news

**Verdict rules**:
- BUY: net ≥ 25 AND (52-week position ≥ 60 OR RVOL ≥ 3)
- AVOID: net ≤ -15
- WATCH: otherwise

**Confidence**: `clamp(round(4 + net/15), 1, 10)` — BUY ≥ 7, WATCH/AVOID ≤ 6

---

## Agent Roles

| Agent | Responsibility |
|-------|---------------|
| **Scout** | Screens the stock universe, identifies profile and data coverage |
| **Technician** | Reads price action, RVOL, trend, SMA, and momentum |
| **Fundamentalist** | Weighs valuation, analyst targets, and consensus |
| **Newsdesk** | Pulls news, scores sentiment (positive/negative/neutral) |
| **Bull** | Argues the case to buy with conviction scoring |
| **Bear** | Argues the case against buying with conviction scoring |
| **Judge** | Weighs the debate, issues verdict, confidence, rationale, key catalyst |
| **Messenger** | Delivers signals via Telegram when criteria are met |

---

## Market Terminology

| Term | Explanation |
|------|-------------|
| **RVOL** | Relative Volume — trading activity compared to normal volume |
| **SMA** | Simple Moving Average — average price over a period (typically 20 days) |
| **52-week high/low** | Highest/lowest price over approximately one year |
| **Analyst target** | Consensus price target from financial analysts |
| **Trend** | Uptrend (rising), Downtrend (falling), or Sideways (range-bound) |
| **News sentiment** | Positive, Neutral, or Negative based on recent news analysis |

---

## Demo Mode

Demo mode works **completely offline** without API keys or internet:

- Sample evidence bundles are generated with realistic data
- Deterministic scoring produces BUY/WATCH/AVOID verdicts
- No LLM calls are made
- Clearly labeled as demo data

To use demo mode (default):
```bash
DEMO_MODE=true python app.py
```

---

## Live Mode

Live mode fetches real market data via yfinance:

- Indian NSE tickers use `.NS` suffix (e.g., TCS.NS)
- Collects ~1 month of daily OHLC data
- Fetches available `.info` fields from yfinance
- Collects available news headlines

To use live mode:
```bash
DEMO_MODE=false python app.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Security
SECRET_KEY=your-random-secret-key

# Mode
DEMO_MODE=auto          # true, false, or auto

# Database (MariaDB)
DATABASE_URL=mysql+pymysql://username:password@localhost:3307/arthix

# LLM (optional)
LLM_PROVIDER=auto       # auto, claude_cli, anthropic, openai, none
ANTHROPIC_API_KEY=       # Your Anthropic API key
OPENAI_API_KEY=          # Your OpenAI API key

# Telegram (optional)
TELEGRAM_BOT_TOKEN=      # Telegram bot token
TELEGRAM_CHAT_ID=        # Target chat ID
CONFIDENCE_THRESHOLD=7   # Min confidence to send BUY signal

# Server
PORT=5000
```

---

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd ArthiX

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings (especially DATABASE_URL)

# Run the application
python app.py
```

Open http://localhost:5000 in your browser.

---

## MariaDB Setup

ArthiX uses **MariaDB** as its production database via **SQLAlchemy ORM** (database-agnostic — switch to PostgreSQL by changing `DATABASE_URL`).

### Install MariaDB

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install mariadb-server mariadb-client
sudo systemctl start mariadb
sudo systemctl enable mariadb
```

**macOS (Homebrew):**
```bash
brew install mariadb
brew services start mariadb
```

**Windows:**
Download from https://mariadb.org/download/ and run the installer.

### Create Database and User

```sql
-- Connect to MariaDB
mysql -u root -p

-- Create database
CREATE DATABASE arthix CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user (adjust username/password)
CREATE USER 'arthix'@'localhost' IDENTIFIED BY 'your-secure-password';

-- Grant privileges
GRANT ALL PRIVILEGES ON arthix.* TO 'arthix'@'localhost';
FLUSH PRIVILEGES;
```

### Configure `.env`

```bash
DATABASE_URL=mysql+pymysql://arthix:your-secure-password@localhost:3307/arthix
```

### Tables

Tables are created automatically on first run via `Base.metadata.create_all()`. No manual migration needed for development.

For production, consider using **Alembic** for schema migrations.

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover:
- Evidence normalization and missing data handling
- RVOL, SMA, and trend calculations
- Deterministic scoring engine
- BUY/WATCH/AVOID verdict rules
- Confidence score calculation
- Grounding verifier
- Authentication and user isolation
- API endpoints

---

## LLM Configuration

ArthiX supports multiple LLM providers with automatic fallback:

1. **Claude Code CLI** — Detected automatically if installed
2. **Anthropic API** — Requires `ANTHROPIC_API_KEY`
3. **OpenAI API** — Requires `OPENAI_API_KEY`
4. **Deterministic fallback** — Always available, no API key needed

Set `LLM_PROVIDER` to control which provider is used:
- `auto` — Try all available providers in order
- `claude_cli` — Use only Claude CLI
- `anthropic` — Use only Anthropic API
- `openai` — Use only OpenAI API
- `none` — Use only deterministic scoring

---

## Telegram Configuration

Optional Telegram notifications for BUY signals:

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get the bot token
3. Get your chat ID (message the bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`)
4. Set environment variables:
   ```
   TELEGRAM_BOT_TOKEN=your-bot-token
   TELEGRAM_CHAT_ID=your-chat-id
   CONFIDENCE_THRESHOLD=7
   ```

Signal format:
```
🟢 BUY SIGNAL — TCS

Verdict: BUY | Confidence: 8/10
Winner: Bull
Why: Strong bullish signals...
Key catalyst: Unusual volume spike (2.5x average)
Live price: ₹3,500 | Day change: +1.5%

— Analysis only. No trade was placed. Not investment advice.
```

---

## Project Structure

```
ArthiX/
├── app.py                    # Flask application
├── config.py                 # Configuration
├── requirements.txt          # Dependencies
├── .env.example              # Environment template
├── .gitignore                # Git ignore rules
├── README.md                 # This file
│
├── backend/
│   ├── auth/
│   │   ├── service.py        # User registration, authentication
│   │   └── middleware.py      # Login required decorator
│   ├── api/
│   │   ├── auth.py           # Auth endpoints
│   │   ├── analysis.py       # Analysis endpoints
│   │   ├── watchlist.py      # Watchlist endpoints
│   │   └── settings.py       # User settings endpoints
│   └── services/
│       ├── analysis.py       # Pipeline orchestrator
│       └── cache.py          # Caching and rate limiting
│
├── agents/
│   ├── scout.py              # Stock screening agent
│   ├── technician.py         # Technical analysis agent
│   ├── fundamentalist.py     # Fundamental analysis agent
│   ├── newsdesk.py           # News sentiment agent
│   ├── bull.py               # Bull case agent
│   ├── bear.py               # Bear case agent
│   ├── judge.py              # Verdict agent
│   └── messenger.py          # Telegram delivery agent
│
├── data/
│   ├── data_sources.py       # Evidence collection (demo + live)
│   ├── evidence.py           # Evidence normalization
│   └── universe.json         # Stock universe (large/mid/small cap)
│
├── engine/
│   ├── scoring.py            # Deterministic scoring engine
│   ├── llm.py                # LLM provider abstraction
│   └── verifier.py           # Grounding/anti-hallucination verifier
│
├── frontend/
│   ├── templates/
│   │   ├── base.html         # Base template with navbar
│   │   ├── login.html        # Login page
│   │   ├── register.html     # Registration page
│   │   ├── dashboard.html    # Main dashboard with search
│   │   ├── analysis.html     # Full analysis view
│   │   ├── history.html      # Analysis history
│   │   └── watchlist.html    # Stock watchlist
│   └── static/
│       └── css/
│           └── style.css     # Dark finance dashboard theme
│
├── demo_data/                # Generated demo evidence bundles
├── database/                 # SQLAlchemy models and session factory
└── tests/
    ├── test_scoring.py       # Scoring engine tests
    ├── test_evidence.py      # Evidence normalization tests
    ├── test_verifier.py      # Verifier tests
    └── test_app.py           # Integration tests
```

---

## Public Deployment Considerations

When deploying to production:

1. **Set `SECRET_KEY`** to a strong random value
2. **Set `SESSION_COOKIE_SECURE=true`** for HTTPS
3. **Configure MariaDB** — set `DATABASE_URL` with secure credentials
4. **Set `DEMO_MODE=false`** and configure LLM API keys
5. **Use a production WSGI server** (gunicorn, waitress)
6. **Set up reverse proxy** (nginx, Cloudflare)
7. **Enable rate limiting** on API endpoints
8. **Monitor LLM costs** if using paid API providers
9. **Use Alembic** for schema migrations in production

---

## Security

- Passwords are hashed using Werkzeug's `generate_password_hash` (pbkdf2)
- Session-based authentication with Flask sessions
- API keys and secrets are never exposed to the frontend
- User isolation — users cannot access each other's analysis history
- Rate limiting prevents API abuse
- Input validation on all API endpoints

---

## Disclaimer

ArthiX is an **analysis platform**, not a financial advisor.

- No guaranteed returns or predictions
- No guaranteed profits
- No certainty about future prices
- Analysis results are AI-generated market assessments for informational purposes only
- **Always include**: "Analysis only. Not investment advice."
- **No trade is ever placed** by ArthiX

---

## License

This project is for educational and personal use. Not for commercial redistribution without permission.

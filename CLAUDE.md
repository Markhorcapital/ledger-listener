# Claude AI Context - Markhor CEX Balance Service

This document provides context for AI assistants (Claude, etc.) working on this project.

## Project Overview

**Purpose:** Automated cryptocurrency exchange balance fetching service for Markhor market making operations.

**Tech Stack:**
- FastAPI (async Python web framework)
- MongoDB (credential storage)
- CCXT (exchange API library)
- Docker (containerization)
- Google Apps Script (sheet automation)

**Flow:**
```
MongoDB → FastAPI → CCXT → Exchanges (Gate.io, HTX, MEXC, Crypto.com)
                       ↓
                Google Apps Script → Google Sheets (daily 7 PM update)
```

## Architecture Principles

### 1. Dynamic & Config-Driven
- **NO hardcoded values** - All configuration in `backend/config.yml`
- Exchange mappings, timeouts, MongoDB credentials → config file
- Add new exchanges without code changes

### 2. Minimal & Reusable
- **Single purpose:** Fetch balances, return JSON
- **No unnecessary abstractions** - Direct, simple code
- **Easy to copy** - Self-contained, minimal dependencies
- Keep codebase under 500 lines total

### 3. Database-Driven Accounts
- Reads ALL accounts from MongoDB `cexaccounts` collection
- Filters by `isActive: true` automatically
- No restart needed when accounts change
- Dynamic discovery of exchanges

## Code Structure

```
backend/app/
├── main.py              # FastAPI app, endpoints, auth
├── config.py            # YAML config loader
├── database.py          # MongoDB connection & queries
├── models.py            # Pydantic schemas for validation
└── services/
    └── exchange_service.py  # CCXT wrapper, balance fetching
```

### Key Files

**config.yml** - Single source of truth
- MongoDB connection
- API authentication token
- Exchange name mappings (DB name → CCXT ID)
- Timeouts, rate limits

**database.py** - MongoDB operations
- `get_active_accounts()` - Fetches all `isActive: true` accounts
- Returns list of account dicts with credentials

**exchange_service.py** - CCXT integration
- `_get_exchange_instance()` - Creates CCXT exchange client
- `fetch_balance_async()` - Fetches one account (async)
- `fetch_all_balances()` - Fetches all accounts in parallel

**main.py** - API endpoints
- `GET /health` - Health check (no auth)
- `GET /api/balances` - All balances (requires Bearer token)
- `GET /api/balances/summary` - Grouped summary (requires Bearer token)

## Design Decisions

### Why CCXT instead of Hummingbot connectors?
- **Hummingbot:** Complex, trading-focused, custom per exchange
- **CCXT:** Battle-tested, 100+ exchanges, simple balance fetching
- **Decision:** Use CCXT - simpler, sufficient for read-only operations

### Why MongoDB for credentials?
- Already in use by Markhor infrastructure
- Existing `cexaccounts` collection
- Dynamic account management (add/remove without code changes)

### Why FastAPI instead of Flask?
- Native async support (parallel exchange requests)
- Automatic API documentation (Swagger)
- Type validation with Pydantic
- Modern, fast, easy to deploy

### Why Google Apps Script instead of server-side sheet updates?
- **Apps Script:** Direct sheet access, free triggers, no OAuth complexity
- **Server-side:** Requires OAuth2, service accounts, more setup
- **Decision:** Apps Script for simplicity, FastAPI for heavy lifting

## Configuration Schema

### MongoDB Connection
```yaml
mongodb:
  host: 
  port: 27017
  username: 
  password: 
  auth_source: 
  database: 
  collection: cexaccounts
```

### Exchange Mapping
```yaml
exchanges:
  name_mapping:
    Gate_io: gateio        # DB name → CCXT ID
    HTX: htx
    MEXC: mexc
    Crypto_com: cryptocom
```

### API Authentication
```yaml
api:
  auth_token: "your-secret-token"  # Bearer token for API access
```

## Database Schema

**Collection:** `cexaccounts`

**Document Structure:**
```json
{
  "accountId": "markhor-1-gate",
  "exchange": "Gate_io",           // Must match config.yml mapping
  "accountName": "MPMMS",
  "apiKey": "your-api-key",
  "apiSecret": "your-api-secret",
  "uid": "35264738",
  "isActive": true                  // Only active accounts are fetched
}
```

**Query:** `db.cexaccounts.find({isActive: true})`

## API Response Schema

```json
{
  "success": true,
  "accounts": [
    {
      "account_id": "markhor-1-gate",
      "account_name": "MPMMS",
      "exchange": "Gate_io",
      "balances": {
        "USDT": {
          "free": 1000.0,
          "used": 0.0,
          "total": 1000.0
        },
        "ALI": {
          "free": 50000.0,
          "used": 0.0,
          "total": 50000.0
        }
      },
      "error": null,
      "timestamp": "2025-01-19T12:00:00Z"
    }
  ],
  "total_accounts": 4,
  "successful_fetches": 4,
  "failed_fetches": 0,
  "timestamp": "2025-01-19T12:00:00Z"
}
```

## Common Operations

### Adding New Exchange

1. Add to MongoDB:
```json
{
  "accountId": "markhor-1-binance",
  "exchange": "Binance",
  "accountName": "Trading",
  "apiKey": "...",
  "apiSecret": "...",
  "isActive": true
}
```

2. Add mapping to `backend/config.yml`:
```yaml
exchanges:
  name_mapping:
    Binance: binance  # Add this line
```

3. Restart service (or hot-reload if implemented)

**No code changes needed!**

### Disabling Account

Update MongoDB:
```javascript
db.cexaccounts.updateOne(
  {accountId: "markhor-1-gate"},
  {$set: {isActive: false}}
)
```

Next API call will automatically exclude it.

### Changing Auth Token

1. Update `backend/config.yml`:
```yaml
api:
  auth_token: "new-secure-token"
```

2. Restart service:
```bash
docker-compose restart
```

3. Update Google Apps Script:
```javascript
const CONFIG = {
  AUTH_TOKEN: 'new-secure-token'
};
```

## Error Handling

### Per-Account Errors
If one exchange fails, others still return data:
```json
{
  "account_id": "markhor-1-mexc",
  "exchange": "MEXC",
  "balances": {},
  "error": "Authentication failed: Invalid API key",
  "timestamp": "..."
}
```

### Global Errors
- **401:** Invalid auth token
- **404:** No active accounts in database
- **500:** MongoDB connection failed or service error

## Testing Strategy

### Unit Tests (Not Implemented Yet)
```python
# test_exchange_service.py
def test_exchange_mapping():
    service = ExchangeService()
    assert service.exchange_map['Gate_io'] == 'gateio'

def test_balance_parsing():
    # Mock CCXT response and test parsing
    pass
```

### Integration Tests
```bash
# test_api.py (already implemented)
python test_api.py
```

### Manual Tests
```bash
# Health check
curl http://localhost:8080/health

# Balance fetch
curl -H "Authorization: Bearer TOKEN" http://localhost:8080/api/balances

# Swagger UI
open http://localhost:8080/docs
```

## Security Considerations

### Sensitive Data
- **API Keys:** Stored in MongoDB (not in code)
- **Auth Token:** In config.yml (not committed to git)
- **MongoDB Password:** In config.yml (not committed to git)

### Access Control
- API requires Bearer token authentication
- MongoDB credentials restricted to specific IP/user
- Docker container runs as non-root user

### Network Security
- Use HTTPS in production (nginx reverse proxy)
- Firewall rules to restrict port access
- Consider IP whitelisting for API access

## Docker Configuration

**Ports:**
- `8080` - FastAPI service

**Volumes:**
- `./backend/config.yml:/app/config.yml:ro` - Config (read-only)
- `./logs:/app/logs` - Logs (persistent)

**Networks:**
- `markhor-network` - Isolated bridge network

**Health Check:**
- Command: `curl -f http://localhost:8080/health`
- Interval: 30s
- Retries: 3

## Deployment Environments

### Local Development
- Port: 8080
- Reload: Enabled
- Logs: Console

### Production Server
- Port: 8080 (behind nginx)
- Reload: Disabled
- Logs: File + Docker logs
- Auto-restart: `unless-stopped`

## Dependencies

**Python:**
- `fastapi==0.109.0` - Web framework
- `uvicorn==0.27.0` - ASGI server
- `ccxt==4.2.25` - Exchange library
- `pymongo==4.6.1` - MongoDB client
- `pydantic==2.5.3` - Data validation
- `pyyaml==6.0.1` - Config parsing

**System:**
- Python 3.11+
- Docker 20.10+
- Docker Compose 2.0+

## Performance Characteristics

### Response Times
- Health check: <50ms
- Single exchange balance: 500-2000ms (depends on exchange API)
- All balances (4 exchanges): 1-3s (parallel fetching)

### Concurrency
- Multiple exchanges fetched in parallel using `asyncio.gather()`
- CCXT calls run in thread pool (CCXT is sync)
- Can handle multiple API requests concurrently

### Rate Limits
- CCXT handles rate limiting automatically (`enableRateLimit: true`)
- MongoDB connection pooled
- No artificial rate limiting on API endpoints

## Maintenance

### Regular Tasks
- Monitor logs for errors: `docker-compose logs -f`
- Check disk usage: `docker system df`
- Update dependencies: Check for security updates monthly
- Rotate auth token: Every 3-6 months

### Updates
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

### Backup
```bash
# Backup config
tar -czf backup_$(date +%Y%m%d).tar.gz backend/config.yml docker-compose.yml

# MongoDB backup (if managed separately)
mongodump --uri="mongodb://..." --out=/backup/
```

## Troubleshooting Guide

### Service Won't Start
1. Check logs: `docker-compose logs`
2. Verify MongoDB accessible: `mongosh "mongodb://..."`
3. Check port availability: `netstat -tulpn | grep 8080`
4. Verify config.yml syntax: `python -c "import yaml; yaml.safe_load(open('backend/config.yml'))"`

### Balance Fetch Fails
1. Check exchange API keys in MongoDB
2. Verify exchange name mapping in config.yml
3. Test CCXT directly: `python -c "import ccxt; print(ccxt.gateio().fetch_status())"`
4. Check exchange rate limits

### MongoDB Connection Issues
1. Verify connection string in config.yml
2. Check MongoDB server status
3. Verify credentials
4. Test from container: `docker exec -it markhor-cex-balance bash`

## Future Enhancements (Not Implemented)

- [ ] Caching layer (Redis) to reduce exchange API calls
- [ ] WebSocket support for real-time balance updates
- [ ] Historical balance tracking (store in DB)
- [ ] Prometheus metrics endpoint
- [ ] Retry logic with exponential backoff
- [ ] Hot-reload configuration without restart
- [ ] Multi-user support with different auth tokens
- [ ] Balance change notifications (Telegram/Slack)

## Contact & Support

**Project:** Markhor Market Making Infrastructure  
**Component:** CEX Balance Service  
**Maintained By:** Markhor Team  
**Created:** January 2025

---

**For AI Assistants:** This project values simplicity, configuration-driven design, and minimal code. When making changes, prioritize clarity over cleverness, and always check if a configuration change can solve the problem before modifying code.


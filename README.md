# Markhor CEX Balance Service

FastAPI service to fetch balances from Gate.io, HTX, MEXC, and Crypto.com. Reads credentials from MongoDB, returns JSON via REST API.


## API Endpoints

- `GET /health` - Health check
- `GET /api/balances` - Get all balances (requires auth)
- `GET /api/balances/summary` - Simplified summary (requires auth)
- `GET /docs` - Swagger UI documentation

## Google Apps Script Setup

See `google-apps-script/Code.gs` for the complete script. 

1. Copy code to your Google Sheet (Extensions → Apps Script)
2. Update CONFIG with your server URL and auth token
3. Run `testAPIConnection()` to test
4. Run `setupTrigger()` to schedule daily 7 PM updates

## Configuration

All settings in `backend/config.yml`:
- MongoDB connection (already configured)
- API auth token (change this!)
- Service port and logging

## Structure

```
backend/
  app/
    main.py              # FastAPI endpoints
    config.py            # YAML config loader
    database.py          # MongoDB client
    models.py            # Pydantic schemas
    services/
      exchange_service.py  # CCXT wrapper
  config.yml             # All configuration
  Dockerfile
docker-compose.yml
google-apps-script/
  Code.gs                # Google Sheet updater
```

## Local Testing

### Option 2: Python Virtual Environment
```bash
# Create venv
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Run service
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload


lsof -ti:8080 | xargs kill -9 && sleep 1 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
# Test in another terminal
python test_api.py
```

### Interactive API Testing
```bash
# Start service
docker-compose up -d

# Open Swagger UI in browser
open http://localhost:8080/docs

# Test endpoints interactively with built-in UI
```

## Server Deployment

### Prerequisites
- Linux server (Ubuntu 22.04+ recommended)
- Docker & Docker Compose installed
- Port 8080 accessible (or configure nginx reverse proxy)

### Deploy Steps

```bash
# 1. SSH to server
ssh user@your-server-ip

# 2. Clone/upload project
git clone your-repo
# or
scp -r Ledger-Update_Service user@server:/path/to/deploy/

# 3. Navigate to project
cd Ledger-Update_Service

# 4. Update configuration
nano backend/config.yml
# Change: api.auth_token to a secure token

docker-compose down

# 5. Start service
docker-compose up -d --build

# 6. Verify
curl http://localhost:8080/health

# 7. Check logs
docker-compose logs -f
```

### Configure Firewall
```bash
# Allow port 8080
sudo ufw allow 8080/tcp

# Or use nginx reverse proxy for HTTPS
sudo apt install nginx certbot python3-certbot-nginx
sudo nano /etc/nginx/sites-available/cex-balance
```

### Nginx Reverse Proxy (Optional)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Enable site and get SSL
sudo ln -s /etc/nginx/sites-available/cex-balance /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
sudo systemctl reload nginx
```

### Auto-restart on Reboot
```bash
# Service already configured with restart: unless-stopped in docker-compose.yml
# Docker will auto-start on system reboot
```

### Update Deployment
```bash
cd Ledger-Update_Service
git pull  # or upload new files
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

## Troubleshooting

```bash
# Check logs
docker-compose logs -f

# Rebuild from scratch
docker-compose build --no-cache && docker-compose up -d

# Test MongoDB connection
mongosh "mongodb://USERNAME:PASSWORD@HOST:PORT/DATABASE?authSource=AUTH_SOURCE"

# Run automated tests
python test_api.py

# Check container status
docker ps | grep markhor

# Restart service
docker-compose restart

# View resource usage
docker stats markhor-cex-balance
```


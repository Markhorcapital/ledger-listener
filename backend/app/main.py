"""FastAPI main application"""
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict
import logging

from app.config import config
from app.database import db
from app.models import AllBalancesResponse, DexBalancesResponse, HealthResponse
from app.services import DexBalanceService, ExchangeService, PriceService

# Configure logging - get level from config
log_level = config.get('service.log_level', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=config.get('api.title', 'CEX Balance Service'),
    version=config.get('api.version', '1.0.0'),
    description=config.get('api.description', 'Fetch balances from CEX accounts'),
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
AUTH_TOKEN = config.get('api.auth_token', 'your-secret-token-here')

# Initialize services
price_service = PriceService()
dex_balance_service = DexBalanceService(price_service)
exchange_service = ExchangeService()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """Verify authentication token"""
    if credentials.credentials != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return credentials.credentials


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    logger.info("Starting CEX Balance Service...")
    try:
        db.connect()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    logger.info("Shutting down CEX Balance Service...")
    db.disconnect()


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": config.get('api.title', 'CEX Balance Service'),
        "version": config.get('api.version', '1.0.0'),
        "status": "running",
        "endpoints": {
            "balances": "/api/balances",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    
    # Check database connection
    try:
        db.collection.find_one()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        database=db_status,
        timestamp=timestamp
    )


@app.get("/api/balances", response_model=AllBalancesResponse, tags=["Balances"])
async def get_all_balances(token: str = Depends(verify_token)):
    """
    Fetch balances from all active CEX accounts
    
    Returns:
        AllBalancesResponse with balance data for all accounts
    """
    try:
        # Fetch accounts from database
        accounts = db.get_active_accounts()
        
        if not accounts:
            raise HTTPException(
                status_code=404,
                detail="No active accounts found in database"
            )
        
        logger.info(f"Fetching balances for {len(accounts)} accounts...")
        
        # Fetch balances from all exchanges
        account_balances = await exchange_service.fetch_all_balances(accounts)

        # Fetch ALI price (optional, non-blocking failure)
        pricing_info = await price_service.get_ali_price()
        
        # Count successes and failures
        successful = sum(1 for ab in account_balances if ab.error is None)
        failed = sum(1 for ab in account_balances if ab.error is not None)
        
        logger.info(f"Completed: {successful} successful, {failed} failed")
        
        return AllBalancesResponse(
            success=True,
            accounts=account_balances,
            total_accounts=len(accounts),
            successful_fetches=successful,
            failed_fetches=failed,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            pricing=pricing_info,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching balances: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/balances/summary", tags=["Balances"])
async def get_balances_summary(token: str = Depends(verify_token)):
    """
    Get a simplified summary of balances (useful for quick overview)
    
    Returns:
        Simplified balance summary by exchange
    """
    try:
        # Fetch full balance data
        full_response = await get_all_balances(token)
        
        # Create summary grouped by exchange
        summary: Dict[str, Dict[str, Dict[str, float]]] = {}
        exchange_totals: Dict[str, Dict[str, float]] = {}
        overall_totals: Dict[str, float] = {}
        
        for account in full_response.accounts:
            exchange = account.exchange
            if exchange not in summary:
                summary[exchange] = {}
            if exchange not in exchange_totals:
                exchange_totals[exchange] = {}
            
            summary[exchange][account.account_name] = {}
            
            for currency, balance in account.balances.items():
                total_value = float(balance.total or 0.0)
                free_value = float(balance.free or 0.0)
                
                summary[exchange][account.account_name][currency] = {
                    "total": total_value,
                    "free": free_value
                }
                
                exchange_totals[exchange][currency] = exchange_totals[exchange].get(currency, 0.0) + total_value
                overall_totals[currency] = overall_totals.get(currency, 0.0) + total_value
        
        return {
            "success": True,
            "summary": summary,
            "totals": {
                "by_exchange": exchange_totals,
                "overall": overall_totals
            },
            "pricing": full_response.pricing,
            "timestamp": full_response.timestamp
        }
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dex/balances", response_model=DexBalancesResponse, tags=["Balances"])
async def get_dex_balances(token: str = Depends(verify_token)):
    """Fetch on-chain DEX balances (EVM + Solana) via Alchemy APIs."""
    try:
        data = await dex_balance_service.fetch_all_balances()
        return DexBalancesResponse(
            success=True,
            chains=data.get("chains", {}),
            prices=data.get("prices", {}),
            timestamp=data.get("timestamp"),
        )
    except Exception as exc:
        logger.error(f"Error fetching DEX balances: {exc}")
        raise HTTPException(status_code=500, detail="Failed to fetch DEX balances")

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=config.get('service.host', '0.0.0.0'),
        port=config.get('service.port', 8080),
        reload=False,
        workers=config.get('service.workers', 1),
        log_level=config.get('service.log_level', 'info')
    )


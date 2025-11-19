"""Exchange service for fetching balances using CCXT"""
import ccxt
import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, List
from app.config import config
from app.models import BalanceInfo, AccountBalance

logger = logging.getLogger(__name__)


class ExchangeService:
    """Service to fetch balances from multiple exchanges"""
    
    def __init__(self):
        self.timeout = config.get('exchanges.timeout', 30000)
        self.retry_attempts = config.get('exchanges.retry_attempts', 3)
        self.enable_rate_limit = config.get('exchanges.rate_limit', True)
        # Load exchange name mapping from config
        self.exchange_map = config.get('exchanges.name_mapping', {})
        # Create dedicated thread pool for parallel exchange API calls
        self.executor = ThreadPoolExecutor(max_workers=10)
    
    def _get_exchange_instance(self, account: Dict[str, Any]) -> ccxt.Exchange:
        """
        Create CCXT exchange instance with credentials
        
        Args:
            account: Account data from database
            
        Returns:
            Configured CCXT exchange instance
        """
        exchange_name = account.get('exchange')
        
        # Get CCXT exchange ID from config mapping, fallback to lowercase conversion
        ccxt_exchange_id = self.exchange_map.get(
            exchange_name, 
            exchange_name.lower().replace('_', '')
        )
        
        # Get exchange class
        if not hasattr(ccxt, ccxt_exchange_id):
            raise ValueError(
                f"Exchange '{exchange_name}' (CCXT ID: '{ccxt_exchange_id}') not supported. "
                f"Add mapping to config.yml: exchanges.name_mapping.{exchange_name}"
            )
        
        exchange_class = getattr(ccxt, ccxt_exchange_id)
        
        # Initialize with credentials
        exchange_config = {
            'apiKey': account.get('apiKey'),
            'secret': account.get('apiSecret'),
            'timeout': self.timeout,
            'enableRateLimit': self.enable_rate_limit,
            'options': {
                'adjustForTimeDifference': True,  # Auto-sync time
                'recvWindow': 5000,  # Faster window for some exchanges
            }
        }
        
        # For HTX (Huobi), explicitly configure for spot trading only
        if ccxt_exchange_id in ['htx', 'huobi']:
            exchange_config['options'] = {
                'defaultType': 'spot',
                'fetchMarkets': ['spot'],  # Only load spot markets, ignore derivatives
            }
        
        exchange = exchange_class(exchange_config)
        
        # CRITICAL: Skip loading markets entirely for speed
        # We only need balance fetching, not trading
        exchange.load_markets = lambda: {}  # No-op function
        exchange.markets = {}
        exchange.markets_by_id = {}
        
        # For HTX/Huobi, override market loading to prevent futures API calls
        if ccxt_exchange_id in ['htx', 'huobi']:
            exchange.options['defaultType'] = 'spot'
            exchange.options['fetchMarkets'] = ['spot']  # Block derivatives market loading
        
        return exchange
    
    async def fetch_balance_with_retry(self, account: Dict[str, Any]) -> AccountBalance:
        """
        Fetch balance with smart retry logic
        - Timeout errors: NO retry (exchange is slow, move on)
        - Other errors: Retry up to configured attempts
        
        Args:
            account: Account data from database
            
        Returns:
            AccountBalance with fetched data or error after retries
        """
        account_id = account.get('accountId', 'unknown')
        account_name = account.get('accountName', 'unknown')
        exchange_name = account.get('exchange', 'unknown')
        
        max_retries = self.retry_attempts
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = await self.fetch_balance_async(account)
                
                # If successful (no error), return immediately
                if result.error is None:
                    return result
                
                # Check if it's a timeout error - don't retry these
                last_error = result.error
                if 'timeout' in last_error.lower() or 'timed out' in last_error.lower():
                    break  # Don't retry timeouts, fail fast
                
                # Retry other errors with minimal delay
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1)  # Minimal wait before retry
                    
            except Exception as e:
                last_error = str(e)
                # Don't retry on timeout exceptions
                if 'timeout' in str(e).lower():
                    break
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1)
        
        # After retries failed, return with zero balances and error
        timestamp = datetime.utcnow().isoformat() + 'Z'
        return AccountBalance(
            account_id=account_id,
            account_name=account_name,
            exchange=exchange_name,
            balances={
                "USDT": BalanceInfo(free=0.0, used=0.0, total=0.0),
                "ALI": BalanceInfo(free=0.0, used=0.0, total=0.0)
            },
            error=f"Failed after {attempt + 1} attempts: {last_error}",
            timestamp=timestamp
        )
    
    async def fetch_balance_async(self, account: Dict[str, Any]) -> AccountBalance:
        """
        Fetch balance for a single account asynchronously (single attempt)
        
        Args:
            account: Account data from database
            
        Returns:
            AccountBalance with fetched data or error
        """
        account_id = account.get('accountId', 'unknown')
        account_name = account.get('accountName', 'unknown')
        exchange_name = account.get('exchange', 'unknown')
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        start_time = time.time()
        logger.info(f"[{exchange_name}] Starting balance fetch for {account_name}")
        
        try:
            # Create exchange instance
            exchange = self._get_exchange_instance(account)
            
            # Fetch balance in dedicated thread pool (CCXT is synchronous)
            # Using dedicated executor for true parallelism
            loop = asyncio.get_event_loop()
            
            # For HTX/Huobi, explicitly pass type parameter
            if exchange.id in ['htx', 'huobi']:
                balance_data = await loop.run_in_executor(
                    self.executor,  # Use dedicated thread pool
                    lambda: exchange.fetch_balance({'type': 'spot'})
                )
            else:
                balance_data = await loop.run_in_executor(
                    self.executor,  # Use dedicated thread pool
                    exchange.fetch_balance
                )
            
            # Parse balance data
            balances = {}
            for currency, balance_info in balance_data.get('total', {}).items():
                if balance_info > 0:  # Only include non-zero balances
                    free = balance_data.get('free', {}).get(currency, 0)
                    used = balance_data.get('used', {}).get(currency, 0)
                    total = balance_data.get('total', {}).get(currency, 0)
                    
                    balances[currency] = BalanceInfo(
                        free=float(free),
                        used=float(used),
                        total=float(total)
                    )
            
            elapsed = time.time() - start_time
            logger.info(f"[{exchange_name}] ✅ Success in {elapsed:.2f}s - {len(balances)} currencies")
            
            return AccountBalance(
                account_id=account_id,
                account_name=account_name,
                exchange=exchange_name,
                balances=balances,
                timestamp=timestamp
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{exchange_name}] ❌ Failed in {elapsed:.2f}s - {str(e)[:100]}")
            
            # Return error info
            return AccountBalance(
                account_id=account_id,
                account_name=account_name,
                exchange=exchange_name,
                balances={},
                error=str(e),
                timestamp=timestamp
            )
    
    async def fetch_all_balances(self, accounts: List[Dict[str, Any]]) -> List[AccountBalance]:
        """
        Fetch balances for all accounts in parallel with retry logic
        
        Args:
            accounts: List of account data from database
            
        Returns:
            List of AccountBalance objects
        """
        # Create tasks for parallel execution with retry
        tasks = [
            self.fetch_balance_with_retry(account)
            for account in accounts
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return results
        account_balances = []
        for result in results:
            if isinstance(result, AccountBalance):
                account_balances.append(result)
            elif isinstance(result, Exception):
                # Log exception but continue
                print(f"Error fetching balance: {result}")
        
        return account_balances


# Global service instance
exchange_service = ExchangeService()


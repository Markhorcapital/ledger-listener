"""Data models for API requests and responses"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, List


class BalanceInfo(BaseModel):
    """Balance information for a single asset"""
    free: float = Field(..., description="Available balance")
    used: float = Field(..., description="Balance in use (locked)")
    total: float = Field(..., description="Total balance (free + used)")


class AccountBalance(BaseModel):
    """Balance for a single exchange account"""
    account_id: str = Field(..., description="Account identifier")
    account_name: str = Field(..., description="Account name")
    exchange: str = Field(..., description="Exchange name")
    balances: Dict[str, BalanceInfo] = Field(..., description="Asset balances")
    error: Optional[str] = Field(None, description="Error message if fetch failed")
    timestamp: str = Field(..., description="Fetch timestamp")


class PricingInfo(BaseModel):
    """Token pricing information (USD)."""
    asset: str = Field(..., description="Asset symbol (e.g., ALI)")
    price_usd: float = Field(..., description="Spot price in USD")
    source: str = Field(..., description="Pricing data source")
    timestamp: str = Field(..., description="Price fetch timestamp")


class AllBalancesResponse(BaseModel):
    """Response containing all account balances"""
    success: bool = Field(..., description="Whether the request was successful")
    accounts: List[AccountBalance] = Field(..., description="List of account balances")
    total_accounts: int = Field(..., description="Total number of accounts")
    successful_fetches: int = Field(..., description="Number of successful fetches")
    failed_fetches: int = Field(..., description="Number of failed fetches")
    timestamp: str = Field(..., description="Response timestamp")
    pricing: Optional[PricingInfo] = Field(
        None, description="Optional pricing information for assets"
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database connection status")
    timestamp: str = Field(..., description="Check timestamp")


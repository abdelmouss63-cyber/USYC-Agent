"""
USYC Protocol Labs - Configuration Settings
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # Network
    arc_rpc_url: str = os.getenv("ARC_RPC_URL", "https://rpc.arc-testnet.circle.com")
    private_key: Optional[str] = os.getenv("PRIVATE_KEY")

    # Contracts
    vault_contract: str = os.getenv("VAULT_CONTRACT", "0x2f685b5Ef138Ac54F4CB1155A9C5922c5A58eD25")
    usdc_contract: Optional[str] = os.getenv("USDC_CONTRACT")

    # Circle Gateway API
    circle_api_key: Optional[str] = os.getenv("CIRCLE_API_KEY")
    circle_wallet_id: Optional[str] = os.getenv("CIRCLE_WALLET_ID")

    # Agent Guardrails
    max_deposit_amount: float = float(os.getenv("MAX_DEPOSIT_AMOUNT", "10000"))
    max_withdraw_amount: float = float(os.getenv("MAX_WITHDRAW_AMOUNT", "10000"))
    cooldown_seconds: int = int(os.getenv("COOLDOWN_SECONDS", "60"))

    # x402 Autonomous Payment Limits
    max_auto_payment: float = float(os.getenv("MAX_AUTO_PAYMENT", "10.0"))

    # API (Railway uses PORT env var)
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))

    # Branding Colors
    brand_navy: str = "#1E3A5F"
    brand_blue: str = "#3498DB"
    brand_green: str = "#2ECC71"

    # USDC Decimals
    usdc_decimals: int = 6

    @property
    def is_configured(self) -> bool:
        """Check if essential configuration is present."""
        return self.private_key is not None and self.usdc_contract is not None

    @property
    def is_gateway_configured(self) -> bool:
        """Check if Circle Gateway is configured."""
        return self.circle_api_key is not None


settings = Settings()

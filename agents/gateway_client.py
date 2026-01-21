"""
USYC Protocol Labs - Circle Gateway Client
Handles USDC payments via Circle's Gateway API.
"""
import asyncio
import aiohttp
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
import os


class PaymentStatus(Enum):
    """Payment status values from Circle Gateway."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETE = "complete"
    FAILED = "failed"
    EXPIRED = "expired"


class TransferStatus(Enum):
    """Transfer status values from Circle Gateway."""
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PaymentIntent:
    """Represents a Circle payment intent."""
    id: str
    amount: str
    currency: str
    status: PaymentStatus
    merchant_wallet_id: Optional[str] = None
    settlement_currency: Optional[str] = None
    payment_methods: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "PaymentIntent":
        """Create PaymentIntent from API response."""
        return cls(
            id=data.get("id", ""),
            amount=data.get("amount", {}).get("amount", "0"),
            currency=data.get("amount", {}).get("currency", "USD"),
            status=PaymentStatus(data.get("status", "pending")),
            merchant_wallet_id=data.get("merchantWalletId"),
            settlement_currency=data.get("settlementCurrency"),
            payment_methods=data.get("paymentMethods"),
            created_at=data.get("createDate"),
            expires_at=data.get("expiresOn"),
            metadata=data.get("metadata"),
        )


@dataclass
class Transfer:
    """Represents a Circle transfer."""
    id: str
    source_wallet_id: str
    destination_address: str
    amount: str
    currency: str
    status: TransferStatus
    chain: str = "ARB-SEPOLIA"  # Arc uses Arbitrum under the hood
    tx_hash: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Transfer":
        """Create Transfer from API response."""
        return cls(
            id=data.get("id", ""),
            source_wallet_id=data.get("source", {}).get("id", ""),
            destination_address=data.get("destination", {}).get("address", ""),
            amount=data.get("amount", {}).get("amount", "0"),
            currency=data.get("amount", {}).get("currency", "USDC"),
            status=TransferStatus(data.get("status", "pending")),
            chain=data.get("destination", {}).get("chain", "ARB-SEPOLIA"),
            tx_hash=data.get("transactionHash"),
            created_at=data.get("createDate"),
        )


class CircleGatewayClient:
    """
    Client for Circle Gateway API.
    Handles payment intents, transfers, and wallet operations.
    """

    BASE_URL = "https://api.circle.com/v1"

    def __init__(self, api_key: Optional[str] = None, demo_mode: bool = False):
        """
        Initialize the Circle Gateway client.

        Args:
            api_key: Circle API key (from env if not provided)
            demo_mode: If True, simulate API calls
        """
        self.api_key = api_key or os.getenv("CIRCLE_API_KEY")
        self.demo_mode = demo_mode
        self._session: Optional[aiohttp.ClientSession] = None

        # Demo mode state
        self._demo_wallet_balance: float = 10000.0  # 10,000 USDC
        self._demo_transfers: List[Transfer] = []
        self._demo_payments: List[PaymentIntent] = []

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request to Circle Gateway.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body

        Returns:
            API response data
        """
        if self.demo_mode:
            return await self._demo_request(method, endpoint, data)

        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        async with session.request(method, url, json=data) as response:
            result = await response.json()

            if response.status >= 400:
                error_msg = result.get("message", "Unknown error")
                raise CircleGatewayError(
                    f"API Error ({response.status}): {error_msg}",
                    status_code=response.status,
                    response=result
                )

            return result.get("data", result)

    async def _demo_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Simulate API request in demo mode."""
        await asyncio.sleep(0.3)  # Simulate network latency

        if endpoint == "/payments" and method == "POST":
            return self._demo_create_payment(data)
        elif endpoint.startswith("/payments/") and method == "GET":
            payment_id = endpoint.split("/")[-1]
            return self._demo_get_payment(payment_id)
        elif endpoint == "/transfers" and method == "POST":
            return self._demo_create_transfer(data)
        elif endpoint.startswith("/transfers/") and method == "GET":
            transfer_id = endpoint.split("/")[-1]
            return self._demo_get_transfer(transfer_id)
        elif endpoint == "/wallets" and method == "GET":
            return self._demo_get_wallets()

        return {}

    def _demo_create_payment(self, data: Dict) -> Dict:
        """Demo: Create a payment intent."""
        payment_id = f"demo-pay-{uuid4().hex[:12]}"
        payment = {
            "id": payment_id,
            "amount": data.get("amount", {}),
            "status": "pending",
            "merchantWalletId": data.get("merchantWalletId", "demo-wallet"),
            "settlementCurrency": "USDC",
            "paymentMethods": [{"type": "blockchain", "chain": "ARC"}],
            "createDate": datetime.utcnow().isoformat(),
            "metadata": data.get("metadata", {}),
        }
        self._demo_payments.append(PaymentIntent.from_api_response(payment))
        return payment

    def _demo_get_payment(self, payment_id: str) -> Dict:
        """Demo: Get payment status."""
        for payment in self._demo_payments:
            if payment.id == payment_id:
                return {
                    "id": payment.id,
                    "amount": {"amount": payment.amount, "currency": payment.currency},
                    "status": "complete",  # Auto-complete in demo
                }
        return {"id": payment_id, "status": "complete"}

    def _demo_create_transfer(self, data: Dict) -> Dict:
        """Demo: Create a transfer."""
        transfer_id = f"demo-txn-{uuid4().hex[:12]}"
        amount = float(data.get("amount", {}).get("amount", 0))

        if amount > self._demo_wallet_balance:
            raise CircleGatewayError("Insufficient balance", status_code=400)

        self._demo_wallet_balance -= amount

        transfer = {
            "id": transfer_id,
            "source": {"type": "wallet", "id": data.get("source", {}).get("id", "demo-wallet")},
            "destination": {
                "type": "blockchain",
                "address": data.get("destination", {}).get("address", ""),
                "chain": data.get("destination", {}).get("chain", "ARC"),
            },
            "amount": data.get("amount", {}),
            "status": "pending",
            "transactionHash": f"0x{uuid4().hex}",
            "createDate": datetime.utcnow().isoformat(),
        }
        self._demo_transfers.append(Transfer.from_api_response(transfer))
        return transfer

    def _demo_get_transfer(self, transfer_id: str) -> Dict:
        """Demo: Get transfer status."""
        for transfer in self._demo_transfers:
            if transfer.id == transfer_id:
                return {
                    "id": transfer.id,
                    "status": "complete",  # Auto-complete in demo
                    "transactionHash": transfer.tx_hash,
                }
        return {"id": transfer_id, "status": "complete"}

    def _demo_get_wallets(self) -> List[Dict]:
        """Demo: Get wallets."""
        return [{
            "walletId": "demo-wallet-001",
            "entityId": "demo-entity",
            "type": "end_user_wallet",
            "balances": [
                {"amount": str(self._demo_wallet_balance), "currency": "USDC"}
            ],
        }]

    # --- Public API Methods ---

    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "USD",
        merchant_wallet_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> PaymentIntent:
        """
        Create a payment intent for receiving payments.

        Args:
            amount: Payment amount
            currency: Currency code (default: USD)
            merchant_wallet_id: Wallet to receive funds
            metadata: Additional metadata

        Returns:
            Created PaymentIntent
        """
        idempotency_key = str(uuid4())

        payload = {
            "idempotencyKey": idempotency_key,
            "amount": {
                "amount": f"{amount:.2f}",
                "currency": currency,
            },
            "settlementCurrency": "USDC",
            "paymentMethods": [{"type": "blockchain", "chain": "ARC"}],
        }

        if merchant_wallet_id:
            payload["merchantWalletId"] = merchant_wallet_id
        if metadata:
            payload["metadata"] = metadata

        result = await self._request("POST", "/payments", payload)
        return PaymentIntent.from_api_response(result)

    async def get_payment_status(self, payment_id: str) -> PaymentIntent:
        """
        Get the status of a payment intent.

        Args:
            payment_id: Payment intent ID

        Returns:
            PaymentIntent with current status
        """
        result = await self._request("GET", f"/payments/{payment_id}")
        return PaymentIntent.from_api_response(result)

    async def transfer_usdc(
        self,
        destination_address: str,
        amount: float,
        source_wallet_id: str,
        chain: str = "ARC",
        metadata: Optional[Dict] = None,
    ) -> Transfer:
        """
        Transfer USDC to an address.

        Args:
            destination_address: Recipient blockchain address
            amount: Amount of USDC to transfer
            source_wallet_id: Source wallet ID
            chain: Blockchain network (default: ARC)
            metadata: Additional metadata

        Returns:
            Created Transfer
        """
        idempotency_key = str(uuid4())

        payload = {
            "idempotencyKey": idempotency_key,
            "source": {
                "type": "wallet",
                "id": source_wallet_id,
            },
            "destination": {
                "type": "blockchain",
                "address": destination_address,
                "chain": chain,
            },
            "amount": {
                "amount": f"{amount:.6f}",
                "currency": "USDC",
            },
        }

        if metadata:
            payload["metadata"] = metadata

        result = await self._request("POST", "/transfers", payload)
        return Transfer.from_api_response(result)

    async def get_transfer_status(self, transfer_id: str) -> Transfer:
        """
        Get the status of a transfer.

        Args:
            transfer_id: Transfer ID

        Returns:
            Transfer with current status
        """
        result = await self._request("GET", f"/transfers/{transfer_id}")
        return Transfer.from_api_response(result)

    async def wait_for_transfer_completion(
        self,
        transfer_id: str,
        timeout: float = 60.0,
        poll_interval: float = 2.0,
    ) -> Transfer:
        """
        Wait for a transfer to complete.

        Args:
            transfer_id: Transfer ID
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks

        Returns:
            Completed Transfer

        Raises:
            TimeoutError: If transfer doesn't complete in time
            CircleGatewayError: If transfer fails
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            transfer = await self.get_transfer_status(transfer_id)

            if transfer.status == TransferStatus.COMPLETE:
                return transfer
            elif transfer.status == TransferStatus.FAILED:
                raise CircleGatewayError(f"Transfer {transfer_id} failed")

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"Transfer {transfer_id} did not complete within {timeout}s")

            await asyncio.sleep(poll_interval)

    async def get_wallets(self) -> List[Dict[str, Any]]:
        """
        Get list of wallets.

        Returns:
            List of wallet data
        """
        result = await self._request("GET", "/wallets")
        return result if isinstance(result, list) else [result]

    async def get_wallet_balance(self, wallet_id: str) -> Dict[str, float]:
        """
        Get wallet balance.

        Args:
            wallet_id: Wallet ID

        Returns:
            Dictionary of currency -> balance
        """
        if self.demo_mode:
            return {"USDC": self._demo_wallet_balance}

        result = await self._request("GET", f"/wallets/{wallet_id}")
        balances = {}
        for balance in result.get("balances", []):
            currency = balance.get("currency", "USDC")
            amount = float(balance.get("amount", 0))
            balances[currency] = amount
        return balances


class CircleGatewayError(Exception):
    """Exception for Circle Gateway API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

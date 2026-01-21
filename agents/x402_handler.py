"""
USYC Protocol Labs - x402 Protocol Handler
Autonomous payment handler for HTTP 402 Payment Required responses.

The x402 protocol enables AI agents to autonomously pay for services using USDC.
When an agent encounters a 402 response, it automatically:
1. Parses the payment requirements from response headers
2. Executes payment via Circle Gateway
3. Retries the original request with payment proof
"""
import asyncio
import aiohttp
import json
import base64
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .gateway_client import CircleGatewayClient, Transfer, CircleGatewayError
from .event_bus import Event, EventType, event_bus


class PaymentScheme(Enum):
    """Supported payment schemes for x402."""
    USDC = "usdc"
    EXACT = "exact"  # Exact amount required


@dataclass
class PaymentRequirement:
    """Parsed payment requirement from 402 response."""
    amount: float
    currency: str
    recipient_address: str
    network: str
    payment_id: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[datetime] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    scheme: PaymentScheme = PaymentScheme.USDC

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "PaymentRequirement":
        """
        Parse payment requirements from HTTP headers.

        Expected headers (x402 protocol):
        - X-Payment-Required: true
        - X-Payment-Amount: 0.10
        - X-Payment-Currency: USDC
        - X-Payment-Address: 0x...
        - X-Payment-Network: ARC (or ETH, ARB, etc.)
        - X-Payment-Id: unique-id (optional)
        - X-Payment-Description: Service description (optional)
        """
        amount = float(headers.get("X-Payment-Amount", "0"))
        currency = headers.get("X-Payment-Currency", "USDC")
        address = headers.get("X-Payment-Address", "")
        network = headers.get("X-Payment-Network", "ARC")
        payment_id = headers.get("X-Payment-Id")
        description = headers.get("X-Payment-Description")

        # Parse optional fields
        min_amount = headers.get("X-Payment-Min-Amount")
        max_amount = headers.get("X-Payment-Max-Amount")

        return cls(
            amount=amount,
            currency=currency,
            recipient_address=address,
            network=network,
            payment_id=payment_id,
            description=description,
            min_amount=float(min_amount) if min_amount else None,
            max_amount=float(max_amount) if max_amount else None,
        )

    @classmethod
    def from_json_body(cls, body: Dict[str, Any]) -> "PaymentRequirement":
        """
        Parse payment requirements from JSON response body.

        Expected structure:
        {
            "payment_required": true,
            "amount": 0.10,
            "currency": "USDC",
            "recipient": "0x...",
            "network": "ARC",
            "payment_id": "...",
            "description": "..."
        }
        """
        return cls(
            amount=float(body.get("amount", 0)),
            currency=body.get("currency", "USDC"),
            recipient_address=body.get("recipient", body.get("address", "")),
            network=body.get("network", "ARC"),
            payment_id=body.get("payment_id"),
            description=body.get("description"),
            min_amount=body.get("min_amount"),
            max_amount=body.get("max_amount"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "amount": self.amount,
            "currency": self.currency,
            "recipient_address": self.recipient_address,
            "network": self.network,
            "payment_id": self.payment_id,
            "description": self.description,
        }


@dataclass
class PaymentProof:
    """Proof of payment to include in retry request."""
    transfer_id: str
    tx_hash: str
    amount: float
    currency: str
    payer_address: str
    timestamp: datetime

    def to_header(self) -> str:
        """Encode payment proof for HTTP header."""
        data = {
            "transfer_id": self.transfer_id,
            "tx_hash": self.tx_hash,
            "amount": str(self.amount),
            "currency": self.currency,
            "payer": self.payer_address,
            "timestamp": self.timestamp.isoformat(),
        }
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode()).decode()

    @classmethod
    def from_header(cls, header_value: str) -> "PaymentProof":
        """Decode payment proof from HTTP header."""
        json_str = base64.b64decode(header_value).decode()
        data = json.loads(json_str)
        return cls(
            transfer_id=data["transfer_id"],
            tx_hash=data["tx_hash"],
            amount=float(data["amount"]),
            currency=data["currency"],
            payer_address=data["payer"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class X402Handler:
    """
    Autonomous payment handler for x402 protocol.

    Enables AI agents to automatically pay for services when encountering
    HTTP 402 Payment Required responses.
    """

    def __init__(
        self,
        gateway_client: CircleGatewayClient,
        source_wallet_id: str,
        payer_address: str,
        max_auto_payment: float = 10.0,  # Maximum auto-payment amount
        demo_mode: bool = False,
    ):
        """
        Initialize the x402 handler.

        Args:
            gateway_client: Circle Gateway client instance
            source_wallet_id: Wallet ID to pay from
            payer_address: Blockchain address of payer
            max_auto_payment: Maximum amount to pay automatically
            demo_mode: If True, simulate payments
        """
        self.gateway = gateway_client
        self.source_wallet_id = source_wallet_id
        self.payer_address = payer_address
        self.max_auto_payment = max_auto_payment
        self.demo_mode = demo_mode
        self._payment_history: List[Dict[str, Any]] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        await self.gateway.close()

    def _is_402_response(self, status: int, headers: Dict[str, str]) -> bool:
        """Check if response requires payment."""
        if status == 402:
            return True
        # Also check for x402 header
        return headers.get("X-Payment-Required", "").lower() == "true"

    def _parse_payment_requirement(
        self,
        status: int,
        headers: Dict[str, str],
        body: Optional[Dict] = None,
    ) -> Optional[PaymentRequirement]:
        """Parse payment requirements from response."""
        if not self._is_402_response(status, headers):
            return None

        # Try headers first (standard x402)
        if headers.get("X-Payment-Amount"):
            return PaymentRequirement.from_headers(headers)

        # Fall back to JSON body
        if body and body.get("payment_required"):
            return PaymentRequirement.from_json_body(body)

        return None

    async def _execute_payment(
        self,
        requirement: PaymentRequirement,
    ) -> Tuple[Transfer, PaymentProof]:
        """
        Execute payment via Circle Gateway.

        Args:
            requirement: Payment requirement to fulfill

        Returns:
            Tuple of (Transfer, PaymentProof)
        """
        # Guardrail: Check against max auto-payment
        if requirement.amount > self.max_auto_payment:
            raise X402PaymentError(
                f"Payment amount ${requirement.amount} exceeds max auto-payment ${self.max_auto_payment}"
            )

        # Emit payment initiated event
        await event_bus.publish(Event(
            event_type=EventType.DEPOSIT_INITIATED,  # Reusing for payment
            data={
                "type": "x402_payment",
                "amount": requirement.amount,
                "recipient": requirement.recipient_address,
                "description": requirement.description,
            },
            source_agent="X402Handler",
        ))

        # Execute transfer
        transfer = await self.gateway.transfer_usdc(
            destination_address=requirement.recipient_address,
            amount=requirement.amount,
            source_wallet_id=self.source_wallet_id,
            chain=requirement.network,
            metadata={
                "payment_id": requirement.payment_id,
                "type": "x402_autonomous_payment",
            }
        )

        # Wait for completion
        completed_transfer = await self.gateway.wait_for_transfer_completion(
            transfer.id,
            timeout=30.0,
        )

        # Create payment proof
        proof = PaymentProof(
            transfer_id=completed_transfer.id,
            tx_hash=completed_transfer.tx_hash or f"0x{transfer.id}",
            amount=requirement.amount,
            currency=requirement.currency,
            payer_address=self.payer_address,
            timestamp=datetime.utcnow(),
        )

        # Record payment
        self._payment_history.append({
            "requirement": requirement.to_dict(),
            "transfer_id": transfer.id,
            "tx_hash": proof.tx_hash,
            "timestamp": proof.timestamp.isoformat(),
        })

        # Emit payment completed event
        await event_bus.publish(Event(
            event_type=EventType.DEPOSIT_COMPLETED,
            data={
                "type": "x402_payment",
                "amount": requirement.amount,
                "recipient": requirement.recipient_address,
                "transfer_id": transfer.id,
                "tx_hash": proof.tx_hash,
            },
            source_agent="X402Handler",
        ))

        return completed_transfer, proof

    async def fetch_with_payment(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict] = None,
        auto_pay: bool = True,
    ) -> Tuple[int, Dict[str, str], Any]:
        """
        Fetch URL with automatic x402 payment handling.

        If the request returns 402, automatically pays and retries.

        Args:
            url: URL to fetch
            method: HTTP method
            headers: Request headers
            json_data: JSON body for POST/PUT
            auto_pay: Whether to automatically pay (default: True)

        Returns:
            Tuple of (status_code, response_headers, response_body)
        """
        session = await self._get_session()
        request_headers = headers.copy() if headers else {}

        # First request
        async with session.request(
            method,
            url,
            headers=request_headers,
            json=json_data,
        ) as response:
            response_headers = dict(response.headers)
            status = response.status

            # Try to get body
            try:
                body = await response.json()
            except:
                body = await response.text()

        # Check for 402
        if not self._is_402_response(status, response_headers):
            return status, response_headers, body

        if not auto_pay:
            return status, response_headers, body

        # Parse payment requirement
        body_dict = body if isinstance(body, dict) else None
        requirement = self._parse_payment_requirement(status, response_headers, body_dict)

        if not requirement:
            raise X402PaymentError("Received 402 but could not parse payment requirements")

        print(f"[X402] Payment required: ${requirement.amount} {requirement.currency} to {requirement.recipient_address[:10]}...")

        # Execute payment
        transfer, proof = await self._execute_payment(requirement)

        print(f"[X402] Payment completed: {proof.tx_hash}")

        # Retry with payment proof
        request_headers["X-Payment-Proof"] = proof.to_header()
        request_headers["X-Payment-TxHash"] = proof.tx_hash

        async with session.request(
            method,
            url,
            headers=request_headers,
            json=json_data,
        ) as response:
            response_headers = dict(response.headers)
            status = response.status

            try:
                body = await response.json()
            except:
                body = await response.text()

        return status, response_headers, body

    async def pay_and_access(
        self,
        url: str,
        method: str = "GET",
        **kwargs,
    ) -> Any:
        """
        Convenience method to access a paid resource.

        Args:
            url: URL to access
            method: HTTP method
            **kwargs: Additional arguments for fetch_with_payment

        Returns:
            Response body if successful

        Raises:
            X402PaymentError: If payment or access fails
        """
        status, headers, body = await self.fetch_with_payment(url, method, **kwargs)

        if status == 402:
            raise X402PaymentError("Payment was made but access still denied")
        elif status >= 400:
            raise X402PaymentError(f"Request failed with status {status}: {body}")

        return body

    def get_payment_history(self) -> List[Dict[str, Any]]:
        """Get history of autonomous payments made."""
        return self._payment_history.copy()

    def get_total_spent(self) -> float:
        """Get total amount spent on autonomous payments."""
        return sum(p["requirement"]["amount"] for p in self._payment_history)


class X402PaymentError(Exception):
    """Exception for x402 payment errors."""
    pass


# --- Utility Functions ---

def create_402_response_headers(
    amount: float,
    recipient_address: str,
    currency: str = "USDC",
    network: str = "ARC",
    payment_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, str]:
    """
    Create x402 response headers for a paywalled endpoint.

    Args:
        amount: Required payment amount
        recipient_address: Address to receive payment
        currency: Payment currency
        network: Blockchain network
        payment_id: Unique payment ID
        description: Description of what's being paid for

    Returns:
        Headers dict for 402 response
    """
    headers = {
        "X-Payment-Required": "true",
        "X-Payment-Amount": f"{amount:.6f}",
        "X-Payment-Currency": currency,
        "X-Payment-Address": recipient_address,
        "X-Payment-Network": network,
    }

    if payment_id:
        headers["X-Payment-Id"] = payment_id
    if description:
        headers["X-Payment-Description"] = description

    return headers


def verify_payment_proof(
    proof_header: str,
    expected_amount: float,
    expected_recipient: str,
) -> Tuple[bool, Optional[PaymentProof]]:
    """
    Verify a payment proof from request headers.

    Args:
        proof_header: X-Payment-Proof header value
        expected_amount: Expected payment amount
        expected_recipient: Expected recipient address

    Returns:
        Tuple of (is_valid, parsed_proof)
    """
    try:
        proof = PaymentProof.from_header(proof_header)

        # Verify amount (allow small variance for fees)
        if proof.amount < expected_amount * 0.99:
            return False, proof

        return True, proof

    except Exception:
        return False, None

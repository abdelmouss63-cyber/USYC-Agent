# USYC Protocol Labs

**Autonomous DeFi Yield Agent System with x402 Payment Protocol**

A multi-agent system for managing yield vault operations on Circle's Arc blockchain with autonomous payment capabilities. Built for the "Agentic Commerce on Arc" hackathon.

## Features

- **Vault Agent**: Autonomous deposit, withdraw, and auto-compound operations
- **Media Agent**: Automatic PDF receipt generation with QR codes
- **Circle Gateway Integration**: USDC transfers via Circle's payment infrastructure
- **x402 Protocol**: Autonomous AI agent payments for paywalled services
- **Event Bus**: Pub/sub architecture for inter-agent communication
- **REST API**: Full-featured FastAPI server with Swagger docs
- **CLI Interface**: Interactive command-line tool
- **Guardrails**: Built-in safety limits (amount caps, cooldowns)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Event Bus (Pub/Sub)                            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│     Vault Agent     │  │    Media Agent      │  │   x402 Handler      │
│  ─────────────────  │  │  ─────────────────  │  │  ─────────────────  │
│  • Deposit          │  │  • PDF Receipt      │  │  • Detect 402       │
│  • Withdraw         │  │  • QR Codes         │  │  • Auto-pay USDC    │
│  • Compound         │  │  • Branding         │  │  • Retry requests   │
│  • Gateway Transfer │  │                     │  │  • Payment proofs   │
└─────────┬───────────┘  └─────────────────────┘  └──────────┬──────────┘
          │                                                   │
          ▼                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Circle Gateway API                                   │
│                    (Payment Intents, Transfers, Wallets)                    │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   YieldVaultV2Upgradeable (Arc Testnet)                     │
│                   0x2f685b5Ef138Ac54F4CB1155A9C5922c5A58eD25                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## x402 Protocol - Autonomous Agent Payments

The x402 protocol enables AI agents to autonomously pay for services using USDC. When an agent encounters an HTTP 402 Payment Required response, it automatically:

1. **Detects** the 402 response and parses payment requirements
2. **Validates** the amount against configured guardrails
3. **Pays** via Circle Gateway
4. **Retries** the original request with payment proof

### How It Works

```
Agent                          Paywalled Service               Circle Gateway
  │                                   │                              │
  │──── GET /premium-data ───────────▶│                              │
  │                                   │                              │
  │◀─── 402 Payment Required ─────────│                              │
  │     (0.10 USDC to 0x742...)       │                              │
  │                                   │                              │
  │─────────────────────── Transfer 0.10 USDC ──────────────────────▶│
  │                                   │                              │
  │◀────────────────────── Transfer Complete ───────────────────────│
  │                                   │                              │
  │──── GET /premium-data ───────────▶│                              │
  │     (+ X-Payment-Proof header)    │                              │
  │                                   │                              │
  │◀─── 200 OK (Premium Content) ─────│                              │
```

## Quick Start

### Prerequisites

- Python 3.11+
- Circle API Key (for Gateway)
- Arc Testnet account with USDC (optional for demo mode)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/usyc-agent-hackathon.git
cd usyc-agent-hackathon

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and addresses
```

### Run in Demo Mode (No blockchain required)

```bash
python main.py --demo
```

### Run API Server

```bash
# Demo mode
python main.py --api --demo

# Production mode (requires .env configuration)
python main.py --api --port 8000
```

## API Endpoints

### Vault Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/vault/deposit` | POST | Deposit USDC into vault |
| `/vault/withdraw` | POST | Withdraw shares from vault |
| `/vault/compound` | POST | Trigger yield compound |
| `/vault/balance` | GET | Get all balances |

### Circle Gateway

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gateway/transfer` | POST | Transfer USDC via Gateway |
| `/gateway/balance` | GET | Get Gateway wallet balance |

### x402 Autonomous Payments

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/x402/access` | POST | Access URL with auto-payment |
| `/x402/history` | GET | Get payment history |

### Demo Paywall

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/demo/paywall` | GET | Mock paywalled endpoint (returns 402) |
| `/demo/paywall/test-auto` | GET | Test autonomous payment flow |
| `/demo/payments` | GET | List received demo payments |

### Example: Autonomous Payment

```bash
# Test the autonomous payment flow
curl http://localhost:8000/demo/paywall/test-auto

# Response shows the agent:
# 1. Tried to access /demo/paywall
# 2. Received 402 Payment Required
# 3. Automatically paid 0.10 USDC
# 4. Successfully accessed premium content
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `deposit <amount>` | Deposit USDC into the vault |
| `withdraw <amount>` | Withdraw shares from the vault |
| `compound` | Trigger auto-compound of yields |
| `balance` | Show current balances |
| `receipts` | List generated PDF receipts |
| `events` | Show recent system events |
| `help` | Display available commands |
| `quit` | Exit the application |

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ARC_RPC_URL` | Arc Testnet RPC endpoint | `https://rpc.arc-testnet.circle.com` |
| `PRIVATE_KEY` | Wallet private key | - |
| `VAULT_CONTRACT` | YieldVault contract address | `0x2f685b...` |
| `USDC_CONTRACT` | USDC token contract address | - |
| `CIRCLE_API_KEY` | Circle Gateway API key | - |
| `CIRCLE_WALLET_ID` | Circle wallet ID | - |
| `MAX_DEPOSIT_AMOUNT` | Maximum deposit limit | `10000` |
| `MAX_WITHDRAW_AMOUNT` | Maximum withdraw limit | `10000` |
| `MAX_AUTO_PAYMENT` | Max autonomous payment | `10.0` |
| `COOLDOWN_SECONDS` | Cooldown between ops | `60` |

## Guardrails

The system includes built-in safety mechanisms:

- **Amount Limits**: Maximum deposit/withdraw amounts
- **Cooldown Periods**: Minimum time between operations
- **Balance Checks**: Verify sufficient funds before transactions
- **Auto-Payment Cap**: Maximum amount for autonomous x402 payments
- **Payment Verification**: Validate payment proofs before granting access

## Project Structure

```
usyc-agent-hackathon/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py        # Abstract base class
│   ├── event_bus.py         # Pub/sub event system
│   ├── vault_agent.py       # DeFi + Gateway operations
│   ├── media_agent.py       # PDF generation
│   ├── gateway_client.py    # Circle Gateway client
│   └── x402_handler.py      # x402 protocol handler
├── api/
│   ├── __init__.py
│   └── server.py            # FastAPI endpoints
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration
├── receipts/                # Generated PDFs
├── main.py                  # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Contract Information

- **Contract**: YieldVaultV2Upgradeable (ERC-4626)
- **Address**: `0x2f685b5Ef138Ac54F4CB1155A9C5922c5A58eD25`
- **Network**: Arc Testnet
- **Status**: Whitelisted with Circle Teller

## Branding

- Navy: `#1E3A5F`
- Blue: `#3498DB`
- Green: `#2ECC71`

## Author

**AbdelAziz**

## References

- [Circle Gateway Documentation](https://developers.circle.com/circle-mint/docs/getting-started-with-the-circle-apis)
- [x402 Protocol](https://www.circle.com/blog/autonomous-payments-using-circle-wallets-usdc-and-x402)
- [Arc Testnet](https://developers.circle.com/stablecoins/docs/usdc-on-testnet)

## License

MIT License

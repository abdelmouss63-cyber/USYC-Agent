#!/usr/bin/env python3
"""
USYC Protocol Labs - Multi-Agent DeFi System
Main entry point for CLI and API server.

Author: AbdelAziz
"""
import argparse
import asyncio
import sys
from typing import Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    # Fallback if colorama not installed
    class Fore:
        GREEN = YELLOW = RED = CYAN = BLUE = MAGENTA = WHITE = ""
    class Style:
        BRIGHT = RESET_ALL = ""

from agents import VaultAgent, MediaAgent, EventBus
from agents.event_bus import event_bus
from config import settings


BANNER = f"""
{Fore.CYAN}{Style.BRIGHT}
  _   _ ______   ______   _____           _                  _   _           _
 | | | |/ ___\\ \\ / / ___| |  __ \\         | |                | | | |         | |
 | | | |\\___ \\\\ V / |     | |__) | __ ___ | |_ ___   ___ ___ | | | |     __ _| |__  ___
 | | | | ___) || || |     |  ___/ '__/ _ \\| __/ _ \\ / __/ _ \\| | | |    / _` | '_ \\/ __|
 | |_| |/ __/ | || |____ _| |   | | | (_) | || (_) | (_| (_) | | | |___| (_| | |_) \\__ \\
  \\___/ |____||_| \\____(_)_|   |_|  \\___/ \\__\\___/ \\___\\___/|_| |______\\__,_|_.__/|___/
{Style.RESET_ALL}
{Fore.BLUE}                    Autonomous DeFi Yield Agent System{Style.RESET_ALL}
{Fore.WHITE}                    Vault: {settings.vault_contract[:10]}...{settings.vault_contract[-8:]}{Style.RESET_ALL}
"""


class CLI:
    """Interactive command-line interface for the agent system."""

    def __init__(self, demo_mode: bool = False):
        """
        Initialize the CLI.

        Args:
            demo_mode: If True, run in demo mode without blockchain
        """
        self.demo_mode = demo_mode
        self.vault_agent: Optional[VaultAgent] = None
        self.media_agent: Optional[MediaAgent] = None
        self.running = False

    async def start(self) -> None:
        """Start the CLI and agents."""
        print(BANNER)

        if self.demo_mode:
            print(f"{Fore.YELLOW}Running in DEMO mode - transactions are simulated{Style.RESET_ALL}\n")
        else:
            if not settings.is_configured:
                print(f"{Fore.RED}Error: Missing configuration. Please set PRIVATE_KEY and USDC_CONTRACT in .env{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Tip: Run with --demo flag to test without blockchain{Style.RESET_ALL}")
                sys.exit(1)
            print(f"{Fore.GREEN}Connected to Arc Testnet{Style.RESET_ALL}\n")

        # Initialize agents
        self.vault_agent = VaultAgent(demo_mode=self.demo_mode)
        self.media_agent = MediaAgent()

        await self.vault_agent.start()
        await self.media_agent.start()

        self.running = True
        await self._run_loop()

    async def stop(self) -> None:
        """Stop the CLI and agents."""
        self.running = False
        if self.vault_agent:
            await self.vault_agent.stop()
        if self.media_agent:
            await self.media_agent.stop()
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")

    def _print_help(self) -> None:
        """Print available commands."""
        print(f"""
{Fore.CYAN}{Style.BRIGHT}Available Commands:{Style.RESET_ALL}
  {Fore.GREEN}deposit <amount>{Style.RESET_ALL}  - Deposit USDC into the vault
  {Fore.GREEN}withdraw <amount>{Style.RESET_ALL} - Withdraw shares from the vault
  {Fore.GREEN}compound{Style.RESET_ALL}          - Trigger auto-compound of yields
  {Fore.GREEN}balance{Style.RESET_ALL}           - Show current balances
  {Fore.GREEN}receipts{Style.RESET_ALL}          - List generated receipts
  {Fore.GREEN}events{Style.RESET_ALL}            - Show recent events
  {Fore.GREEN}help{Style.RESET_ALL}              - Show this help message
  {Fore.GREEN}quit{Style.RESET_ALL}              - Exit the application
""")

    async def _run_loop(self) -> None:
        """Main command loop."""
        self._print_help()

        while self.running:
            try:
                prompt = f"{Fore.BLUE}usyc>{Style.RESET_ALL} "
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input(prompt)
                )

                if not user_input.strip():
                    continue

                await self._handle_command(user_input.strip())

            except KeyboardInterrupt:
                await self.stop()
                break
            except EOFError:
                await self.stop()
                break

    async def _handle_command(self, command: str) -> None:
        """
        Handle a CLI command.

        Args:
            command: The user input command
        """
        parts = command.lower().split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        try:
            if cmd == "deposit":
                if not args:
                    print(f"{Fore.RED}Usage: deposit <amount>{Style.RESET_ALL}")
                    return
                amount = float(args[0])
                print(f"{Fore.YELLOW}Depositing {amount} USDC...{Style.RESET_ALL}")
                result = await self.vault_agent.deposit(amount)
                print(f"{Fore.GREEN}Deposit successful!{Style.RESET_ALL}")
                print(f"  TX Hash: {result.get('tx_hash', 'N/A')}")
                print(f"  Shares Received: {result.get('shares_received', 'N/A')}")

            elif cmd == "withdraw":
                if not args:
                    print(f"{Fore.RED}Usage: withdraw <shares>{Style.RESET_ALL}")
                    return
                shares = float(args[0])
                print(f"{Fore.YELLOW}Withdrawing {shares} shares...{Style.RESET_ALL}")
                result = await self.vault_agent.withdraw(shares)
                print(f"{Fore.GREEN}Withdraw successful!{Style.RESET_ALL}")
                print(f"  TX Hash: {result.get('tx_hash', 'N/A')}")
                print(f"  USDC Received: {result.get('assets_received', 'N/A')}")

            elif cmd == "compound":
                print(f"{Fore.YELLOW}Triggering compound...{Style.RESET_ALL}")
                result = await self.vault_agent.compound()
                print(f"{Fore.GREEN}Compound successful!{Style.RESET_ALL}")
                print(f"  TX Hash: {result.get('tx_hash', 'N/A')}")
                if result.get('yield_compounded'):
                    print(f"  Yield Compounded: {result.get('yield_compounded')}")

            elif cmd == "balance":
                print(f"{Fore.YELLOW}Fetching balance...{Style.RESET_ALL}")
                balance = await self.vault_agent.get_balance()
                print(f"\n{Fore.CYAN}{Style.BRIGHT}Current Balance:{Style.RESET_ALL}")
                print(f"  Vault Shares: {Fore.GREEN}{balance.get('vault_shares', 0):.6f}{Style.RESET_ALL}")
                if balance.get('vault_value_usdc'):
                    print(f"  Vault Value:  {Fore.GREEN}{balance.get('vault_value_usdc'):.6f} USDC{Style.RESET_ALL}")
                print(f"  USDC Balance: {Fore.GREEN}{balance.get('usdc_balance', 0):.6f} USDC{Style.RESET_ALL}")
                if balance.get('address'):
                    print(f"  Address:      {balance.get('address')}")
                if balance.get('demo'):
                    print(f"  {Fore.YELLOW}(Demo Mode){Style.RESET_ALL}")

            elif cmd == "receipts":
                receipts = self.media_agent.list_receipts()
                if not receipts:
                    print(f"{Fore.YELLOW}No receipts generated yet{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.CYAN}{Style.BRIGHT}Generated Receipts:{Style.RESET_ALL}")
                    for r in receipts[:10]:  # Show last 10
                        print(f"  {Fore.GREEN}{r.name}{Style.RESET_ALL}")

            elif cmd == "events":
                events = event_bus.get_history(limit=10)
                if not events:
                    print(f"{Fore.YELLOW}No events yet{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.CYAN}{Style.BRIGHT}Recent Events:{Style.RESET_ALL}")
                    for e in reversed(events):
                        color = Fore.GREEN if "COMPLETED" in e.event_type.value else Fore.YELLOW
                        print(f"  {color}{e.event_type.value}{Style.RESET_ALL} - {e.timestamp.strftime('%H:%M:%S')}")

            elif cmd in ("help", "?"):
                self._print_help()

            elif cmd in ("quit", "exit", "q"):
                await self.stop()

            else:
                print(f"{Fore.RED}Unknown command: {cmd}{Style.RESET_ALL}")
                print(f"Type {Fore.GREEN}help{Style.RESET_ALL} for available commands")

        except ValueError as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


async def run_api(demo_mode: bool = False, host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Run the FastAPI server.

    Args:
        demo_mode: If True, run in demo mode
        host: Host to bind to
        port: Port to bind to
    """
    import uvicorn
    from api.server import create_app

    app = create_app(demo_mode=demo_mode)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="USYC Protocol Labs - Multi-Agent DeFi System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --demo              Run CLI in demo mode
  python main.py --api               Run API server
  python main.py --api --demo        Run API server in demo mode
  python main.py --api --port 8080   Run API on custom port
        """
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode (simulate transactions)"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run as API server instead of CLI"
    )
    parser.add_argument(
        "--host",
        default=settings.api_host,
        help=f"API server host (default: {settings.api_host})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.api_port,
        help=f"API server port (default: {settings.api_port})"
    )

    args = parser.parse_args()

    try:
        if args.api:
            print(BANNER)
            print(f"{Fore.GREEN}Starting API server on {args.host}:{args.port}{Style.RESET_ALL}")
            if args.demo:
                print(f"{Fore.YELLOW}Running in DEMO mode{Style.RESET_ALL}")
            asyncio.run(run_api(demo_mode=args.demo, host=args.host, port=args.port))
        else:
            cli = CLI(demo_mode=args.demo)
            asyncio.run(cli.start())
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Shutting down...{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    main()

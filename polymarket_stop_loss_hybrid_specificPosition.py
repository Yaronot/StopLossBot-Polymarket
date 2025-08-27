#!/usr/bin/env python3
"""
Polymarket Stop Loss Bot - Hybrid Version with Position Selection
Uses Data API for position monitoring + CLOB client for order execution

This bot:
1. Fetches positions using the reliable Data API (no auth required)
2. Allows user to select specific positions for stop loss monitoring
3. Monitors only selected position values against stop loss thresholds
4. Executes stop loss orders using CLOB client (authenticated with private key)

LEGAL WARNING: US residents are PROHIBITED from trading on Polymarket.
This script is for educational purposes and international users only.
"""



import os
import sys
import time
import json
import requests
import logging
from datetime import datetime
from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL
from typing import Dict, List, Optional, Set
from dataclasses import dataclass



# Import required packages
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import MarketOrderArgs
except ImportError:
    print("❌ Error: py-clob-client not installed")
    print("Run: pip install py-clob-client")
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("❌ Error: python-dotenv not installed")
    print("Run: pip install python-dotenv")
    sys.exit(1)


# for telegram bot
try:
    from telegram_overlay import TelegramOverlay
    TelegramOverlay.initialize()
except ImportError:
    print("⚠️ Telegram overlay not available. Continuing without Telegram notifications.")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class StopLossConfig:
    """Configuration for stop loss monitoring"""
    stop_loss_percentage: float = 20.0
    stop_loss_price: Optional[float] = None  # ADD THIS LINE
    check_interval: int = 60
    min_position_value: float = 0.1
    dry_run: bool = True
    max_slippage: float = 0.05
    selected_positions: Set[str] = None
    selection_mode: str = "none"

    def __post_init__(self):
        if self.selected_positions is None:
            self.selected_positions = set()


# =============================================================================
# POSITION DATA CLASS
# =============================================================================

@dataclass
class Position:
    """Represents a position from the Data API"""
    token_id: str
    market_name: str
    outcome: str
    size: float
    current_value: float
    current_price: float
    initial_value: float
    pnl: float
    pnl_percentage: float
    raw_data: Dict

    @classmethod
    def from_data_api(cls, raw_position: Dict) -> 'Position':
        """Create Position from Data API response"""
        try:
            # Extract data using CORRECT API field names
            token_id = raw_position.get('asset', '')  # Changed from 'tokenId' to 'asset'
            market_name = raw_position.get('title', 'Unknown Market')  # Changed from 'market' to 'title'
            outcome = raw_position.get('outcome', 'Unknown')
            size = float(raw_position.get('size', 0))
            current_value = float(raw_position.get('currentValue', 0))  # Changed from 'value' to 'currentValue'
            current_price = float(raw_position.get('curPrice', 0))  # Changed from 'price' to 'curPrice'
            initial_value = float(raw_position.get('initialValue', current_value))

            # Calculate P&L
            pnl = current_value - initial_value
            pnl_percentage = (pnl / initial_value * 100) if initial_value > 0 else 0

            return cls(
                token_id=token_id,
                market_name=market_name,
                outcome=outcome,
                size=size,
                current_value=current_value,
                current_price=current_price,
                initial_value=initial_value,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                raw_data=raw_position
            )
        except Exception as e:
            raise ValueError(f"Failed to parse position data: {e}")

    def get_display_id(self) -> str:
        """Get a short display ID for this position"""
        return f"{self.market_name[:30]}...{self.outcome}" if len(
            self.market_name) > 30 else f"{self.market_name} - {self.outcome}"


# =============================================================================
# DATA API CLIENT
# =============================================================================

class PolymarketDataClient:
    """Client for fetching positions from Polymarket Data API"""

    def __init__(self, user_file: str = "user.txt"):
        self.base_url = "https://data-api.polymarket.com"
        self.user_address = self._load_user_address(user_file)

    def _load_user_address(self, user_file: str) -> str:
        """Load user address from file"""
        try:
            if not os.path.exists(user_file):
                # Create example file
                with open(user_file, 'w') as f:
                    f.write("0x1234567890123456789012345678901234567890\n")
                    f.write("# Replace with your actual Polygon wallet address\n")

                print(f"📁 Created {user_file} with example address")
                print(f"✏️  Please edit {user_file} with your wallet address")
                return ""

            with open(user_file, 'r') as f:
                lines = f.readlines()

            # Get first non-comment line
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    return line

            return ""

        except Exception as e:
            print(f"❌ Error loading user address: {e}")
            return ""

    def fetch_positions(self, config: StopLossConfig) -> List[Position]:
        """Fetch current positions from Data API"""
        if not self.user_address:
            raise Exception("No user address configured")

        url = f"{self.base_url}/positions"
        params = {
            "sizeThreshold": str(config.min_position_value),
            "limit": "100",
            "sortDirection": "DESC",
            "user": self.user_address
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            raw_positions = response.json()

            # Convert to Position objects
            positions = []
            for i, raw_pos in enumerate(raw_positions):
                try:
                    position = Position.from_data_api(raw_pos)

                    if position.current_value >= config.min_position_value:
                        positions.append(position)

                except Exception as e:
                    print(f"  ❌ FAILED TO PARSE: {e}")
                    continue

            return positions

        except Exception as e:
            raise Exception(f"Failed to fetch positions: {e}")


# =============================================================================
# CLOB TRADING CLIENT
# =============================================================================

class PolymarketTradingClient:
    """Fixed client for executing orders using CLOB"""

    def __init__(self):
        self.client = None
        self.POLYMARKET_PROXY_ADDRESS = '0x8f87964FB57640a6fC09964123c6212c2c5c07B9'
        self._initialize_client()

    def _initialize_client(self):
        """Initialize CLOB client with proper configuration"""
        try:
            private_key = os.getenv("PRIVATE_KEY")
            if not private_key:
                raise Exception("PRIVATE_KEY not found in .env file")

            # Initialize client with SAME configuration as working script
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=private_key,
                chain_id=137,
                signature_type=1,  # ADDED: This was missing!
                funder=self.POLYMARKET_PROXY_ADDRESS  # ADDED: This was missing!
            )

            # Setup API credentials
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)

            # Test authentication
            wallet_address = self.client.get_address()
            logging.info(f"✅ CLOB client initialized for wallet: {wallet_address}")

        except Exception as e:
            raise Exception(f"Failed to initialize CLOB client: {e}")

    def execute_market_sell(self, position, config) -> Dict:
        """Execute a market sell order with improved liquidity handling"""
        try:
            print(f"\n🔧 DEBUG: Starting order execution (IMPROVED VERSION)...")
            print(f"   Token ID: {position.token_id}")
            print(f"   Market: {position.market_name}")
            print(f"   Size to sell: {position.size}")
            print(f"   Current price: ${position.current_price}")

            # Strategy 1: Get current orderbook to find best bid price
            try:
                orderbook = self.client.get_order_book(position.token_id)
                bids = orderbook.get('bids', [])

                if bids:
                    # Use the best bid price (highest price someone is willing to pay)
                    best_bid = float(bids[0]['price'])
                    sell_price = max(0.001, best_bid)  # Use best bid price
                    print(f"🔧 DEBUG: Using best bid price: ${sell_price:.6f}")
                else:
                    # Fallback: Use current price with larger discount for liquidity
                    sell_price = max(0.001, position.current_price * 0.95)  # 5% below current
                    print(f"🔧 DEBUG: No bids found, using discounted price: ${sell_price:.6f}")

            except Exception as e:
                print(f"🔧 DEBUG: Could not get orderbook: {e}")
                # Fallback: More aggressive pricing
                sell_price = max(0.001, position.current_price * 0.90)  # 10% below current
                print(f"🔧 DEBUG: Using fallback aggressive price: ${sell_price:.6f}")

            # Strategy 2: Try smaller chunks if position is large
            chunk_size = min(position.size, 50.0)  # Max 50 tokens per order
            remaining_size = position.size
            total_filled = 0
            orders_placed = []

            while remaining_size > 0.1:  # Keep going until almost nothing left
                current_chunk = min(remaining_size, chunk_size)

                print(f"🔧 DEBUG: Attempting to sell {current_chunk} tokens at ${sell_price:.6f}")

                # Create order
                order_args = OrderArgs(
                    price=sell_price,
                    size=current_chunk,
                    side=SELL,
                    token_id=position.token_id
                )

                signed_order = self.client.create_order(order_args)

                # Try GTC first (Good Till Cancelled) - more likely to fill
                try:
                    result = self.client.post_order(signed_order, OrderType.GTC)

                    if result.get('success', False):
                        order_id = result.get('orderID', 'N/A')
                        print(f"✅ Order placed successfully: {order_id}")
                        orders_placed.append(result)
                        total_filled += current_chunk
                        remaining_size -= current_chunk

                        # Wait a moment for potential fill
                        time.sleep(2)

                        # Check if order was filled
                        try:
                            order_status = self.client.get_order(order_id)
                            if order_status.get('status') == 'FILLED':
                                print(f"✅ Order {order_id} filled completely")
                            else:
                                print(f"⏳ Order {order_id} status: {order_status.get('status', 'unknown')}")
                        except:
                            print(f"⚠️ Could not check order status for {order_id}")

                    else:
                        error_msg = result.get('errorMsg', 'Unknown error')
                        print(f"❌ Order failed: {error_msg}")

                        # If this chunk fails, try with even lower price
                        sell_price = max(0.001, sell_price * 0.95)
                        print(f"🔧 DEBUG: Reducing price to ${sell_price:.6f} and retrying")
                        continue

                except Exception as e:
                    print(f"❌ Exception placing order: {e}")
                    # Try even more aggressive pricing
                    sell_price = max(0.001, sell_price * 0.90)
                    print(f"🔧 DEBUG: Exception occurred, reducing price to ${sell_price:.6f}")
                    continue

            # Strategy 3: If we still have significant amount left, place a very low price order
            if remaining_size > 0.1:
                print(f"🔧 DEBUG: {remaining_size} tokens remaining, placing final low-price order")

                # Very aggressive final price
                final_price = max(0.001, position.current_price * 0.50)  # 50% below current

                order_args = OrderArgs(
                    price=final_price,
                    size=remaining_size,
                    side=SELL,
                    token_id=position.token_id
                )

                try:
                    signed_order = self.client.create_order(order_args)
                    result = self.client.post_order(signed_order, OrderType.GTC)

                    if result.get('success', False):
                        orders_placed.append(result)
                        total_filled += remaining_size
                        print(f"✅ Final order placed for {remaining_size} tokens at ${final_price:.6f}")

                except Exception as e:
                    print(f"❌ Final order failed: {e}")

            # Summary
            if orders_placed:
                logging.info(
                    f"✅ STOP LOSS EXECUTED: Placed {len(orders_placed)} orders for "
                    f"{position.market_name} ({position.outcome}). "
                    f"Target: {position.size}, Ordered: {total_filled}"
                )

                return {
                    "success": True,
                    "orders_placed": len(orders_placed),
                    "total_size_ordered": total_filled,
                    "remaining_size": position.size - total_filled,
                    "order_details": orders_placed
                }
            else:
                return {
                    "success": False,
                    "error": "No orders could be placed",
                    "attempted_size": position.size
                }

        except Exception as e:
            print(f"🔧 DEBUG: Exception in execute_market_sell:")
            print(f"   Error: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to execute stop loss order: {e}")

    def execute_true_market_sell(self, position, config) -> Dict:
        """Alternative method: Execute using market order if available"""
        try:
            print(f"\n🔧 DEBUG: Trying TRUE market order method...")

            # Check if market order methods exist
            if hasattr(self.client, 'create_market_order'):
                from py_clob_client.clob_types import MarketOrderArgs

                order_args = MarketOrderArgs(
                    token_id=position.token_id,
                    amount=position.size,
                    side="SELL"
                )

                signed_order = self.client.create_market_order(order_args)
                result = self.client.post_order(signed_order, OrderType.FOK)

                return {"success": result.get('success', False), "result": result}
            else:
                print("❌ create_market_order method not available")
                return {"success": False, "error": "market_order_not_supported"}

        except Exception as e:
            print(f"❌ True market order failed: {e}")
            return {"success": False, "error": str(e)}


# =============================================================================
# POSITION SELECTION MANAGER
# =============================================================================

class PositionSelector:
    """Handles position selection for targeted stop loss monitoring"""

    @staticmethod
    def save_selected_positions(selected_positions: Set[str], filename: str = "selected_positions.json"):
        """Save selected positions to file"""
        try:
            with open(filename, 'w') as f:
                json.dump(list(selected_positions), f, indent=2)
        except Exception as e:
            print(f"❌ Error saving selected positions: {e}")

    @staticmethod
    def load_selected_positions(filename: str = "selected_positions.json") -> Set[str]:
        """Load selected positions from file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                    return set(data) if isinstance(data, list) else set()
            return set()
        except Exception as e:
            print(f"❌ Error loading selected positions: {e}")
            return set()

    @staticmethod
    def display_positions_for_selection(positions: List[Position]) -> Dict[int, Position]:
        """Display positions with selection numbers"""
        if not positions:
            print("📊 No positions found above minimum threshold")
            return {}

        print("\n" + "=" * 100)
        print("📊 AVAILABLE POSITIONS FOR SELECTION")
        print("=" * 100)
        print(f"{'#':<3} {'Market':<35} {'Outcome':<10} {'Value':<10} {'P&L':<10} {'P&L%':<8} ")
        print("-" * 100)

        position_map = {}
        for i, pos in enumerate(positions, 1):
            position_map[i] = pos
            print(f"{i:<3} {pos.market_name[:34]:<35} "
                  f"{pos.outcome[:9]:<10} "
                  f"${pos.current_value:>8.2f} "
                  f"${pos.pnl:>8.2f} "
                  f"{pos.pnl_percentage:>6.1f}% ")

        print("-" * 100)
        return position_map

    @staticmethod
    def interactive_position_selection(positions: List[Position], current_selected: Set[str]) -> Set[str]:
        """Interactive position selection interface"""
        position_map = PositionSelector.display_positions_for_selection(positions)

        if not position_map:
            return current_selected

        # Show currently selected positions
        if current_selected:
            selected_positions = [pos for pos in positions if pos.token_id in current_selected]
            print(f"\n{'=' * 60}")
            print(f"🎯 CURRENTLY SELECTED POSITIONS ({len(selected_positions)})")
            print(f"{'=' * 60}")
            print(f"{'#':<3} {'Market':<30} {'Outcome':<10} {'Value':<10} {'P&L%':<8}")
            print(f"{'-' * 60}")
            for i, pos in enumerate(selected_positions, 1):
                print(f"{i:<3} {pos.market_name[:29]:<30} "
                      f"{pos.outcome[:9]:<10} "
                      f"${pos.current_value:>8.2f} "
                      f"{pos.pnl_percentage:>6.1f}%")
            print(f"{'=' * 60}")
        else:
            print(f"\n{'=' * 40}")
            print("🎯 NO POSITIONS CURRENTLY SELECTED")
            print(f"{'=' * 40}")

        print(f"\n📝 SELECTION OPTIONS:")
        print("   • Enter position numbers (comma-separated): e.g., '1,3,5'")
        print("   • Enter 'all' to select all positions")
        print("   • Enter 'clear' to clear all selections")
        print("   • Enter 'done' to finish selection")

        while True:
            try:
                user_input = input(f"\nEnter your selection: ").strip().lower()

                if user_input == 'done':
                    break
                elif user_input == 'all':
                    current_selected = {pos.token_id for pos in positions}
                    print(f"✅ Selected all {len(positions)} positions")
                elif user_input == 'clear':
                    current_selected = set()
                    print("✅ Cleared all selections")
                elif user_input:
                    # Parse comma-separated numbers
                    try:
                        numbers = [int(x.strip()) for x in user_input.split(',') if x.strip()]
                        new_selections = set()

                        for num in numbers:
                            if num in position_map:
                                new_selections.add(position_map[num].token_id)
                            else:
                                print(f"❌ Invalid position number: {num}")
                                continue

                        if new_selections:
                            current_selected = new_selections
                            selected_names = [position_map[num].get_display_id()
                                              for num in numbers if num in position_map]
                            print(f"✅ Selected {len(new_selections)} positions:")
                            for name in selected_names:
                                print(f"   • {name}")

                    except ValueError:
                        print("❌ Invalid input. Use numbers separated by commas (e.g., '1,3,5')")

            except KeyboardInterrupt:
                print("\n❌ Selection cancelled")
                break

        return current_selected


# =============================================================================
# MAIN STOP LOSS BOT
# =============================================================================

class PolymarketStopLossBot:
    """Main stop loss bot combining Data API monitoring with CLOB execution"""

    def __init__(self, config: StopLossConfig):
        self.config = config
        self.data_client = PolymarketDataClient()
        self.trading_client = None
        self.stop_loss_log = []

        # Load previously selected positions
        if self.config.selection_mode == "selected":
            self.config.selected_positions = PositionSelector.load_selected_positions()

        # Setup logging
        self._setup_logging()

        # Initialize trading client only if not in dry run mode
        if not config.dry_run:
            self.trading_client = PolymarketTradingClient()

    def _setup_logging(self):
        """Setup logging for the bot"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('polymarket_stop_loss.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def validate_configuration(self) -> bool:
        """Validate bot configuration before starting"""
        if self.config.selection_mode == "none":
            self.logger.error("❌ Cannot start monitoring: No monitoring mode selected")
            self.logger.error("   Use option 7 to select specific positions or option 8 to monitor all")
            return False

        if self.config.selection_mode == "selected" and not self.config.selected_positions:
            self.logger.error("❌ Invalid configuration: 'selected' mode with no positions selected")
            return False

        if not self.data_client.user_address:
            self.logger.error("❌ Invalid configuration: No user address configured")
            return False

        return True

    def fetch_current_positions(self) -> List[Position]:
        """Fetch current positions using Data API"""
        try:
            positions = self.data_client.fetch_positions(self.config)
            return positions
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch positions: {e}")
            return []

    def filter_monitored_positions(self, positions: List[Position]) -> List[Position]:
        """Filter positions based on selection mode"""
        if self.config.selection_mode == "all":
            return positions
        elif self.config.selection_mode == "selected":
            if not self.config.selected_positions:
                self.logger.warning("⚠️ Selection mode is 'selected' but no positions are selected!")
                return []

            monitored = [pos for pos in positions if pos.token_id in self.config.selected_positions]

            missing_count = len(self.config.selected_positions) - len(monitored)
            if missing_count > 0:
                self.logger.warning(f"⚠️ {missing_count} selected positions not found in current portfolio")

            return monitored
        elif self.config.selection_mode == "none":
            # NEW: Handle "none" mode
            self.logger.info("📵 Monitoring mode is NONE - no positions will be monitored")
            return []

        return []  # Fallback - monitor nothing if mode is unclear

    def check_stop_loss_triggers(self, positions: List[Position]) -> List[Position]:
        """Check which positions have triggered stop loss"""
        monitored_positions = self.filter_monitored_positions(positions)
        triggered_positions = []

        for position in monitored_positions:
            # Check percentage-based stop loss
            percentage_triggered = position.pnl_percentage <= -self.config.stop_loss_percentage

            price_triggered = (self.config.stop_loss_price is not None and
                               position.current_price <= self.config.stop_loss_price)

            if percentage_triggered or price_triggered:
                triggered_positions.append(position)
                trigger_reason = []
                if percentage_triggered:
                    trigger_reason.append(f"Loss: {position.pnl_percentage:.2f}%")
                if price_triggered:
                    trigger_reason.append(f"Price: ${position.current_price:.3f} <= ${self.config.stop_loss_price:.3f}")

                self.logger.warning(
                    f"🚨 STOP LOSS TRIGGERED: {position.market_name} ({position.outcome}) "
                    f"- {' | '.join(trigger_reason)}"
                )

        return triggered_positions

    def execute_stop_loss(self, position: Position) -> bool:
        """Execute stop loss for a position"""
        try:
            if self.config.dry_run:
                self.logger.info(
                    f"🔥 DRY RUN: Would sell {position.size} of {position.market_name} "
                    f"({position.outcome}) at ~${position.current_price:.4f}"
                )
                return True

            if not self.trading_client:
                raise Exception("Trading client not initialized")

            # Execute the order
            result = self.trading_client.execute_market_sell(position, self.config)

            # Log the execution
            self.stop_loss_log.append({
                "timestamp": datetime.now().isoformat(),
                "position": {
                    "market": position.market_name,
                    "outcome": position.outcome,
                    "size": position.size,
                    "value": position.current_value,
                    "pnl": position.pnl,
                    "pnl_percentage": position.pnl_percentage
                },
                "order_result": result
            })

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to execute stop loss: {e}")
            return False

    def print_positions_summary(self, positions: List[Position]):
        """Print a summary of current positions with monitoring status"""
        if not positions:
            print("📊 No positions found above minimum threshold")
            return

        # Get monitored positions
        monitored_positions = self.filter_monitored_positions(positions)
        monitored_token_ids = {pos.token_id for pos in monitored_positions}

        print("\n" + "=" * 120)
        stop_loss_config = f"Stop Loss %: {self.config.stop_loss_percentage}%"
        if self.config.stop_loss_price:
            stop_loss_config += f", Stop Loss Price: ${self.config.stop_loss_price:.3f}"

        print(f"📊 POSITIONS SUMMARY ({len(positions)} total, {len(monitored_positions)} monitored) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Configuration: {stop_loss_config}")
        print("=" * 120)
        print(
            f"{'Market':<35} {'Outcome':<10} {'Price':<8} {'Amount':<10} {'Value':<10} {'P&L':<10} {'P&L%':<8} {'Monitor':<8} {'Status'}")
        print("-" * 120)

        total_value = 0
        total_pnl = 0

        for pos in positions:
            # Check monitoring status
            is_monitored = pos.token_id in monitored_token_ids
            monitor_status = "🎯 YES" if is_monitored else "   NO"

            # Check if stop loss would trigger (only for monitored positions)
            percentage_triggered = (is_monitored and
                                    pos.pnl_percentage <= -self.config.stop_loss_percentage)
            price_triggered = (is_monitored and
                               self.config.stop_loss_price is not None and
                               pos.current_price <= self.config.stop_loss_price)
            stop_loss_triggered = percentage_triggered or price_triggered
            status = "🚨 STOP LOSS" if stop_loss_triggered else "✅ OK"

            print(f"{pos.market_name[:34]:<35} "
                  f"{pos.outcome[:9]:<10} "
                  f"${pos.current_price:>6.4f} "
                  f"{pos.size:>9.2f} "
                  f"{pos.current_value:>8.2f} "
                  f"${pos.pnl:>8.2f} "
                  f"${pos.pnl_percentage:>11.1f}% "
                  f"{monitor_status:<13} "
                  f"{status}")

            total_value += pos.current_value
            total_pnl += pos.pnl

        print("-" * 120)
        print(f"{'TOTAL':<35} {'':<10} {'':<8} {'':<10} {total_value:>8.2f} ${total_pnl:>8.2f}")
        print("=" * 120)

        # FIXED: Show selection mode info with proper handling of "none" mode
        if self.config.selection_mode == "selected":
            print(f"🎯 MONITORING MODE: Selected positions only ({len(monitored_positions)} positions)")
        elif self.config.selection_mode == "all":
            print(f"🎯 MONITORING MODE: All positions ({len(positions)} positions)")
        elif self.config.selection_mode == "none":
            print(f"🎯 MONITORING MODE: None (0 positions monitored)")
        else:
            print(f"🎯 MONITORING MODE: Unknown mode ({self.config.selection_mode})")
        print("=" * 120)

    def save_stop_loss_log(self):
        """Save stop loss execution log to file"""
        if self.stop_loss_log:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stop_loss_executions_{timestamp}.json"

            try:
                with open(filename, 'w') as f:
                    json.dump(self.stop_loss_log, f, indent=2)
                self.logger.info(f"💾 Stop loss log saved to: {filename}")
            except Exception as e:
                self.logger.error(f"❌ Failed to save log: {e}")

    def run_monitoring_cycle(self) -> bool:
        """Run one complete monitoring cycle"""
        try:
            self.logger.info("🔄 Starting monitoring cycle...")

            # 1. Fetch current positions from Data API
            positions = self.fetch_current_positions()
            if not positions:
                self.logger.info("📊 No positions found")
                return True

            # 2. Print positions summary
            self.print_positions_summary(positions)

            # 3. Check for stop loss triggers (only on monitored positions)
            triggered_positions = self.check_stop_loss_triggers(positions)

            # 4. Execute stop loss orders
            if triggered_positions:
                self.logger.warning(f"🚨 {len(triggered_positions)} positions triggered stop loss")

                for position in triggered_positions:
                    success = self.execute_stop_loss(position)
                    if not success:
                        self.logger.error(f"❌ Failed to execute stop loss for {position.market_name}")

                # Save execution log
                self.save_stop_loss_log()
            else:
                self.logger.info("✅ No stop loss triggers")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error in monitoring cycle: {e}")
            return False

    def select_positions_for_monitoring(self):
        """Interactive position selection"""
        try:
            positions = self.fetch_current_positions()
            if not positions:
                print("📊 No positions found to select from")
                return

            # Interactive selection
            new_selections = PositionSelector.interactive_position_selection(
                positions, self.config.selected_positions
            )

            # Update configuration
            self.config.selected_positions = new_selections
            self.config.selection_mode = "selected" if new_selections else "all"

            # Save selections
            PositionSelector.save_selected_positions(new_selections)

            if new_selections:
                print(f"\n✅ Selected {len(new_selections)} positions for stop loss monitoring")
                print("💾 Selections saved to selected_positions.json")
            else:
                print("\n⚠️ No positions selected - will monitor all positions")

        except Exception as e:
            print(f"❌ Error during position selection: {e}")

    def start_monitoring(self):
        """Start the continuous monitoring loop"""
        self.logger.info("🚀 Starting Polymarket Stop Loss Bot - Enhanced Version")
        self.logger.info(f"📊 Configuration:")
        self.logger.info(f"   Stop Loss Percentage: {self.config.stop_loss_percentage}%")
        if self.config.stop_loss_price:
            self.logger.info(f"   Stop Loss Price: ${self.config.stop_loss_price:.3f}")
        self.logger.info(f"   Check Interval: {self.config.check_interval}s")
        self.logger.info(f"   Min Position Value: ${self.config.min_position_value}")
        self.logger.info(f"   Dry Run Mode: {self.config.dry_run}")
        self.logger.info(f"   Selection Mode: {self.config.selection_mode}")
        self.logger.info(f"   Selected Positions: {len(self.config.selected_positions)}")
        self.logger.info(f"   User Address: {self.data_client.user_address}")

        if self.config.dry_run:
            self.logger.warning("⚠️  RUNNING IN DRY RUN MODE - No actual trades will be executed")

        if self.config.selection_mode == "selected" and not self.config.selected_positions:
            self.logger.warning("⚠️  No positions selected - will monitor all positions")
            self.config.selection_mode = "all"

        try:
            while True:
                success = self.run_monitoring_cycle()
                if not success:
                    self.logger.error("❌ Monitoring cycle failed, continuing...")

                self.logger.info(f"⏰ Next check in {self.config.check_interval} seconds")
                time.sleep(self.config.check_interval)

        except KeyboardInterrupt:
            self.logger.info("👋 Stop loss bot stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal error: {e}")
            raise


# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    """Main function with enhanced configuration interface"""
    print("\n" + "=" * 70)
    print("🛡️  Polymarket Stop Loss Bot - Enhanced Version")
    print("📊 Data API monitoring + CLOB execution + Position Selection")
    print("⚠️  WARNING: US residents are prohibited from trading on Polymarket")
    print("=" * 70)

    # Check for required files and environment
    if not os.path.exists("user.txt"):
        print("❌ user.txt file not found")
        print("Create user.txt with your wallet address")
        return

    if not os.getenv("PRIVATE_KEY"):
        print("❌ PRIVATE_KEY not found in .env file")
        print("Create .env file with: PRIVATE_KEY=your_polygon_private_key")
        return

    # Configuration
    config = StopLossConfig()  # Now defaults to "none"

    # Load previously selected positions if they exist
    saved_positions = PositionSelector.load_selected_positions()

    print(f" " * 60)
    print(f"\n🎯 DEFAULT STOP LOSS CONFIGURATION:")

    # Basic settings
    print(f"   Stop Loss Percentage: {config.stop_loss_percentage}%")
    print(f"   Stop Loss Price: ${config.stop_loss_price:.3f}" if config.stop_loss_price else "   Stop Loss Price: Not set")
    print(f"   Check Interval: {config.check_interval} seconds")
    print(f"   Minimum Position Value: ${config.min_position_value}")
    print(f"   Max Slippage: {config.max_slippage * 100}%")
    print(f"   Dry Run Mode: {'ON' if config.dry_run else 'OFF'}")
    print(f" " * 60)
    print(f"=" * 60)

    if saved_positions:
        config.selected_positions = saved_positions
        config.selection_mode = "selected"
        print(f"📁 Loaded {len(saved_positions)} previously selected positions")
        print(f" " * 60)
        print("🎯 Monitoring mode: SELECTED POSITIONS")
    else:
        print(f" " * 60)
        print("🎯 Monitoring mode: NONE")
        print("⚠️  Bot will NOT monitor any positions until you choose a monitoring mode")
        print("Use option 7 to select specific positions or option 8 to monitor all")

    while True:
        print("\n" + "=" * 70)
        print(f"🚨  CHOOSE AN OPTION:")
        print("1. Start monitoring with current settings")
        print("2. Change stop loss percentage")
        print("3. Change check interval")
        print("4. Change minimum position value")
        print("5. Toggle dry run mode")
        print("6. Test connection and show positions")
        print("7. Select specific positions to monitor")
        print("8. Switch to monitor all positions")
        print("9. View current monitoring configuration")
        print("10. Exit")
        print("11. Clear monitoring mode (set to NONE)")

        choice = input(f"\nSelect option (1-11): ").strip()

        if choice == "1":
            # Validate configuration before starting
            if config.selection_mode == "none":
                print("❌ Cannot start monitoring: No monitoring mode selected")
                print("   Use option 7 to select specific positions or option 8 to monitor all")
                continue  # Don't break, go back to menu
            elif config.selection_mode == "selected" and not config.selected_positions:
                print("❌ Cannot start monitoring: No positions selected")
                print("   Use option 7 to select positions or option 8 to monitor all")
                continue  # Don't break, go back to menu

            # Configuration is valid, start monitoring
            break


        elif choice == "2":
            try:
                new_pct = float(input(f"Enter stop loss percentage (current: {config.stop_loss_percentage}%): "))
                if 0 < new_pct <= 100:
                    config.stop_loss_percentage = new_pct
                    print(f"✅ Stop loss set to {new_pct}%")
                else:
                    print("❌ Invalid percentage (must be 0-100)")
            except ValueError:
                print("❌ Invalid number")
        elif choice == "3":
            try:
                new_interval = int(input(f"Enter check interval in seconds (current: {config.check_interval}): "))
                if new_interval >= 10:
                    config.check_interval = new_interval
                    print(f"✅ Check interval set to {new_interval} seconds")
                else:
                    print("❌ Interval must be at least 10 seconds")
            except ValueError:
                print("❌ Invalid number")

        elif choice == "4":
            print("\n4a. Change minimum position value")
            print("4b. Set stop loss price threshold")
            sub_choice = input("Choose 4a or 4b: ").strip().lower()

            if sub_choice == "4a":
                try:
                    new_min = float(input(f"Enter minimum position value (current: ${config.min_position_value}): "))
                    if new_min >= 0:
                        config.min_position_value = new_min
                        print(f"✅ Minimum position value set to ${new_min}")
                    else:
                        print("❌ Value must be positive")
                except ValueError:
                    print("❌ Invalid number")

            elif sub_choice == "4b":
                try:
                    current_price_str = f"${config.stop_loss_price:.3f}" if config.stop_loss_price else "Not set"
                    new_price_input = input(
                        f"Enter stop loss price (current: {current_price_str}, 'clear' to remove): ").strip()

                    if new_price_input.lower() == 'clear':
                        config.stop_loss_price = None
                        print("✅ Stop loss price cleared")
                    else:
                        new_price = float(new_price_input)
                        if new_price > 0:
                            config.stop_loss_price = new_price
                            print(f"✅ Stop loss price set to ${new_price:.3f}")
                        else:
                            print("❌ Price must be positive")
                except ValueError:
                    print("❌ Invalid number")
            else:
                print("❌ Invalid choice")




        elif choice == "5":
            config.dry_run = not config.dry_run
            print(f"✅ Dry run mode: {'ON' if config.dry_run else 'OFF'}")
            if not config.dry_run:
                confirm = input(
                    "⚠️  WARNING: Dry run is OFF. Real trades will be executed! Type 'CONFIRM' to proceed: ")
                if confirm != "CONFIRM":
                    config.dry_run = True
                    print("✅ Dry run mode turned back ON")


        elif choice == "6":
            try:
                bot = PolymarketStopLossBot(config)
                bot.run_monitoring_cycle()
            except Exception as e:
                print(f"❌ Error during test: {e}")


        elif choice == "7":
            try:
                bot = PolymarketStopLossBot(config)
                bot.select_positions_for_monitoring()
                # Update config with new selections
                config.selected_positions = bot.config.selected_positions

                # Set mode based on selections
                if config.selected_positions:
                    config.selection_mode = "selected"
                    print(f"✅ Monitoring mode set to: SELECTED POSITIONS ({len(config.selected_positions)})")
                else:
                    config.selection_mode = "none"
                    print(f"⚠️  No positions selected - monitoring mode set to: NONE")

            except Exception as e:
                print(f"❌ Error during position selection: {e}")

        elif choice == "8":
            config.selection_mode = "all"
            config.selected_positions = set()
            print("✅ Switched to monitoring ALL positions")



        elif choice == "9":
            print(f"\n🎯 CURRENT MONITORING CONFIGURATION:")

            if config.selection_mode == "none":
                print(f"   Mode: NONE")
                print(f"   Status: ⚠️  No positions will be monitored")
                print(f"   Action needed: Use option 7 to select positions or option 8 to monitor all")

            elif config.selection_mode == "all":
                print(f"   Mode: ALL POSITIONS")
                print(f"   Status: ✅ Will monitor every position above minimum threshold")
                try:
                    temp_bot = PolymarketStopLossBot(config)
                    positions = temp_bot.fetch_current_positions()
                    if positions:
                        print(f"\n📊 ALL POSITIONS WILL BE MONITORED ({len(positions)}):")
                        for i, pos in enumerate(positions, 1):
                            print(f"   {i}. {pos.market_name} - {pos.outcome}")
                            print(f"      Value: ${pos.current_value:.2f}, P&L: {pos.pnl_percentage:.1f}%")
                    else:
                        print("   📊 No positions found in your portfolio")
                except Exception as e:
                    print(f"   ❌ Error fetching positions: {e}")

            elif config.selection_mode == "selected":
                print(f"   Mode: SELECTED POSITIONS")
                if config.selected_positions:
                    print(f"   Status: ✅ Will monitor {len(config.selected_positions)} selected positions")
                    try:
                        temp_bot = PolymarketStopLossBot(config)
                        positions = temp_bot.fetch_current_positions()
                        selected_positions = [pos for pos in positions if pos.token_id in config.selected_positions]

                        print(f"\n📊 SELECTED POSITIONS WILL BE MONITORED ({len(selected_positions)}):")
                        for i, pos in enumerate(selected_positions, 1):
                            print(f"   {i}. {pos.market_name} - {pos.outcome}")
                            print(f"      Value: ${pos.current_value:.2f}, P&L: {pos.pnl_percentage:.1f}%")

                        if len(selected_positions) < len(config.selected_positions):
                            missing = len(config.selected_positions) - len(selected_positions)
                            print(f"   ⚠️  {missing} selected positions not found in current portfolio")

                    except Exception as e:
                        print(f"   ❌ Error fetching position details: {e}")
                else:
                    print(f"   Status: ⚠️  No positions selected")
                    print(f"   Action needed: Use option 7 to select positions")


        elif choice == "10":  # REMOVE the duplicate elif choice == "9" block
            print("👋 Goodbye!")
            return

        elif choice == "11":
            config.selection_mode = "none"
            config.selected_positions = set()
            PositionSelector.save_selected_positions(set())  # Clear saved selections
            print("✅ Monitoring mode set to: NONE")
            print("   Bot will not monitor any positions until you select a mode")

        else:
            print("❌ Invalid choice")

    # Start the bot
    try:
        bot = PolymarketStopLossBot(config)
        bot.start_monitoring()
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Bot interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
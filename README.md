# Polymarket Stop Loss Bot

Polymarket currently lacks stop-loss functionality, a fundamental risk management tool standard across virtually all major trading platforms. This critical omission forces users to seek alternative loss mitigation strategies such as hedging, yet these workarounds fail to adequately address numerous scenarios where losses could be minimized. This repository solves this problem by utilizing Polymarket's API infrastructure to deliver automated stop-loss protection featuring sophisticated position selection and continuous monitoring capabilities.

## Legal Disclaimer

**US RESIDENTS ARE PROHIBITED FROM TRADING ON POLYMARKET.** This tool is intended for educational purposes. Use at your own risk and ensure compliance with your local regulations.
The developer assume no responsibility for trading losses, technical failures, or legal issues arising from use of this software.

## Features

- **Hybrid Architecture**: Uses Data API for reliable position monitoring + CLOB client for order execution
- **Flexible Position Selection**: Monitor all positions or select specific ones
- **Advanced Order Execution**: Multiple strategies for improved liquidity handling
- **Dry Run Mode**: Test the bot without executing real trades
- **CSV Export**: Convert execution logs to CSV format for analysis
- **Real-time Monitoring**: Continuous position monitoring with configurable intervals
- **Telegram Notifications (Optional)**: Integrate a Telegram bot to send updates whenever a stop-loss action is triggered.

## Prerequisites

### System Requirements
- Python 3.7+
- Active Polymarket account (non-US residents only)
- Polygon wallet with USDC balance for trading
- Stable internet connection

### Required Information
- **Polygon Wallet Address**: Your wallet address holding Polymarket positions
- **Private Key**: For executing trades (stored securely in .env file)
- **USDC Balance**: Sufficient funds for gas fees and potential trades

## Installation

### 1. Clone Repository
```bash
git clone https://github.com/Yaronot/StopLossBot-Polymarket
```

### 2. Install Dependencies
```bash
pip install py-clob-client python-dotenv requests
```

### 3. Configuration Files Setup

#### Adjust `.env` file with your private key:
```
PRIVATE_KEY=0x1234567890abcdef
```

#### Adjust `user.txt` file with your wallet address:
```
0xYourPolygonWalletAddressHere
```
#### If you want to integrate a telegram bot that notifies when stop-loss action is triggered, uncomment TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID from .env (they're commented by default to make this capability optional) and adjust it to yours:
```
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ123456
TELEGRAM_CHAT_ID=123456789
```



## Configuration Options

### Stop Loss Settings
- **Stop Loss Percentage**: Threshold for triggering stop loss (default: 20%)
- **Check Interval**: Time between position checks in seconds (default: 60s)
- **Minimum Position Value**: Only monitor positions above this USD value (default: $0.1)
- **Max Slippage**: Maximum acceptable price slippage (default: 5%)

### Monitoring Modes
1. **None**: Bot monitors no positions (default for safety)
2. **Selected**: Monitor only user-selected positions
3. **All**: Monitor every position above minimum threshold

### Execution Modes
- **Dry Run**: Simulate trades without execution (recommended for testing)
- **Live Trading**: Execute actual stop loss orders

## Usage

### Starting the Bot
```bash
python polymarket_stop_loss_hybrid_specificPosition.py
```

### Interactive Menu Options (Menu 1-11)

### Basic Stop Loss Settings
- **Stop Loss Percentage** (Option 2): Threshold for triggering stop loss
- **Check Interval** (Option 3): Time between position checks in seconds
- **Minimum Position Value** (Option 4a): Only monitor positions above this USD value
- **Stop Loss Price Threshold** (Option 4b): Absolute price level to trigger stop loss

### Execution Mode
- **Dry Run Toggle** (Option 5): Switch between simulation and live trading

### Monitoring Configuration
- **Position Selection** (Option 7): Choose specific positions to monitor. Bot displays all available positions and their index.
  a. for several positions - Enter position numbers separated by commas (e.g., "1,3,5")
  b. Enter position numbers separated by commas (e.g., "1,3,5")
  c. Use "all" to select everything
  d. Use "clear" to deselect everything
  e. Use "done" to finish selection
  f. Selections are automatically saved to `selected_positions.json`
- **Monitor All Positions** (Option 8): Switch to monitoring every position
- **Clear Monitoring** (Option 11): Set monitoring mode to none

### Utility Functions
- **Test Connection** (Option 6): View current positions and test API
- **View Configuration** (Option 9): Display current monitoring setup

**At last, when all configurations have been adjusted according to your needs - start monitoring**: Begin continuous monitoring with current settings (Option 1)

### Risk Management

1. **Stop Loss Threshold**: Consider market volatility when setting percentages
2. **Position Size**: Larger positions may have execution challenges
3. **Market Liquidity**: Low liquidity markets may experience higher slippage
4. **Network Congestion**: Polygon network issues can delay executions

## CSV Export Feature

Convert execution logs to CSV format:
```bash
bash convert_stop_loss_to_csv.sh
```

This creates `stop_loss_executions_summary.csv` with:
- Execution timestamps
- Market and outcome details
- Position sizes and values
- P&L calculations
- Order execution details
- Pricing information

## Troubleshooting

### Common Issues

**"No positions found"**
- Verify wallet address in `user.txt` is correct
- Ensure positions exist and are above minimum threshold
- Check network connectivity

**"CLOB client initialization failed"**
- Verify private key in `.env` is correct and complete
- Ensure wallet has USDC balance for gas
- Check Polygon network status

**"Orders failing to execute"**
- Market may have low liquidity
- Try reducing position size
- Adjust slippage tolerance
- Check USDC balance for gas fees

**"Selected positions not found"**
- Positions may have been closed or transferred
- Re-run position selection to update
- Check if position values fell below minimum threshold

### Debug Mode

For detailed debugging, check:
1. `polymarket_stop_loss.log` - General bot activity
2. Console output during execution
3. `stop_loss_executions_*.json` - Detailed execution results

## Limitations

### Technical Limitations
- Requires stable internet connection
- Dependent on Polymarket API availability
- Subject to Polygon network congestion
- Limited by market liquidity

### Market Limitations
- Stop losses may not execute at exact trigger prices
- Low liquidity markets may experience significant slippage
- Rapid market movements may result in larger losses than intended
- No guarantee of order execution during high volatility

### Regulatory Limitations
- US residents cannot use this tool legally
- Users must comply with local financial regulations
- Tool provided as-is without warranty

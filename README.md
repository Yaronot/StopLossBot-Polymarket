# Polymarket Stop Loss Bot

Polymarket currently lacks stop-loss functionality, a fundamental risk management tool standard across virtually all major trading platforms. This critical omission forces users to seek alternative loss mitigation strategies such as hedging, yet these workarounds fail to adequately address numerous scenarios where losses could be minimized. This repository solves this problem by utilizing Polymarket's API infrastructure to deliver automated stop-loss protection.

## Legal Disclaimer

**US RESIDENTS ARE PROHIBITED FROM TRADING ON POLYMARKET.** This tool is intended for educational purposes. Use at your own risk and ensure compliance with your local regulations.
The developer assume no responsibility for trading losses, technical failures, or legal issues arising from use of this software.

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

## Risk Management

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

## Common Issues

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


## Screenshots Of User Interface

<table>
  <tr>
    <td><img src=![Screenshot 2025-08-28 at 0 44 54](https://github.com/user-attachments/assets/76b7b03a-7a98-455e-965b-b8ceb4265cef)
    <td><img src=<img width="730" height="558" alt="צילום מסך 2025-08-28 ב-0 41 39" src="https://github.com/user-attachments/assets/976b4b0b-4c30-4383-a06b-6d863f04247e" />
    <td><img src=<img width="892" height="214" alt="צילום מסך 2025-08-28 ב-0 42 49" src="https://github.com/user-attachments/assets/26ecb802-789d-42f5-9cb7-ee3826a78e54" />
  </tr>
</table>





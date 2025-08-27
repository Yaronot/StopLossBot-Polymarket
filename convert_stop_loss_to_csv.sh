#!/bin/bash

# Stop Loss Executions JSON to CSV Converter
# Finds all stop_loss_executions_*.json files and converts them to CSV

OUTPUT_CSV="stop_loss_executions_summary.csv"
TEMP_FILE="/tmp/stop_loss_temp.txt"

echo "🔍 Searching for stop loss execution JSON files..."

# Find all matching JSON files
JSON_FILES=$(find . -maxdepth 1 -name "stop_loss_executions_*.json" -type f | sort)

if [ -z "$JSON_FILES" ]; then
    echo "❌ No stop loss execution JSON files found in current directory"
    echo "   Looking for pattern: stop_loss_executions_*.json"
    exit 1
fi

echo "📁 Found JSON files:"
echo "$JSON_FILES"

# Create CSV header
echo "Creating CSV header..."
echo "timestamp,market,outcome,size,value,pnl,pnl_percentage,orders_placed,total_size_ordered,remaining_size,order_success,avg_sale_price,min_sale_price,max_sale_price,file_source" > "$OUTPUT_CSV"

# Process each JSON file
for json_file in $JSON_FILES; do
    echo "📊 Processing: $json_file"
    
    # Extract filename for source tracking
    filename=$(basename "$json_file")
    
    # Use Python to parse JSON and extract data
    python3 -c "
import json
import sys
import os

filename = '$filename'
try:
    with open('$json_file', 'r') as f:
        data = json.load(f)
    
    # Handle both list and single object formats
    if isinstance(data, list):
        executions = data
    else:
        executions = [data]
    
    for execution in executions:
        # Extract basic info
        timestamp = execution.get('timestamp', '')
        
        # Extract position info
        position = execution.get('position', {})
        market = position.get('market', '').replace(',', ';')  # Replace commas to avoid CSV issues
        outcome = position.get('outcome', '').replace(',', ';')
        size = position.get('size', 0)
        value = position.get('value', 0)
        pnl = position.get('pnl', 0)
        pnl_percentage = position.get('pnl_percentage', 0)
        
        # Extract order result info
        order_result = execution.get('order_result', {})
        orders_placed = order_result.get('orders_placed', 0)
        total_size_ordered = order_result.get('total_size_ordered', 0)
        remaining_size = order_result.get('remaining_size', 0)
        order_success = order_result.get('success', False)
        
        # Extract pricing information from order details
        avg_sale_price = ''
        min_sale_price = ''
        max_sale_price = ''
        
        try:
            order_details = order_result.get('order_details', [])
            
            # Handle different order result formats
            if order_details and isinstance(order_details, list):
                prices = []
                sizes = []
                
                for order in order_details:
                    # Try to extract price from different possible locations
                    price = None
                    order_size = None
                    
                    # Check if order has direct price field
                    if 'price' in order:
                        price = float(order['price'])
                    
                    # Check if order has result with price
                    elif 'result' in order and isinstance(order['result'], dict):
                        if 'price' in order['result']:
                            price = float(order['result']['price'])
                    
                    # Check if order has size information
                    if 'size' in order:
                        order_size = float(order['size'])
                    elif 'result' in order and 'size' in order['result']:
                        order_size = float(order['result']['size'])
                    
                    if price is not None:
                        prices.append(price)
                        if order_size is not None:
                            sizes.append(order_size)
                
                if prices:
                    # Calculate weighted average if we have sizes, otherwise simple average
                    if len(sizes) == len(prices) and sum(sizes) > 0:
                        avg_sale_price = f'{sum(p * s for p, s in zip(prices, sizes)) / sum(sizes):.6f}'
                    else:
                        avg_sale_price = f'{sum(prices) / len(prices):.6f}'
                    
                    min_sale_price = f'{min(prices):.6f}'
                    max_sale_price = f'{max(prices):.6f}'
            
            # Fallback: try to extract from single result format
            elif 'result' in order_result and isinstance(order_result['result'], dict):
                result = order_result['result']
                if 'price' in result:
                    price = float(result['price'])
                    avg_sale_price = f'{price:.6f}'
                    min_sale_price = f'{price:.6f}'
                    max_sale_price = f'{price:.6f}'
                    
        except Exception as e:
            # If price extraction fails, leave fields empty
            avg_sale_price = 'N/A'
            min_sale_price = 'N/A'
            max_sale_price = 'N/A'
        
        # Print CSV row
        print(f'{timestamp},{market},{outcome},{size},{value},{pnl},{pnl_percentage},{orders_placed},{total_size_ordered},{remaining_size},{order_success},{avg_sale_price},{min_sale_price},{max_sale_price},{filename}')

except Exception as e:
    print(f'Error processing {filename}: {e}', file=sys.stderr)
" >> "$OUTPUT_CSV"

done

# Check if CSV was created successfully
if [ -f "$OUTPUT_CSV" ]; then
    echo "✅ CSV file created successfully: $OUTPUT_CSV"
    
    # Show summary
    total_rows=$(( $(wc -l < "$OUTPUT_CSV") - 1 ))  # Subtract header row
    echo "📊 Summary:"
    echo "   - Total executions: $total_rows"
    echo "   - Output file: $OUTPUT_CSV"
    
    # Show first few lines as preview
    echo ""
    echo "📋 Preview (first 5 rows):"
    head -6 "$OUTPUT_CSV" | column -t -s','
    
    # Show file size
    file_size=$(ls -lh "$OUTPUT_CSV" | awk '{print $5}')
    echo ""
    echo "📁 File size: $file_size"
    
else
    echo "❌ Failed to create CSV file"
    exit 1
fi

echo ""
echo "🎉 Conversion complete! You can now open $OUTPUT_CSV in Excel or any spreadsheet application."

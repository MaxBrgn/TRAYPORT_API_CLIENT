# Trayport Data Analytics API Client

A Python client for the Trayport Data Analytics API, providing programmatic access to European energy trading data including trades, order books, and reference data.

## Overview

This client provides access to:
- **Historical trade data** for energy products (gas, power, coal, oil, etc.)
- **Order book snapshots** (Level 1 and Level 2)
- **OHLCV bars** for technical analysis
- **Reference data** for instruments, markets, and contract sequences
- **Private trade data** (requires appropriate permissions)

## Key Concepts

### Understanding Trayport Data Structure

1. **Instruments**: Products like "TTF Hi Cal 51.6" (gas) or "DE Base" (power)
2. **Markets**: Trading venues like "TTF Screen 3% 38.1"
3. **Sequences**: Contract series (e.g., "Months", "Quarters", "Years")
4. **Sequence Items**: Individual contracts within a sequence (e.g., "Aug-25", "Q3-25")

### Contract Types

- **SinglePeriod**: Standard single delivery period contracts
- **Spread**: Price difference between two contracts (e.g., Aug-25 vs Sep-25)
- **PeriodSpread**: Spread between different period types
- **Range**: Multiple consecutive contracts
- **PeriodRange**: Range across different period types

## Installation

```bash
# Using pip
pip install -r requirements.txt

# Or install from source
git clone https://github.com/yourusername/TP_API_WRAPPER.git
cd TP_API_WRAPPER
pip install -e .
```

## Configuration

Create a `.env` file in your project root:

```bash
# Required
TRAYPORT_API_KEY=your_api_key_here

# Optional (with defaults)
TRAYPORT_BASE_URL_ANALYTICS=https://daapi.trayport.com
TRAYPORT_BASE_URL_REFERENCE=https://daapi.trayport.com/api
TRAYPORT_RATE_LIMIT_PER_SECOND=6    # Conservative: 75% of 8/sec limit
TRAYPORT_RATE_LIMIT_PER_MINUTE=360  # Conservative: 75% of 480/min limit
TRAYPORT_REQUEST_TIMEOUT=30
TRAYPORT_MAX_RETRIES=3
```

## Important Notes

### Data Availability
The Trayport API typically has a delay in data availability:
- **Today's data**: Usually NOT available
- **Yesterday's data**: May or may not be available
- **2+ days ago**: Generally available

Always use dates that are at least 2 days in the past to ensure data availability:

```python
from datetime import datetime, timedelta, timezone

# Good: Request data ending 2 days ago
end_date = datetime.now(timezone.utc) - timedelta(days=2)
start_date = end_date - timedelta(days=30)
```

## Quick Start

### Basic Trade Query

```python
import asyncio
from datetime import datetime, timedelta, timezone
from trayport_client import TrayportClient

async def get_recent_trades():
    # Initialize client
    client = TrayportClient(api_key="your_api_key_here")
    
    # Define date range (max 32 days for trades)
    # Use 2+ days ago to ensure data availability
    end_date = datetime.now(timezone.utc) - timedelta(days=2)
    start_date = end_date - timedelta(days=7)
    
    # Get trades for TTF Aug-25
    trades = await client.trades.get_trades(
        market_id=10000065,        # TTF market
        sequence_id=10000305,      # Months sequence
        sequence_item_id=260,      # Aug-25 contract
        contract_type="SinglePeriod",
        from_=start_date,
        until=end_date
    )
    
    print(f"Found {len(trades)} trades")
    for trade in trades[:5]:
        print(f"Price: {trade.price}, Volume: {trade.quantity}, "
              f"Time: {trade.deal_date}, Venue: {trade.venue_code}")
    
    await client.close()

asyncio.run(get_recent_trades())
```

### Finding Active Contracts

```python
async def find_tradable_contracts():
    client = TrayportClient(api_key="your_api_key_here")
    
    # Get sequence items (contracts) for TTF months
    items = await client.reference.get_sequence_items(
        sequence_id=10000305  # TTF months
    )
    
    # Find contracts that are currently tradable
    now = datetime.utcnow()
    tradable = [
        item for item in items 
        if item.trading_start <= now <= item.trading_end
    ]
    
    print("Currently tradable TTF month contracts:")
    for item in tradable[:12]:  # Next 12 months
        print(f"- {item.name} (ID: {item.id})")
        print(f"  Trading until: {item.trading_end}")
        print(f"  Delivery: {item.period_start} to {item.period_end}")
    
    await client.close()
```

### Spread Trading Data

```python
async def get_spread_trades():
    client = TrayportClient(api_key="your_api_key_here")
    
    # Get spread trades between Aug-25 and Sep-25
    trades = await client.trades.get_trades(
        market_id=10000065,
        sequence_id=10000305,
        sequence_item_id=260,           # Aug-25
        second_sequence_item_id=261,    # Sep-25
        contract_type="Spread",
        from_=datetime(2025, 7, 22),
        until=datetime(2025, 7, 23),
        optional_fields=["Contract", "Route"]  # Include contract details
    )
    
    # Spread trades can have negative prices
    for trade in trades:
        print(f"Spread price: {trade.price} (Aug-Sep)")
```

### OHLCV Data

```python
async def get_ohlcv_bars():
    client = TrayportClient(api_key="your_api_key_here")
    
    # Get 15-minute bars (note: seconds must be 0 for OHLCV)
    bars = await client.trades.get_ohlcv(
        market_id=10000065,
        sequence_id=10000305,
        sequence_item_id=260,
        contract_type="SinglePeriod",
        from_=datetime(2025, 7, 22, 9, 0, 0),   # 09:00:00
        until=datetime(2025, 7, 22, 17, 0, 0),  # 17:00:00
        interval=15,
        interval_unit="minute"
    )
    
    for bar in bars:
        print(f"Time: {bar.from_timestamp}, O: {bar.open}, "
              f"H: {bar.high}, L: {bar.low}, C: {bar.close}, V: {bar.volume}")
```

### Bulk Operations

```python
async def bulk_trade_query():
    client = TrayportClient(api_key="your_api_key_here")
    
    # Query multiple contracts in one request (up to 50)
    trades = await client.trades.get_trades(
        market_id=10000065,
        sequence_id=10000305,
        sequence_item_id="260,261,262",  # Aug, Sep, Oct 2025
        contract_type="SinglePeriod",
        from_=datetime(2025, 7, 22),
        until=datetime(2025, 7, 23)
    )
    
    # Results include trades from all three contracts
    print(f"Total trades from 3 contracts: {len(trades)}")
```

## Important API Limitations

### Date Range Limits

| Endpoint | Maximum Range | Notes |
|----------|--------------|-------|
| Trades | 32 days | Single query limit |
| OHLCV | 92 days | For intervals < 1 day |
| OHLCV | 1827 days (~5 years) | For intervals ≥ 1 day |
| Order Book | 60 days OR 100k points | Whichever is smaller |
| Activity | 7 days | Data from April 10, 2023 onwards |

### Rate Limits

- **8 requests per second**
- **480 requests per minute**

The client enforces conservative limits (75% of actual) to ensure stability.

### Timestamp Requirements

1. **No fractional seconds**: All timestamps must be whole seconds
2. **OHLCV special rule**: Seconds must be 0 (e.g., 09:15:00, not 09:15:30)
3. **UTC timezone**: All times are in UTC

### Data Availability

- **Intraday data**: Not available for current day without Data Analytics Gateway
- **Historical data**: Available from different dates per venue (see docs)
- **Private trades**: Same-day available, historical requires permissions

## Common Patterns

### Finding Contracts by Date

```python
# Find which contract was trading on a specific date
async def find_contract_for_date(client, sequence_id, target_date):
    items = await client.reference.get_sequence_items(sequence_id)
    
    for item in items:
        if (item.trading_start <= target_date <= item.trading_end and
            item.period_start <= target_date <= item.period_end):
            return item
    return None
```

### Handling Optional Fields

```python
# Request specific optional fields for trades
trades = await client.trades.get_trades(
    market_id=10000065,
    sequence_id=10000305,
    sequence_item_id=260,
    contract_type="SinglePeriod",
    from_=start_date,
    until=end_date,
    optional_fields=[
        "AggressorOwnedSpread",
        "FromBrokenSpread",
        "Route",
        "Contract"  # Includes full contract specification
    ]
)
```

### Error Handling

```python
from trayport_client.exceptions import (
    TrayportAPIError,
    TrayportRateLimitError,
    TrayportValidationError
)

try:
    trades = await client.trades.get_trades(...)
except TrayportRateLimitError:
    print("Rate limit hit - client will retry automatically")
except TrayportValidationError as e:
    print(f"Invalid parameters: {e}")
except TrayportAPIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## Advanced Usage

### Working with Order Books

```python
# Level 1 (top of book)
top = await client.orders.get_book_top(
    market_id=10000065,
    sequence_id=10000305,
    sequence_item_id=260,
    contract_type="SinglePeriod",
    at=datetime(2025, 7, 22, 14, 30, 0)
)

# Level 2 (full depth)
book = await client.orders.get_book(
    market_id=10000065,
    sequence_id=10000305,
    sequence_item_id=260,
    contract_type="SinglePeriod",
    at=datetime(2025, 7, 22, 14, 30, 0),
    depth=10  # Top 10 levels each side
)
```

### Private Trade Data

```python
# Requires appropriate permissions
private_trades = await client.trades.get_private_trades(
    market_id=10000065,
    from_=datetime.utcnow() - timedelta(hours=2),
    until=datetime.utcnow()
)

for trade in private_trades:
    print(f"Aggressor: {trade.aggressor_trader_name}")
    print(f"Initiator: {trade.initiator_trader_name}")
```

## Testing

```bash
# Test your connection
python test_connection.py

# Test the models with sample data
python test_models.py
```

## Project Structure

```
trayport_client/
├── client/          # HTTP client, rate limiting, retry logic
├── models/          # Pydantic models for requests/responses
├── endpoints/       # API endpoint implementations
├── exceptions/      # Custom exception types
├── config/          # Configuration and constants
└── utils/           # Utility functions
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Disclaimer

This is an unofficial client library and is not affiliated with or endorsed by Trayport. Use at your own risk and ensure compliance with Trayport's terms of service.
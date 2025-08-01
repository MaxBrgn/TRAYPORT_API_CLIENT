# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python connector for the Trayport Data Analytics API, providing programmatic access to historical energy trading data. The project consists of:
- A high-performance async HTTP client with rate limiting and retry logic
- Strongly-typed data models for all API requests and responses
- Convenience methods for common operations like bulk data fetching
- Comprehensive error handling and monitoring capabilities

## Development Best Practices

- Always run python code in venv
- Always run python in the virtual environment

## Key API Information

### API Endpoints
- **Reference Data API**: `https://referencedata.trayport.com`
  - `/instruments`, `/markets`, `/sequences` - Metadata about tradable contracts
- **Analytics API**: `https://analytics.trayport.com/api`
  - `/trades`, `/trades/ohlcv`, `/trades/last` - Historical trade data
  - `/orders/book`, `/orders/book/top` - Order book snapshots

### Authentication
- Uses API key authentication via `X-API-KEY` header
- API keys are environment-specific and should be stored securely

### Critical Rate Limits
- **Hard limits**: 8 requests/second OR 480 requests/minute
- **Implementation target**: 6 req/sec OR 360 req/min (25% safety buffer)
- Both limits must be respected simultaneously

### Date Range Constraints
- **Trades/Orders**: Maximum 32 days per query
- **OHLCV**: 92 days for intervals <1 day, 1827 days for ≥1 day intervals
- **Order Book**: 60 days OR 100,000 data points (whichever is smaller)
- **Activity**: 7 days maximum, data available from April 10, 2023

## Development Commands

```bash
# Project setup (once pyproject.toml exists)
poetry install

# Run tests
poetry run pytest
poetry run pytest -v  # verbose
poetry run pytest tests/test_client.py::test_specific  # single test

# Code quality
poetry run black .  # format code
poetry run isort .  # sort imports
poetry run mypy .   # type checking
poetry run ruff check .  # linting

# Performance testing
poetry run pytest tests/test_performance.py -v
poetry run py-spy record -o profile.svg -- python scripts/benchmark.py

# Documentation
poetry run mkdocs serve  # local docs server
poetry run mkdocs build  # build docs
```

## High-Level Architecture

### Core Components

1. **HTTP Client Layer** (`client/`)
   - `base.py`: Async httpx wrapper with connection pooling
   - `rate_limiter.py`: Dual-tier token bucket (per-second AND per-minute)
   - `retry.py`: Exponential backoff with jitter
   - `circuit_breaker.py`: Fault tolerance for API failures

2. **Data Models** (`models/`)
   - Request models validate parameters before API calls
   - Response models use Pydantic for type safety and validation
   - High-performance variants with `__slots__` for large datasets

3. **API Endpoints** (`endpoints/`)
   - `reference.py`: Instrument/market/sequence lookups (heavily cached)
   - `trades.py`: Historical trade data with bulk operations
   - `orders.py`: Order book snapshots (single-contract only)

4. **Bulk Operations**
   - Automatic request batching for compatible endpoints
   - Parallel execution for incompatible contract combinations
   - Smart grouping by market/sequence for efficiency

### Request Flow
```
User Request → Validation → Rate Limiter → Circuit Breaker → HTTP Client → API
                                ↓                                           ↓
                          Rate exceeded                              Response/Error
                                ↓                                           ↓
                            Queue/Wait                              Retry Handler
                                                                           ↓
                                                                    Parse & Validate
                                                                           ↓
                                                                      User Response
```

### Multi-Contract Query Optimization

The API has varying support for bulk queries:
- `/trades`, `/snapshots`: Up to 50 contracts via `sequenceItemId` parameter
- `/trades/private`: Unlimited contracts when querying by market
- `/orders/*`: Single contract only - requires parallel requests

The client automatically optimizes queries:
1. Groups contracts by market/sequence where possible
2. Uses bulk endpoints when available
3. Falls back to parallel single-contract queries with rate limiting

## Testing Against Real API

```python
# Basic connectivity test
import os
from trayport_client import TrayportClient

async def test_connection():
    client = TrayportClient(api_key=os.getenv("TRAYPORT_API_KEY"))
    
    # Test reference data (cached, low impact)
    instruments = await client.reference.get_instruments()
    print(f"Found {len(instruments)} instruments")
    
    # Test minimal trade query
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    trades = await client.trades.get_trades(
        market_id=10000123,  # TTF
        sequence_id=10000456,  # Prompt
        sequence_item_id=789,  # DA
        from_=yesterday,
        until=datetime.utcnow(),
        limit=10  # Small limit for testing
    )
```

## Performance Considerations

1. **Reference Data Caching**: Instruments/markets/sequences change rarely - cache aggressively
2. **Connection Pooling**: Maintain persistent HTTP/2 connections for throughput
3. **Memory Management**: Use streaming for large datasets (>100MB)
4. **Bulk Operations**: Always prefer bulk endpoints over multiple single requests
5. **Compression**: API defaults to Brotli - ensure client supports it

## Common Pitfalls

1. **Rate Limiting**: Both per-second AND per-minute limits apply simultaneously
2. **Date Validation**: Each endpoint has different maximum date ranges
3. **Contract Specification**: Use `marketId` OR `instrumentId`, never both
4. **Order Book Queries**: Cannot batch multiple contracts - plan accordingly
5. **Timezone Handling**: API uses UTC exclusively - convert local times

## Implementation Status

See `trayport_connector_plan.md` for detailed implementation tasks. The project follows this structure but implementation is in early stages. Key files to reference:
- `Introduction_to_Data_Analytics.ipynb`: Example API usage patterns
- `trayport_connector_plan.md`: Comprehensive implementation roadmap
- `Data_Analytics_API.pdf`: Official API documentation (if available)
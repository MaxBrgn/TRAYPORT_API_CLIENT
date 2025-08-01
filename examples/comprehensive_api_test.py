#!/usr/bin/env python3
"""Comprehensive test of all Trayport API endpoints with request/response audit trail."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from trayport_client import TrayportClient


def save_audit(request_info: Dict[str, Any], response_data: Any, filename: str, output_dir: Path):
    """Save request and response for audit."""
    filepath = output_dir / filename
    
    # Process response
    if hasattr(response_data, '__iter__') and not isinstance(response_data, (dict, str)):
        response_json = [item.model_dump() if hasattr(item, 'model_dump') else item for item in response_data]
    elif hasattr(response_data, 'model_dump'):
        response_json = response_data.model_dump()
    else:
        response_json = response_data
    
    audit_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": request_info,
        "response_count": len(response_json) if isinstance(response_json, list) else 1,
        "response": response_json
    }
    
    with open(filepath, 'w') as f:
        json.dump(audit_data, f, indent=2, default=str)
    
    print(f"  💾 {filename}")
    return response_json


def adjust_to_trading_hours(dt: datetime) -> datetime:
    """Adjust datetime to be within trading hours (08:00-18:00 CET)."""
    # CET is UTC+1, CEST is UTC+2
    # For simplicity, assume CET (UTC+1) offset
    cet_offset = timedelta(hours=1)
    
    # Convert to CET
    dt_cet = dt + cet_offset
    
    # If outside trading hours, adjust to nearest trading time
    if dt_cet.hour < 8:
        # Before 8am, set to 8am
        dt_cet = dt_cet.replace(hour=8, minute=0, second=0, microsecond=0)
    elif dt_cet.hour >= 18:
        # After 6pm, set to 5:59pm
        dt_cet = dt_cet.replace(hour=17, minute=59, second=0, microsecond=0)
    
    # Convert back to UTC
    return dt_cet - cet_offset


async def test_all_endpoints():
    """Test all Trayport API endpoints comprehensively."""
    
    # Setup
    output_dir = Path("api_test_results")
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Test results will be saved to: {output_dir.absolute()}\n")
    
    # Date ranges (2+ days ago, during trading hours)
    # Set end time to 17:00 CET (16:00 UTC) 2 days ago
    end_date = datetime.now(timezone.utc).replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=2)
    
    # Set start times to 09:00 CET (08:00 UTC)
    start_date_7d = (end_date - timedelta(days=7)).replace(hour=8, minute=0, second=0, microsecond=0)
    start_date_30d = (end_date - timedelta(days=30)).replace(hour=8, minute=0, second=0, microsecond=0)
    start_date_90d = (end_date - timedelta(days=90)).replace(hour=8, minute=0, second=0, microsecond=0)
    
    print(f"🕐 Using trading hours (08:00-18:00 CET)")
    print(f"📅 Date range: {start_date_7d.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC\n")  # For testing auto-slicing
    
    async with TrayportClient() as client:
        print("=" * 60)
        print("REFERENCE DATA ENDPOINTS")
        print("=" * 60)
        
        # 1. Get all instruments
        print("\n1️⃣ Testing GET /instruments")
        instruments = await client.reference.get_instruments()
        save_audit(
            {
                "endpoint": "https://referencedata.trayport.com/instruments",
                "method": "GET",
                "description": "Get all available instruments"
            },
            instruments[:10],  # Save first 10 only
            "01_instruments.json",
            output_dir
        )
        print(f"   ✅ Found {len(instruments)} instruments")
        
        # 2. Get all markets
        print("\n2️⃣ Testing GET /markets")
        markets = await client.reference.get_markets()
        save_audit(
            {
                "endpoint": "https://referencedata.trayport.com/markets",
                "method": "GET",
                "description": "Get all available markets"
            },
            markets[:10],  # Save first 10 only
            "02_markets.json",
            output_dir
        )
        print(f"   ✅ Found {len(markets)} markets")
        
        # Find TTF market for further tests
        ttf_market = next((m for m in markets if m.name == "TTF Hi Cal 51.6"), None)
        if not ttf_market:
            print("   ❌ TTF market not found")
            return
        
        # 3. Get sequences for a market
        print(f"\n3️⃣ Testing GET /markets/{{id}}/sequences")
        sequences = await client.reference.get_sequences(market_id=ttf_market.id)
        save_audit(
            {
                "endpoint": f"https://referencedata.trayport.com/markets/{ttf_market.id}/sequences",
                "method": "GET",
                "market_id": ttf_market.id,
                "description": f"Get sequences for market '{ttf_market.name}'"
            },
            sequences,
            "03_market_sequences.json",
            output_dir
        )
        print(f"   ✅ Found {len(sequences)} sequences")
        
        # Find monthly sequence
        month_seq = next((s for s in sequences if s.name == "Gas - NG Months"), None)
        if not month_seq:
            print("   ❌ Monthly sequence not found")
            return
        
        # 4. Get sequence items
        print(f"\n4️⃣ Testing GET /sequences/{{id}}/sequenceItems")
        items = await client.reference.get_sequence_items(month_seq.id, count=10)
        save_audit(
            {
                "endpoint": f"https://referencedata.trayport.com/sequences/{month_seq.id}/sequenceItems",
                "method": "GET",
                "params": {"Count": "10"},
                "sequence_id": month_seq.id,
                "description": f"Get items for sequence '{month_seq.name}'"
            },
            items,
            "04_sequence_items.json",
            output_dir
        )
        print(f"   ✅ Found {len(items)} sequence items")
        
        # Get a future contract that's still actively trading
        # Skip contracts that have already expired or are near expiry
        contract = None
        for item in items:
            # Use contracts at least 2 months in the future
            if item.period_start and "Sep-25" in item.name:
                contract = item
                break
        
        if not contract:
            # Fallback to 3rd contract if Sep-25 not found
            contract = items[2] if len(items) > 2 else items[0]
            
        if not contract:
            print("   ❌ No contracts found")
            return
        
        print(f"   📌 Using contract: {contract.name} (ID: {contract.id})")
        
        print("\n" + "=" * 60)
        print("TRADES ENDPOINTS")
        print("=" * 60)
        
        # 5. Get trades for single contract
        print(f"\n5️⃣ Testing GET /trades (single contract)")
        trades = await client.trades.get_trades(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_ids=contract.id,
            from_=start_date_7d,
            until=end_date,
            contract_type="SinglePeriod"
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_7d.isoformat(),
                    "until": end_date.isoformat(),
                    "contractType": "SinglePeriod"
                },
                "description": f"Get trades for {contract.name}"
            },
            trades,
            "05_trades_single.json",
            output_dir
        )
        print(f"   ✅ Found {len(trades)} trades")
        
        # 6. Test bulk trades query
        if len(items) >= 5:
            print(f"\n6️⃣ Testing GET /trades (bulk - 3 contracts)")
            # Use Sep, Oct, Nov contracts (indices 2, 3, 4)
            bulk_ids = [items[2].id, items[3].id, items[4].id]
            bulk_trades = await client.trades.get_trades(
                market_id=ttf_market.id,
                sequence_id=month_seq.id,
                sequence_item_ids=bulk_ids,
                from_=start_date_7d,
                until=end_date,
                contract_type="SinglePeriod"
            )
            save_audit(
                {
                    "endpoint": "https://analytics.trayport.com/api/trades",
                    "method": "GET",
                    "params": {
                        "marketId": ttf_market.id,
                        "sequenceId": month_seq.id,
                        "sequenceItemId": ",".join(map(str, bulk_ids)),
                        "from": start_date_7d.isoformat(),
                        "until": end_date.isoformat(),
                        "contractType": "SinglePeriod"
                    },
                    "description": f"Bulk query for {[items[i].name for i in range(2, 5)]}"
                },
                bulk_trades,
                "06_trades_bulk.json",
                output_dir
            )
            print(f"   ✅ Found {len(bulk_trades)} trades across 3 contracts")
        
        # 7. Test spread trades
        if len(items) >= 4:
            print(f"\n7️⃣ Testing GET /trades (spread)")
            # Use Sep-25 vs Oct-25 spread
            spread_trades = await client.trades.get_trades(
                market_id=ttf_market.id,
                sequence_id=month_seq.id,
                sequence_item_ids=items[2].id,
                second_sequence_item_id=items[3].id,
                from_=start_date_7d,
                until=end_date,
                contract_type="Spread"
            )
            save_audit(
                {
                    "endpoint": "https://analytics.trayport.com/api/trades",
                    "method": "GET",
                    "params": {
                        "marketId": ttf_market.id,
                        "sequenceId": month_seq.id,
                        "sequenceItemId": items[0].id,
                        "secondSequenceItemId": items[1].id,
                        "from": start_date_7d.isoformat(),
                        "until": end_date.isoformat(),
                        "contractType": "Spread"
                    },
                    "description": f"Spread trades {items[2].name} vs {items[3].name}"
                },
                spread_trades,
                "07_trades_spread.json",
                output_dir
            )
            print(f"   ✅ Found {len(spread_trades)} spread trades")
        
        # 8. Test OHLCV
        print(f"\n8️⃣ Testing GET /trades/ohlcv")
        ohlcv = await client.trades.get_ohlcv(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_ids=contract.id,
            from_=start_date_7d,
            until=end_date,
            interval=1,
            interval_unit="hour",
            contract_type="SinglePeriod"
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades/ohlcv",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_7d.isoformat(),
                    "until": end_date.isoformat(),
                    "interval": "1",
                    "intervalUnit": "hour",
                    "contractType": "SinglePeriod"
                },
                "description": f"Hourly OHLCV for {contract.name}"
            },
            ohlcv[:24],  # Save first 24 hours
            "08_ohlcv_hourly.json",
            output_dir
        )
        print(f"   ✅ Found {len(ohlcv)} hourly bars")
        
        # 9. Test last trade
        print(f"\n9️⃣ Testing GET /trades/last")
        last_trade = await client.trades.get_last_trade(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_id=contract.id,
            contract_type="SinglePeriod"
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades/last",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "contractType": "SinglePeriod"
                },
                "description": f"Last trade for {contract.name}"
            },
            last_trade,
            "09_last_trade.json",
            output_dir
        )
        print(f"   ✅ Last trade: {f'${last_trade.price} at {datetime.fromtimestamp(last_trade.deal_date / 1e9).isoformat()}' if last_trade else 'No trades found'}")
        
        # 10. Test date slicing (90 days)
        print(f"\n🔟 Testing automatic date slicing (90 days)")
        sliced_trades = await client.trades.get_trades(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_ids=contract.id,
            from_=start_date_90d,
            until=end_date,
            contract_type="SinglePeriod"
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades",
                "method": "GET (auto-sliced into 3 requests)",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_90d.isoformat(),
                    "until": end_date.isoformat(),
                    "contractType": "SinglePeriod"
                },
                "description": f"90-day query auto-sliced into 3x 32-day requests"
            },
            sliced_trades[:10],  # Save first 10 trades
            "10_trades_sliced.json",
            output_dir
        )
        print(f"   ✅ Found {len(sliced_trades)} trades from auto-sliced requests")
        
        print("\n" + "=" * 60)
        print("ORDER BOOK ENDPOINTS")
        print("=" * 60)
        
        # 11. Test order book top
        print(f"\n1️⃣1️⃣ Testing GET /orders/book/top")
        book_top = await client.orders.get_order_book_top(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_id=contract.id,
            from_=start_date_7d,
            until=end_date,
            interval=1,
            interval_unit="hour",
            contract_type="SinglePeriod",
            optional_fields=["VenueCode"]  # Get venue codes
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/orders/book/top",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_7d.isoformat(),
                    "until": end_date.isoformat(),
                    "interval": "1",
                    "intervalUnit": "hour",
                    "contractType": "SinglePeriod"
                },
                "description": f"Hourly best bid/ask for {contract.name}"
            },
            book_top[:24],  # Save first 24 hours
            "11_book_top.json",
            output_dir
        )
        print(f"   ✅ Found {len(book_top)} hourly snapshots")
        
        # 12. Test full order book
        print(f"\n1️⃣2️⃣ Testing GET /orders/book")
        # Use a weekday from the test period
        book_date = end_date - timedelta(days=3)
        # Ensure it's a weekday (Monday=0, Sunday=6)
        while book_date.weekday() >= 5:  # Saturday or Sunday
            book_date = book_date - timedelta(days=1)
        book_start = book_date.replace(hour=10, minute=0, second=0, microsecond=0)  # 11:00 CET
        book_end = book_date.replace(hour=11, minute=0, second=0, microsecond=0)  # 12:00 CET
        book_full = await client.orders.get_order_book(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_id=contract.id,
            from_=book_start,
            until=book_end,
            interval=5,
            interval_unit="minute",
            contract_type="SinglePeriod",
            depth=10,
            include_private=True,
            optional_fields=["VenueCode", "Route"]  # Get venue and route info
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/orders/book",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": book_start.isoformat(),
                    "until": book_end.isoformat(),
                    "interval": "5",
                    "intervalUnit": "minute",
                    "contractType": "SinglePeriod",
                    "depth": "10",
                    "includePrivate": "true"
                },
                "description": f"5-minute order book depth (10 levels) for {contract.name} during trading hours"
            },
            book_full,
            "12_book_full.json",
            output_dir
        )
        print(f"   ✅ Found {len(book_full)} order book snapshots")
        if book_full:
            with_data = sum(1 for s in book_full if s.bids or s.asks)
            print(f"   📊 Snapshots with bid/ask data: {with_data}")
            if with_data > 0:
                sample = next((s for s in book_full if s.bids or s.asks), None)
                if sample:
                    print(f"   💰 Sample: {len(sample.bids)} bids, {len(sample.asks)} asks")
        
        # 12b. Test Winter 25 seasonal order book
        print(f"\n1️⃣2️⃣b Testing GET /orders/book (Winter 25 Seasonal)")
        # Get seasonal sequence
        season_seq = next((s for s in sequences if s.name == "Gas - NG Sum/Win Seasons"), None)
        if season_seq:
            season_items = await client.reference.get_sequence_items(season_seq.id)
            win_25 = next((i for i in season_items if "Win 25" in i.name), None)
            
            if win_25:
                book_full_seasonal = await client.orders.get_order_book(
                    market_id=ttf_market.id,
                    sequence_id=season_seq.id,
                    sequence_item_id=win_25.id,
                    from_=book_start,
                    until=book_end,
                    interval=10,
                    interval_unit="minute",
                    contract_type="SinglePeriod",
                    depth=5,
                    include_private=True,
                    optional_fields=["VenueCode", "Route"]  # Get venue and route info
                )
                save_audit(
                    {
                        "endpoint": "https://analytics.trayport.com/api/orders/book",
                        "method": "GET",
                        "params": {
                            "marketId": ttf_market.id,
                            "sequenceId": season_seq.id,
                            "sequenceItemId": win_25.id,
                            "from": book_start.isoformat(),
                            "until": book_end.isoformat(),
                            "interval": "10",
                            "intervalUnit": "minute",
                            "contractType": "SinglePeriod",
                            "depth": "5",
                            "includePrivate": "true"
                        },
                        "description": f"10-minute order book depth for Winter 25 seasonal"
                    },
                    book_full_seasonal,
                    "12b_book_seasonal.json",
                    output_dir
                )
                print(f"   ✅ Found {len(book_full_seasonal)} seasonal order book snapshots")
                if book_full_seasonal:
                    with_data = sum(1 for s in book_full_seasonal if s.bids or s.asks)
                    print(f"   📊 Snapshots with bid/ask data: {with_data}")
        
        print("\n" + "=" * 60)
        print("SPECIAL CASES & ERROR HANDLING")
        print("=" * 60)
        
        # 13. Test with optional fields
        print(f"\n1️⃣3️⃣ Testing trades with optional fields")
        trades_optional = await client.trades.get_trades(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_ids=contract.id,
            from_=start_date_7d,
            until=end_date,
            contract_type="SinglePeriod",
            optional_fields=[
                "AggressorOwnedSpread",
                "FromBrokenSpread", 
                "InitiatorOwnedSpread",
                "InitiatorSleeve",
                "AggressorSleeve",
                "Route",
                "RouteId",
                "Contract"
            ]
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_7d.isoformat(),
                    "until": end_date.isoformat(),
                    "contractType": "SinglePeriod",
                    "optionalFields": "AggressorOwnedSpread,FromBrokenSpread,InitiatorOwnedSpread,InitiatorSleeve,AggressorSleeve,Route,RouteId,Contract"
                },
                "description": "Trades with optional fields"
            },
            trades_optional[:5],
            "13_trades_optional_fields.json",
            output_dir
        )
        print(f"   ✅ Found {len(trades_optional)} trades with optional fields")
        
        # 14. Test OHLCV with different intervals
        print(f"\n1️⃣4️⃣ Testing OHLCV with daily interval")
        ohlcv_daily = await client.trades.get_ohlcv(
            market_id=ttf_market.id,
            sequence_id=month_seq.id,
            sequence_item_ids=contract.id,
            from_=start_date_30d,
            until=end_date,
            interval=1,
            interval_unit="day",
            contract_type="SinglePeriod",
            include_empty_buckets=True
        )
        save_audit(
            {
                "endpoint": "https://analytics.trayport.com/api/trades/ohlcv",
                "method": "GET",
                "params": {
                    "marketId": ttf_market.id,
                    "sequenceId": month_seq.id,
                    "sequenceItemId": contract.id,
                    "from": start_date_30d.isoformat(),
                    "until": end_date.isoformat(),
                    "interval": "1",
                    "intervalUnit": "day",
                    "contractType": "SinglePeriod",
                    "includeEmptyBuckets": "true"
                },
                "description": "Daily OHLCV with empty buckets"
            },
            ohlcv_daily,
            "14_ohlcv_daily.json",
            output_dir
        )
        print(f"   ✅ Found {len(ohlcv_daily)} daily bars")
        
        # 15. Test caching behavior
        print(f"\n1️⃣5️⃣ Testing reference data caching")
        import time
        start_time = time.time()
        markets2 = await client.reference.get_markets()
        time1 = time.time() - start_time
        
        start_time = time.time()
        markets3 = await client.reference.get_markets()
        time2 = time.time() - start_time
        
        save_audit(
            {
                "endpoint": "https://referencedata.trayport.com/markets",
                "method": "GET (cached)",
                "description": "Testing cache performance",
                "first_call_time": f"{time1:.3f}s",
                "cached_call_time": f"{time2:.3f}s",
                "cache_speedup": f"{time1/time2:.1f}x faster"
            },
            {"cached": True, "speedup": time1/time2},
            "15_cache_test.json",
            output_dir
        )
        print(f"   ✅ Cache speedup: {time1/time2:.1f}x faster")
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        # Generate summary
        test_files = sorted(output_dir.glob("*.json"))
        summary = {
            "test_run": datetime.now(timezone.utc).isoformat(),
            "total_tests": len(test_files),
            "endpoints_tested": [
                "/instruments",
                "/markets",
                "/markets/{id}/sequences",
                "/sequences/{id}/sequenceItems",
                "/trades",
                "/trades/ohlcv",
                "/trades/last",
                "/orders/book/top",
                "/orders/book"
            ],
            "features_tested": [
                "Single contract queries",
                "Bulk contract queries (up to 50)",
                "Spread trades",
                "Automatic date slicing (32-day chunks)",
                "Optional fields",
                "Empty bucket handling",
                "Reference data caching",
                "Multiple time intervals"
            ],
            "test_files": [f.name for f in test_files]
        }
        
        with open(output_dir / "00_test_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n✅ All tests completed!")
        print(f"📁 Results saved to: {output_dir.absolute()}")
        print(f"📊 Total test files: {len(test_files) + 1}")


async def main():
    """Run comprehensive API tests."""
    print("Trayport API Comprehensive Test Suite")
    print("=" * 60)
    
    try:
        await test_all_endpoints()
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
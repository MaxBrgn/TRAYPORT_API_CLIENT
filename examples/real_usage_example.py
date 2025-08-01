#!/usr/bin/env python3
"""
Real-world usage example for the Trayport API client.
This shows how to fetch actual trading data for research purposes.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
from dotenv import load_dotenv

from trayport_client import TrayportClient
from trayport_client.models import Market, Sequence, SequenceItem, Trade

# Load environment variables
load_dotenv()


async def find_ttf_market(client: TrayportClient) -> Optional[Market]:
    """Find the TTF Hi Cal 51.6 market."""
    markets = await client.reference.get_markets()
    for market in markets:
        if market.name == "TTF Hi Cal 51.6":
            return market
    return None


async def find_month_sequence(client: TrayportClient, market: Market) -> Optional[Sequence]:
    """Find a monthly sequence for the given market."""
    sequences = await client.reference.get_sequences(market_id=market.id)
    for seq in sequences:
        if "month" in seq.name.lower():
            return seq
    return None


async def get_current_month_contract(client: TrayportClient, sequence: Sequence) -> Optional[SequenceItem]:
    """Get the current front month contract."""
    # Get the next few months
    items = await client.reference.get_sequence_items(sequence.id, count=5)
    
    if not items:
        return None
    
    # Find the first contract that hasn't expired
    now = datetime.now(timezone.utc)
    for item in items:
        if item.trading_end > now:
            return item
    
    return items[0] if items else None


async def analyze_ttf_trading():
    """Analyze recent TTF trading activity."""
    
    async with TrayportClient() as client:
        print("🔍 Finding TTF market...")
        ttf_market = await find_ttf_market(client)
        if not ttf_market:
            print("❌ TTF market not found")
            return
        
        print(f"✅ Found market: {ttf_market.name} (ID: {ttf_market.id})")
        
        # Get sequences
        print("\n🔍 Finding monthly contracts...")
        month_sequence = await find_month_sequence(client, ttf_market)
        if not month_sequence:
            print("❌ No monthly sequence found")
            return
        
        print(f"✅ Found sequence: {month_sequence.name} (ID: {month_sequence.id})")
        
        # Get current month contract
        current_month = await get_current_month_contract(client, month_sequence)
        if not current_month:
            print("❌ No current month contract found")
            return
        
        print(f"✅ Current month: {current_month.name} (ID: {current_month.id})")
        print(f"   Trading period: {current_month.trading_start.date()} to {current_month.trading_end.date()}")
        
        # Analyze last 7 days of trading
        print("\n📊 Analyzing last 7 days of trading...")
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        # Get trades
        print(f"📅 Fetching trades from {start_date.date()} to {end_date.date()}...")
        trades = await client.trades.get_trades(
            market_id=ttf_market.id,
            sequence_id=month_sequence.id,
            sequence_item_ids=current_month.id,
            from_=start_date,
            until=end_date,
            contract_type="SinglePeriod"
        )
        
        print(f"✅ Found {len(trades)} trades")
        
        if trades:
            # Convert to DataFrame for analysis
            df = pd.DataFrame([t.dict() for t in trades])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Basic statistics
            print("\n📈 Trade Statistics:")
            print(f"   Total volume: {df['volume'].sum():,.0f}")
            print(f"   Average price: {df['price'].mean():.2f}")
            print(f"   Price range: {df['price'].min():.2f} - {df['price'].max():.2f}")
            print(f"   Trades per day: {len(df) / 7:.1f}")
            
            # Daily summary
            daily = df.resample('D').agg({
                'price': ['mean', 'min', 'max'],
                'volume': 'sum',
                'trade_id': 'count'
            })
            daily.columns = ['avg_price', 'min_price', 'max_price', 'volume', 'trade_count']
            
            print("\n📅 Daily Summary:")
            print(daily)
        
        # Get OHLCV data
        print("\n📊 Fetching hourly OHLCV data...")
        ohlcv = await client.trades.get_ohlcv(
            market_id=ttf_market.id,
            sequence_id=month_sequence.id,
            sequence_item_id=current_month.id,
            from_=start_date,
            until=end_date,
            interval=1,
            interval_unit="hour",
            contract_type="SinglePeriod"
        )
        
        print(f"✅ Found {len(ohlcv)} hourly bars")
        
        if ohlcv:
            # Convert to DataFrame
            ohlcv_df = pd.DataFrame([bar.dict() for bar in ohlcv])
            ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['timestamp'])
            ohlcv_df.set_index('timestamp', inplace=True)
            
            # Find most volatile hours
            ohlcv_df['range'] = ohlcv_df['high'] - ohlcv_df['low']
            ohlcv_df['range_pct'] = (ohlcv_df['range'] / ohlcv_df['open']) * 100
            
            print("\n🌊 Most volatile hours (by price range %):")
            volatile_hours = ohlcv_df.nlargest(5, 'range_pct')[['open', 'high', 'low', 'close', 'volume', 'range_pct']]
            print(volatile_hours)
        
        # Test bulk contract query
        print("\n🔄 Testing bulk contract query...")
        # Get next 3 months
        next_months = await client.reference.get_sequence_items(month_sequence.id, count=3)
        if len(next_months) >= 3:
            contract_ids = [item.id for item in next_months[:3]]
            print(f"📅 Fetching trades for contracts: {[item.name for item in next_months[:3]]}")
            
            bulk_trades = await client.trades.get_trades(
                market_id=ttf_market.id,
                sequence_id=month_sequence.id,
                sequence_item_ids=contract_ids,  # Pass list of IDs
                from_=start_date,
                until=end_date,
                contract_type="SinglePeriod"
            )
            
            print(f"✅ Found {len(bulk_trades)} trades across {len(contract_ids)} contracts")


async def main():
    """Run the analysis."""
    try:
        await analyze_ttf_trading()
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
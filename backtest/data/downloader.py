import os
import time
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

INTERVAL_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def date_to_ms(date_str: str) -> int:
    """Convert YYYY-MM-DD string or ISO timestamp to millisecond epoch."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def download_binance_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    start_date: str = "2023-01-01",
    end_date: str = "2024-01-01",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Downloads historical OHLCV data from Binance Public REST API.
    Handles pagination automatically (1000 bars per call).
    Caches results to disk for zero-latency re-runs.
    """
    parquet_file = CACHE_DIR / f"{symbol}_{interval}_{start_date}_{end_date}.parquet"
    csv_file = CACHE_DIR / f"{symbol}_{interval}_{start_date}_{end_date}.csv"

    if use_cache:
        if parquet_file.exists():
            print(f"📦 Loading cached data from: {parquet_file.name}")
            return pd.read_parquet(parquet_file)
        elif csv_file.exists():
            print(f"📦 Loading cached data from: {csv_file.name}")
            df = pd.read_csv(csv_file)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df

    start_ms = date_to_ms(start_date)
    end_ms = date_to_ms(end_date)
    interval_delta = INTERVAL_MS.get(interval, 60 * 60 * 1000)

    print(f"🌐 Fetching {symbol} ({interval}) from Binance [{start_date} -> {end_date}]...")
    all_data = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": current_start,
            "endTime": end_ms,
            "limit": 1000
        }
        try:
            resp = requests.get(BINANCE_KLINES_URL, params=params, timeout=15)
            if resp.status_code != 200:
                print(f"❌ Binance API Error {resp.status_code}: {resp.text}")
                break
            klines = resp.json()
            if not klines:
                break

            all_data.extend(klines)
            last_open_time = klines[-1][0]
            current_start = last_open_time + interval_delta

            print(f"  Downloaded {len(all_data)} bars (up to {datetime.fromtimestamp(last_open_time/1000).strftime('%Y-%m-%d %H:%M')})...", end="\r")
            time.sleep(0.1)  # rate limit safety
        except Exception as e:
            print(f"\n❌ Network error while downloading: {e}")
            break

    print(f"\n✅ Total bars downloaded: {len(all_data)}")
    if not all_data:
        raise ValueError(f"No data returned for {symbol} {interval} between {start_date} and {end_date}")

    # Binance Kline format:
    # 0: Open time, 1: Open, 2: High, 3: Low, 4: Close, 5: Volume,
    # 6: Close time, 7: Quote asset volume, 8: Number of trades,
    # 9: Taker buy base asset volume, 10: Taker buy quote asset volume, 11: Ignore
    cols = [
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ]
    df = pd.DataFrame(all_data, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)

    df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
    df.drop_duplicates(subset=["timestamp"], inplace=True)
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Save cache
    try:
        df.to_parquet(parquet_file)
        print(f"💾 Cached {len(df)} bars to {parquet_file.name}")
    except Exception:
        # Fallback to CSV if pyarrow/parquet engine not present
        df.to_csv(csv_file, index=False)
        print(f"💾 Cached {len(df)} bars to {csv_file.name}")

    return df

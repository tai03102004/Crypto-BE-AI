import pandas as pd
from typing import Tuple, Dict, Optional, Any
from .downloader import download_binance_klines


class DataLoader:
    """
    Manages historical data loading, integrity auditing, and splitting into:
    - Train (In-Sample research)
    - Validation (Parameter sanity & walk-forward checks)
    - Out-Of-Sample (OOS / Final holdout evaluation)
    """

    FREQ_MAP = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1D"
    }

    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1h"):
        self.symbol = symbol
        self.interval = interval
        self.df: Optional[pd.DataFrame] = None
        self.audit_report: Dict[str, Any] = {}

    def load(
        self,
        start_date: str = "2022-01-01",
        end_date: str = "2026-01-01",
        use_cache: bool = True,
        fill_missing: bool = True
    ) -> pd.DataFrame:
        raw_df = download_binance_klines(
            symbol=self.symbol,
            interval=self.interval,
            start_date=start_date,
            end_date=end_date,
            use_cache=use_cache
        )
        self.df = self._audit_and_clean(raw_df, fill_missing=fill_missing)
        return self.df

    def _audit_and_clean(self, df: pd.DataFrame, fill_missing: bool = True) -> pd.DataFrame:
        """
        Audits data for duplicate timestamps and missing exchange candles (e.g. maintenance downtime).
        If fill_missing is True, forward-fills gaps with volume=0.
        """
        initial_len = len(df)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        duplicates_removed = initial_len - len(df)

        freq = self.FREQ_MAP.get(self.interval, "1h")
        df_indexed = df.set_index("timestamp")

        # Full expected index
        full_index = pd.date_range(start=df["timestamp"].iloc[0], end=df["timestamp"].iloc[-1], freq=freq)
        missing_count = len(full_index) - len(df_indexed)

        self.audit_report = {
            "initial_bars": initial_len,
            "duplicates_removed": duplicates_removed,
            "missing_bars_found": missing_count,
            "missing_pct": (missing_count / len(full_index)) * 100 if len(full_index) > 0 else 0.0,
            "filled": fill_missing and missing_count > 0
        }

        if missing_count > 0:
            print(f"  🔍 Data Audit: Detected {missing_count} missing bars ({self.audit_report['missing_pct']:.3f}%).")
            if fill_missing:
                # Reindex to continuous timeline
                df_reindexed = df_indexed.reindex(full_index)
                # Forward fill price data
                df_reindexed["close"] = df_reindexed["close"].ffill()
                df_reindexed["open"] = df_reindexed["open"].fillna(df_reindexed["close"])
                df_reindexed["high"] = df_reindexed["high"].fillna(df_reindexed["close"])
                df_reindexed["low"] = df_reindexed["low"].fillna(df_reindexed["close"])
                df_reindexed["volume"] = df_reindexed["volume"].fillna(0.0)
                clean_df = df_reindexed.reset_index().rename(columns={"index": "timestamp"})
                print(f"  ✅ Repaired: Forward-filled {missing_count} gaps (volume=0) for continuous frequency.")
                return clean_df

        return df

    def split_regimes(
        self,
        train_end: str = "2024-01-01",
        val_end: str = "2025-01-01"
    ) -> Dict[str, pd.DataFrame]:
        """
        Splits dataset into:
          - 'train': start -> train_end (e.g. 2022-2023)
          - 'val':   train_end -> val_end (e.g. 2024)
          - 'oos':   val_end -> end (e.g. 2025+)
        """
        if self.df is None:
            raise ValueError("Data not loaded yet. Call load() first.")

        train_mask = self.df["timestamp"] < pd.to_datetime(train_end)
        val_mask = (self.df["timestamp"] >= pd.to_datetime(train_end)) & (
            self.df["timestamp"] < pd.to_datetime(val_end)
        )
        oos_mask = self.df["timestamp"] >= pd.to_datetime(val_end)

        return {
            "train": self.df[train_mask].copy().reset_index(drop=True),
            "val": self.df[val_mask].copy().reset_index(drop=True),
            "oos": self.df[oos_mask].copy().reset_index(drop=True),
            "all": self.df.copy().reset_index(drop=True)
        }

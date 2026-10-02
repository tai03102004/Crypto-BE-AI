import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor

data_dir = Path(__file__).parent.parent / "data"
dev = pd.read_csv(data_dir / "breakouts_dev_2022_2023.csv")
val = pd.read_csv(data_dir / "breakouts_val_2024.csv")

features = [
    "channel_width_pct", "channel_width_change", "breakout_magnitude_pct",
    "breakout_close_position", "dist_to_ema200_pct", "ema50_slope_5",
    "natr", "atr_expansion", "vol_ratio", "breakout_volume_zscore",
    "asset_ret_24h", "asset_ret_7d", "btc_ret_24h", "btc_natr"
]

tree = DecisionTreeRegressor(max_depth=2, min_samples_leaf=15, random_state=42)
tree.fit(dev[features].values, dev["target_realized_r"].values)
val["leaf"] = tree.apply(val[features].values)

node2 = val[val["leaf"] == 2]
print("=" * 80)
print("  CHECK A: OUTLIER SENSITIVITY IN NODE #2 (Val 2024)")
print("=" * 80)
for idx, r in node2.iterrows():
    print(f"Trade: {r['trade_id']:<14} Asset: {r['asset']:<8} Time: {r['entry_time']} | R = {r['target_realized_r']:>+7.3f}R | PnL = ${r['net_pnl']:>+7.2f} | BTC_NATR = {r['btc_natr']:.3f} | BTC_RET = {r['btc_ret_24h']:>+6.2f}%")

sorted_r = node2["target_realized_r"].sort_values().values
print(f"\nTotal trades in Node #2: {len(node2)}")
print(f"Realized R values: {sorted_r}")
print(f"Mean Realized R:          {sorted_r.mean():+.3f}R")
print(f"Mean R without Top 1:     {sorted_r[:-1].mean():+.3f}R")
print(f"Median Realized R:        {np.median(sorted_r):+.3f}R")
print(f"Total PnL:                ${node2['net_pnl'].sum():+.2f}")
print(f"Total PnL without Top 1:  ${node2['net_pnl'].iloc[:-1].sum():+.2f}")

print("\n" + "=" * 80)
print("  CHECK B: EXACT FEATURE SELECTION & VARIANCE REDUCTION ON DEV")
print("=" * 80)
for f, imp in sorted(zip(features, tree.feature_importances_), key=lambda x: x[1], reverse=True):
    if imp > 0:
        print(f"  Feature: {f:<26} Importance (Variance Reduction): {imp*100:5.2f}%")

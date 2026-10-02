import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import json
import pandas as pd
from backtest.ai.shadow_engine import ShadowExecutionEngine


def run_shadow_simulation():
    print("=" * 115)
    print("  SHADOW ENGINE REPLAY VALIDATION (HISTORICAL VERIFICATION)")
    print("  Dataset: Out-of-Sample (OOS) Holdout: 2025-01-01 -> 2026-10-02 (N = 123 Trades)")
    print("  Status: Verifying Causal Execution Logic, Accounting, & Telemetry (Outcomes Already Known)")
    print("  Protocol: Bar-by-bar Sequential Feeding | Zero Re-fitting | Report Every 25 Trades")
    print("=" * 115)

    data_dir = Path(__file__).parent / "data"
    oos_path = data_dir / "breakouts_oos_2025_2026.csv"
    oos_df = pd.read_csv(oos_path)

    # Sort strictly by signal_time / entry_time
    oos_df["signal_time"] = pd.to_datetime(oos_df["signal_time"])
    oos_df["entry_time"] = pd.to_datetime(oos_df["entry_time"])
    oos_df = oos_df.sort_values("signal_time").reset_index(drop=True)

    engine = ShadowExecutionEngine()

    report_interval = 25
    total_trades = len(oos_df)

    print(f"\n[1] Shadow Engine Initialized with Frozen Parameters:")
    print(f"  - Model:     {engine.manifest['model_name']} ({engine.manifest['hyperparameters']['model_type']})")
    print(f"  - Features:  Combined {len(engine.features_list)} (Snapshot 14 + Sequence 9)")
    print(f"  - Threshold: theta = {engine.threshold:+.6f}R")
    print(f"  - Total Trades to Evaluate Sequentially: {total_trades}")

    # Sequential iteration
    for idx, row in oos_df.iterrows():
        trade_num = idx + 1

        # Extract features dictionary
        feat_dict = {col: float(row[col]) for col in engine.features_list}

        # Evaluate candidate at candle t
        log_entry = engine.evaluate_candidate(
            timestamp=str(row["signal_time"]),
            asset=row["asset"],
            breakout_id=row["trade_id"],
            features=feat_dict,
            baseline_signal="BUY",
            baseline_entry_price=float(row["entry_price"]),
            eventual_realized_r=float(row["target_realized_r"]),
            eventual_pnl=float(row["net_pnl"])
        )

        # Trigger periodic report every 25 trades or at the final trade
        if trade_num % report_interval == 0 or trade_num == total_trades:
            print("\n" + "-" * 115)
            print(f"  📊 PERIODIC SHADOW MONITORING REPORT (After Trade #{trade_num} of {total_trades})")
            print("-" * 115)

            metrics = engine.generate_dashboard_metrics()
            p1 = metrics["pillar_1_filter_precision"]
            p2 = metrics["pillar_2_tail_preservation"]
            p3 = metrics["pillar_3_avoided_loss_value"]
            p4 = metrics["pillar_4_opportunity_cost"]
            vq = metrics["veto_quality_metrics"]
            reg = metrics["pillar_5_regimes"]
            pnl = metrics["portfolio_pnl"]

            print(f"  • Progress: Evaluated {trade_num}/{total_trades} trades ({trade_num/total_trades*100:4.1f}%)")
            print(f"  • Cumulative Decisions: Passed = {metrics['passed_count']} | Vetoed = {metrics['vetoed_count']} ({metrics['veto_rate_pct']:.1f}%)")
            print(f"  • Portfolio PnL: Baseline Counterfactual = ${pnl['baseline_counterfactual_total_pnl']:>+7.2f} | Shadow Realized = ${pnl['shadow_realized_total_pnl']:>+7.2f} | Net Edge = ${pnl['net_pnl_benefit']:>+7.2f}")
            print(f"  • [Pillar 1 - Filter Precision]: {p1['wording_note']}")
            print(f"  • [Pillar 2 - Tail Preservation]: {p2['tail_preservation_observation']} | Tail Damage: {p2['tail_damage']}")
            print(f"  • [Pillar 3 - Avoided-Loss Value]: ${p3['avoided_dollar_losses']:.2f} saved from toxic setups")
            print(f"  • [Pillar 4 - Opportunity Cost]:   ${p4['foregone_winner_pnl']:.2f} lost from false vetoes")
            print(f"  • [Veto Quality Metrics]: Counterfactual Efficiency = {vq['counterfactual_efficiency']:.3f} | Veto Value Ratio = {vq['veto_value_ratio']:+.3f}")
            print(f"  • [Pillar 5 - Regime Highlights]:")
            for asset, a_stats in reg["by_asset"].items():
                print(f"      - {asset:<8}: {a_stats['total_trades']:>2} trades | {a_stats['vetoed_trades']:>2} vetoed | Base: ${a_stats['baseline_counterfactual_pnl']:>+6.2f} -> Shadow: ${a_stats['shadow_realized_pnl']:>+6.2f}")

    # Export logs
    log_dir = Path(__file__).parent / "logs"
    jsonl_path = log_dir / "shadow_execution_log.jsonl"
    csv_path = log_dir / "shadow_execution_log.csv"
    engine.export_logs(jsonl_path=jsonl_path, csv_path=csv_path)

    print("\n" + "=" * 115)
    print("  SHADOW ENGINE REPLAY VALIDATION SUMMARY (ALL 123 TRADES COMPLETED)")
    print("=" * 115)
    final_m = engine.generate_dashboard_metrics()
    print(f"  Total Trades Processed:           {final_m['total_evaluations']}")
    print(f"  Total Trades Passed:              {final_m['passed_count']}")
    print(f"  Total Trades Vetoed:              {final_m['vetoed_count']}")
    print(f"  Baseline Counterfactual PnL:      ${final_m['portfolio_pnl']['baseline_counterfactual_total_pnl']:+.2f}")
    print(f"  Shadow Realized PnL:              ${final_m['portfolio_pnl']['shadow_realized_total_pnl']:+.2f}")
    print(f"  Net Economic Benefit:             ${final_m['portfolio_pnl']['net_pnl_benefit']:+.2f} (+{final_m['portfolio_pnl']['net_pnl_benefit']/final_m['portfolio_pnl']['baseline_counterfactual_total_pnl']*100:.1f}%)")
    print(f"  Avoided Losses:                   ${final_m['pillar_3_avoided_loss_value']['avoided_dollar_losses']:+.2f}")
    print(f"  Opportunity Cost:                 ${final_m['pillar_4_opportunity_cost']['foregone_winner_pnl']:+.2f}")
    print(f"  Counterfactual Efficiency:        {final_m['veto_quality_metrics']['counterfactual_efficiency']:.3f}")
    print(f"  Veto Value Ratio:                 {final_m['veto_quality_metrics']['veto_value_ratio']:+.3f}")
    print(f"  Tail Preservation Observation:    {final_m['pillar_2_tail_preservation']['tail_preservation_observation']}")
    print(f"  Tail Damage Status:               {final_m['pillar_2_tail_preservation']['tail_damage']}")
    print(f"  Telemetry Logs Saved:             {jsonl_path.relative_to(Path(__file__).parent.parent.parent)}")
    print("=" * 115 + "\n")


if __name__ == "__main__":
    run_shadow_simulation()

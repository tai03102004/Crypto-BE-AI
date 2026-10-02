# AI Negative Veto Filter: Research Freeze & Shadow Governance Protocol v1.0

**Effective Date:** 2026-10-02  
**Current Status Hierarchy:**
```text
RESEARCH
─────────────────────────────────────────────
Feature Research        DONE
Model Selection         DONE (Linear Ridge L2, α=500.0)
Threshold Selection     DONE (+0.356025R từ Dev+Val)
Leakage Audit           PASSED (0.0000000000 future perturbation)
OOS Validation          PASSED (Holdout 2025–2026, 123 trades)
Walk-forward Replay     PASSED (5/5 năm edge dương)
Artifact Freeze         PASSED (SHA256 verified)

SHADOW
─────────────────────────────────────────────
Historical Replay       PASSED (Shadow Engine Replay Validation)
Live Feed               NEXT (Stage A: Infrastructure Validation)
Paper Portfolio         NOT STARTED (Stage C)

LIVE CAPITAL
─────────────────────────────────────────────
NOT APPROVED
```

---

## 1. Triết Lý Thiết Kế & Nguyên Tắc Hoạt Động

Giai đoạn nghiên cứu mô hình (Model/Feature Exploration) chính thức **ĐÓNG BĂNG TUYỆT ĐỐI**.

Mô hình hoạt động thuần túy dưới vai trò **Negative Veto Gate (Bộ lọc phòng thủ)**:

```text
Donchian 55 Signal (Flat state)
             │
             ▼
        Breakout at t
             │
             ▼
     Combined 23 Ridge Score (t)
             │
             ├── Score < +0.356025R ──► VETO (Stay Flat in Cash)
             │
             └── Score ≥ +0.356025R ──► TRADE (Enter at t+1 Open)
```

Mô hình không cố dự báo siêu sóng thắng lớn. Mục tiêu duy nhất:
> *"Setup này có nằm trong vùng mà bằng chứng lịch sử đã chứng minh nên phòng thủ đứng ngoài hay không?"*

---

## 2. Thông Số Mô Hình & Artifacts Đóng Băng Tuyệt Đối

Tất cả binary và manifest được lưu trữ tại [backtest/ai/models/](file:///Users/macbookpro14m1pro/Crypto-BE-AI/backtest/ai/models/) với mã băm SHA256 bất biến:

| Thông Số | Giá Trị Đóng Băng | Ghi Chú & Mã Băm SHA256 |
| :--- | :--- | :--- |
| **Model Architecture** | `sklearn.linear_model.Ridge` | Linear model with L2 regularization, `fit_intercept=True` |
| **Regularization ($\alpha$)** | `500.0` | Co hẹp trọng số cực mạnh, triệt tiêu đa cộng tuyến |
| **Random State** | `42` | Đảm bảo tính tất định hoàn toàn |
| **Training Partition** | `2022-01-01 -> 2024-12-31` | 193 trades (Dev 2022–2023 + Val 2024) |
| **Holdout OOS Partition** | `2025-01-01 -> 2026-10-02` | **123 trades hoàn toàn không tham gia fit model hay scaler** |
| **Input Representation** | `Combined 23` | 14 Snapshot tại nến $t$ + 9 Sequence tiền breakout trong $[t-55, t-1]$ |
| **Scaler Artifact** | `frozen_scaler_v1.joblib` | SHA256: `82d8548d7f874f06cf05dbe003e8707bebb30a10c1445778aee80bdf483b8b1f` |
| **Model Artifact** | `frozen_ridge_v1.joblib` | SHA256: `9d893633631a80447fa0d238b32948ea92c9f55e090be0ec8c9918ff866874eb` |
| **Frozen Decision Threshold ($\theta$)** | `+0.356025R` | Điểm phân vị 20% của $\hat{R}$ tính trên tập Dev+Val, **khóa trước khi OOS bắt đầu** |
| **Decision Rule** | `VETO if predicted_R < +0.356025 else PASS` | Đánh giá trước khi nến $t+1$ mở cửa |

---

## 3. Khóa Cứng Giao Thức Đánh Giá (Freeze the Evaluation Protocol)

Để ngăn ngừa hiện tượng "model shopping" hoặc "metric drift" sau khi nhìn dữ liệu mới, không chỉ model mà **toàn bộ protocol đánh giá được đóng băng**:

```text
Model                 FROZEN
Scaler                FROZEN
Features              FROZEN
Threshold             FROZEN
Decision Rule         FROZEN
Evaluation Window     FROZEN (Định kỳ báo cáo mỗi 25-50 trade)
Metrics Set           FROZEN (5 Trụ cột + Counterfactual Efficiency)
Promotion Criteria    FROZEN (Giao thức 3 tầng bên dưới)
```

---

## 4. Giao Thức Xét Duyệt 3 Tầng (3-Tier Promotion Protocol)

Hệ thống **tuyệt đối không nhảy từ 50 trade shadow sang vốn thật**. Quá trình chuyển tiếp phải trải qua 3 giai đoạn độc lập:

### Stage A — Infrastructure Validation (20–30 live signals)
Mục tiêu là kiểm tra tính toàn vẹn kỹ thuật của pipeline trên real-time feed, không tối ưu hiệu suất:
- Timestamp của feature khớp chính xác với thời điểm nến đóng cửa ($t$).
- Không có missing candle, không có nến tương lai ($t+1$).
- Giá trị dự báo $\hat{R}$ tái lập 100% khớp với artifact model đã khóa (SHA256 verified).
- Threshold kiểm tra đúng chuẩn `+0.356025R`.
- Dòng thời gian: $\text{Signal Timestamp} (t) \to \text{Decision Timestamp} < \text{Bar Close } (t+1)$.
- Khả năng chống trùng lặp tín hiệu (deduplication) khi websocket bị disconnect/reconnect.
- Log telemetry ghi nhận đầy đủ vào JSONL/CSV.
*Nguyên tắc:* Nếu phát hiện lỗi trong Stage A, chỉ sửa **infrastructure**, **tuyệt đối không sửa model**.

### Stage B — Statistical Shadow Validation (50–100 eligible signals/trades)
Theo dõi hành vi thống kê của model trên dữ liệu mới mà chưa vào lệnh:
- $N$ (Số lượng setup), Veto rate (%).
- Mean Realized $R$ của nhóm bị veto, tỷ lệ thua lỗ trong nhóm bị veto.
- Số lượng veto sai (False-veto count).
- Avoided-Loss Value ($), Opportunity Cost ($), Net Economic Edge ($).
- Số lượng tail winners bị veto ($\ge +2R, \ge +5R, \ge +10R$).
*Lưu ý:* Việc tổn thất tail winner phải được **theo dõi (monitor)**, không biến thành hard gate tuyệt đối (như $0/50$ winners $\ge +5R$) để tránh lấy mẫu nhiễu làm tiêu chí loại bỏ model.

### Stage C — Paper Portfolio (Chạy song song 2 danh mục ảo)
Chạy song song trên cùng một luồng tín hiệu (identical signal stream):
```text
Tín hiệu Donchian 55
         │
         ├── Portfolio 1: Baseline Paper Trade (Không filter)
         │
         └── Portfolio 2: AI-Filtered Paper Trade (Veto if score < +0.356R)
```
Đánh giá so sánh: Equity curve, Max Drawdown (MDD), Profit Factor (PF), Expectancy, Turnover, Phí giao dịch thực tế, Slippage thực tế, missed winners, và hành vi theo regime thị trường.

---

## 5. Cấu Trúc Log Telemetry & Kế Toán Phản Thực (Counterfactual Accounting)

Log tại [shadow_engine.py](file:///Users/macbookpro14m1pro/Crypto-BE-AI/backtest/ai/shadow_engine.py) phân biệt rõ ràng giữa kết quả thực tế của shadow portfolio và kết quả phản thực (counterfactual) của lệnh bị veto:

```json
{
  "timestamp": "2026-03-04 12:00:00",
  "asset": "SOLUSDT",
  "breakout_id": "SOLUSDT_021",
  "baseline_signal": "BUY",
  "ai_predicted_r": -0.3401,
  "threshold": 0.356025,
  "ai_decision": "VETO",
  "baseline_entry": 142.50,
  "shadow_entry": null,
  "eventual_realized_r": -1.023,
  "baseline_counterfactual_pnl": -9.82,
  "shadow_realized_pnl": 0.0,
  "avoided_loss": 9.82,
  "opportunity_cost": 0.0,
  "would_have_been_vetoed": true,
  "pnl_delta": 9.82
}
```

---

## 6. Bộ Chỉ Số Giám Sát Dashboard (5 Trụ Cột + Veto Quality Metrics)

Dashboard theo dõi định kỳ sau mỗi 25–50 trade gồm 5 nhóm chính và 2 chỉ số chất lượng veto bổ sung:

1. **Filter Precision:**
   - Số lệnh thua vs Số lệnh thắng trong nhóm bị veto.
   - *Wording chuẩn mực:* `7/7 vetoed trades were losses (sample size n=7)`. Không dùng từ "100% precision".
2. **Tail Preservation:**
   - Theo dõi số lượng lệnh bị veto có $R \ge +2R, \ge +5R, \ge +10R$.
   - *Wording chuẩn mực:*
     ```text
     Tail Preservation Observation: 0 / 12 OOS winners >= top-10% were vetoed
     Tail Damage: NOT OBSERVED
     ```
3. **Avoided-Loss Value:**
   - Tổng số tiền lỗ tránh được từ các lệnh bị veto có $PnL < 0$: $\sum |\text{PnL}_{\text{vetoed losers}}|$.
4. **Opportunity Cost:**
   - Tổng số tiền lãi bỏ lỡ từ các lệnh bị veto nhầm có $PnL > 0$: $\sum \text{PnL}_{\text{vetoed winners}}$.
5. **Veto Quality Metrics (Mới bổ sung):**
   - **Counterfactual Efficiency:**
     $$\text{Counterfactual Efficiency} = \frac{\text{Avoided Losses}}{\text{Total Vetoed Absolute PnL}} = \frac{\text{Avoided Losses}}{\sum |\text{PnL of Vetoed Trades}|}$$
   - **Veto Value Ratio:**
     $$\text{Veto Value Ratio} = \frac{\text{Avoided Loss} - \text{Opportunity Cost}}{|\text{Opportunity Cost}| + \text{Avoided Loss}}$$
6. **Regime Breakdown:**
   - Phân loại theo Trend (Close vs EMA200), Volatility (NATR vs Median), và Asset (BTC, ETH, SOL, BNB).

---

## 7. Kết Quả Xác Nhận Shadow Engine Replay (Historical Verification)

Thực hiện replay tuần tự 123 trade OOS (2025–2026) bằng [run_shadow_simulation.py](file:///Users/macbookpro14m1pro/Crypto-BE-AI/backtest/ai/run_shadow_simulation.py):

| Chỉ Số Giám Sát | Kết Quả Replay | Ghi Chú Phương Pháp Luận |
| :--- | :---: | :--- |
| **Total Trades Processed** | 123 | Chạy tuần tự không nhìn trước |
| **Passed / Vetoed** | 116 / 7 (5.7%) | Tỷ lệ veto conservative |
| **Baseline Counterfactual PnL** | +$80.93 | Lợi nhuận nếu đánh toàn bộ 123 trade |
| **Shadow Realized PnL** | **+$156.38** | Lợi nhuận danh mục sau khi loại 7 trade bị veto |
| **Net Economic Benefit** | **+$75.45 (+93.2%)** | Giá trị kinh tế gia tăng ròng |
| **Filter Precision Observation** | 7/7 vetoed were losses | Quan sát thực nghiệm trên mẫu nhỏ $n=7$ |
| **Tail Damage Status** | **NOT OBSERVED** | 0/12 top 10% winners bị loại |
| **Avoided Losses / Opportunity Cost** | **+$75.45 / $0.00** | Tránh toàn bộ 7 stop-out, không bỏ lỡ winner |
| **Counterfactual Efficiency** | **1.000** | 100% PnL của nhóm veto là lỗ được triệt tiêu |
| **Veto Value Ratio** | **+1.000** | Tỷ số giá trị veto đạt mức tối ưu trong mẫu OOS |

---

## 8. Hành Động Tiếp Theo Duy Nhất

**Không code thêm AI hay tune lại threshold.**

Hành động kỹ thuật tiếp theo: **Kết nối `ShadowExecutionEngine` vào luồng nến live (hoặc mock feed streaming) để bắt đầu Stage A (Infrastructure Validation)**. Mọi tín hiệu mới từ thời điểm này là dữ liệu tương lai chưa biết; toàn bộ tham số nghiên cứu được bảo tồn nguyên vẹn.

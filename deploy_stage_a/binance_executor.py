import time
import hmac
import hashlib
import math
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode
import requests


class BinanceExecutor:
    """
    Production-grade Binance Spot Execution Engine.
    Handles HMAC-SHA256 signature authentication, exchange filter normalization,
    order sizing, market execution, and stop-loss placement.

    Modes:
      - 'LIVE': Real trading on https://api.binance.com
      - 'TESTNET': Paper trading on https://testnet.binance.vision
      - 'DRY_RUN': Simulated live execution (safe local testing without placing orders)
    """

    LIVE_BASE_URL = "https://api.binance.com"
    TESTNET_BASE_URL = "https://testnet.binance.vision"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        mode: str = "DRY_RUN",
        risk_per_trade_pct: float = 0.01,  # 1% equity risk per trade
        max_order_usdt: float = 500.0,     # Safety hard cap per order
        default_dry_run_equity: float = 1000.0
    ):
        self.api_key = api_key or ""
        self.api_secret = api_secret or ""
        self.mode = mode.upper()
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_order_usdt = max_order_usdt
        self.dry_run_balance = default_dry_run_equity

        if self.mode == "TESTNET":
            self.base_url = self.TESTNET_BASE_URL
        else:
            self.base_url = self.LIVE_BASE_URL

        # Auto fallback to DRY_RUN if credentials are not provided
        if self.mode in ["LIVE", "TESTNET"] and (not self.api_key or not self.api_secret):
            print("⚠️ [Executor Warning] Binance API Key or Secret missing. Falling back to DRY_RUN mode.")
            self.mode = "DRY_RUN"

        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-MBX-APIKEY": self.api_key})

        self.symbol_filters: Dict[str, Dict[str, float]] = {}
        self._load_exchange_filters()

    def _sign_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Appends timestamp, recvWindow, and cryptographic HMAC-SHA256 signature."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _load_exchange_filters(self):
        """Fetches symbol lot size and price filters to prevent LOT_SIZE / NOTIONAL errors."""
        try:
            res = requests.get(f"{self.base_url}/api/v3/exchangeInfo", timeout=10)
            if res.status_code == 200:
                data = res.json()
                for s in data.get("symbols", []):
                    symbol = s["symbol"]
                    filters = s.get("filters", [])
                    step_size = 0.0001
                    min_qty = 0.0001
                    min_notional = 5.0
                    tick_size = 0.01

                    for f in filters:
                        if f["filterType"] == "LOT_SIZE":
                            step_size = float(f.get("stepSize", 0.0001))
                            min_qty = float(f.get("minQty", 0.0001))
                        elif f["filterType"] in ["NOTIONAL", "MIN_NOTIONAL"]:
                            min_notional = float(f.get("minNotional", 5.0))
                        elif f["filterType"] == "PRICE_FILTER":
                            tick_size = float(f.get("tickSize", 0.01))

                    self.symbol_filters[symbol] = {
                        "step_size": step_size,
                        "min_qty": min_qty,
                        "min_notional": min_notional,
                        "tick_size": tick_size
                    }
        except Exception as e:
            print(f"⚠️ [Executor Warning] Could not fetch exchange filters: {e}")

    def format_quantity(self, symbol: str, raw_qty: float) -> float:
        """Rounds quantity down to exact valid stepSize allowed by Binance."""
        filt = self.symbol_filters.get(symbol, {"step_size": 0.0001, "min_qty": 0.0001})
        step = filt["step_size"]
        if step <= 0:
            return round(raw_qty, 4)
        precision = max(0, int(round(-math.log10(step))))
        qty = math.floor(raw_qty / step) * step
        return round(qty, precision)

    def get_usdt_balance(self) -> float:
        """Returns free available USDT balance."""
        if self.mode == "DRY_RUN":
            return self.dry_run_balance

        try:
            params = self._sign_params({})
            res = self.session.get(f"{self.base_url}/api/v3/account", params=params, timeout=10)
            if res.status_code == 200:
                balances = res.json().get("balances", [])
                for b in balances:
                    if b["asset"] == "USDT":
                        return float(b["free"])
            else:
                print(f"⚠️ [Binance API Error] Failed to get balance: {res.text}")
        except Exception as e:
            print(f"⚠️ [Binance Network Error] Get balance failed: {e}")

        return 0.0

    def calculate_position_size(self, symbol: str, current_price: float, atr: float) -> Tuple[float, float, float]:
        """
        Calculates position size based on 1% equity risk:
          Dollar Risk per Unit = 2.0 * ATR
          Risk Amount = Balance * risk_per_trade_pct
          Quantity = Risk Amount / Dollar Risk
        Returns: (formatted_qty, dollar_risk_per_unit, total_cost_usdt)
        """
        balance = self.get_usdt_balance()
        if balance <= 0:
            balance = 100.0  # Fallback minimum

        dollar_risk_per_unit = 2.0 * atr if atr > 0 else current_price * 0.03
        risk_budget = balance * self.risk_per_trade_pct
        raw_qty = risk_budget / dollar_risk_per_unit

        # Apply hard safety cap on total trade notional
        total_cost = raw_qty * current_price
        if total_cost > self.max_order_usdt:
            raw_qty = self.max_order_usdt / current_price

        qty = self.format_quantity(symbol, raw_qty)
        filt = self.symbol_filters.get(symbol, {"min_qty": 0.0001, "min_notional": 5.0})
        
        # Verify minNotional and minQty
        if qty < filt["min_qty"] or (qty * current_price) < filt["min_notional"]:
            print(f"ℹ️ [Size Notice] Calculated qty {qty} is below minNotional ${filt['min_notional']}. Adjusting to min allowed.")
            min_required = filt["min_notional"] / current_price * 1.05
            qty = self.format_quantity(symbol, max(min_required, filt["min_qty"]))

        return qty, dollar_risk_per_unit, qty * current_price

    def place_market_buy(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Places a Market BUY order."""
        if self.mode == "DRY_RUN":
            order_id = f"DRY_BUY_{int(time.time()*1000)}"
            print(f"🧪 [DRY RUN] Executed simulated BUY: {quantity} {symbol}")
            return {
                "status": "FILLED",
                "orderId": order_id,
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "executedQty": str(quantity),
                "is_dry_run": True
            }

        try:
            params = {
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quantity": quantity
            }
            signed_params = self._sign_params(params)
            res = self.session.post(f"{self.base_url}/api/v3/order", data=signed_params, timeout=10)
            res_data = res.json()
            if res.status_code == 200:
                print(f"✅ [LIVE BUY FILLED] {quantity} {symbol} | OrderID: {res_data.get('orderId')}")
                return res_data
            else:
                print(f"❌ [LIVE BUY FAILED] {res_data}")
                return {"status": "FAILED", "error": res_data}
        except Exception as e:
            print(f"❌ [LIVE BUY EXCEPTION] {e}")
            return {"status": "ERROR", "error": str(e)}

    def place_market_sell(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Places a Market SELL order (for Stop Loss or Take Profit exit)."""
        qty = self.format_quantity(symbol, quantity)
        if self.mode == "DRY_RUN":
            order_id = f"DRY_SELL_{int(time.time()*1000)}"
            print(f"🧪 [DRY RUN] Executed simulated SELL: {qty} {symbol}")
            return {
                "status": "FILLED",
                "orderId": order_id,
                "symbol": symbol,
                "side": "SELL",
                "type": "MARKET",
                "executedQty": str(qty),
                "is_dry_run": True
            }

        try:
            params = {
                "symbol": symbol,
                "side": "SELL",
                "type": "MARKET",
                "quantity": qty
            }
            signed_params = self._sign_params(params)
            res = self.session.post(f"{self.base_url}/api/v3/order", data=signed_params, timeout=10)
            res_data = res.json()
            if res.status_code == 200:
                print(f"✅ [LIVE SELL FILLED] {qty} {symbol} | OrderID: {res_data.get('orderId')}")
                return res_data
            else:
                print(f"❌ [LIVE SELL FAILED] {res_data}")
                return {"status": "FAILED", "error": res_data}
        except Exception as e:
            print(f"❌ [LIVE SELL EXCEPTION] {e}")
            return {"status": "ERROR", "error": str(e)}

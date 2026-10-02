class TradingCosts:
    """
    Simulates exchange transaction costs:
    - Maker fee (limit orders)
    - Taker fee (market orders / stops)
    - Slippage (market impact & volatility execution decay)
    """

    def __init__(
        self,
        fee_rate: float = 0.0005,      # 0.05% default taker fee (Binance VIP0 Futures or promo Spot)
        slippage_rate: float = 0.0003  # 0.03% realistic slippage for high-liquidity crypto (BTC/ETH)
    ):
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def calculate_entry_execution(self, requested_price: float, side: str) -> tuple[float, float]:
        """
        Applies slippage and calculates fee for an entry fill.
        - For BUY: slippage pushes execution price UP.
        - For SELL: slippage pushes execution price DOWN.
        Returns: (executed_price, fee_pct)
        """
        if side.upper() in ["BUY", "LONG"]:
            executed_price = requested_price * (1.0 + self.slippage_rate)
        else:
            executed_price = requested_price * (1.0 - self.slippage_rate)
        return executed_price, self.fee_rate

    def calculate_exit_execution(self, requested_price: float, position_side: str) -> tuple[float, float]:
        """
        Applies slippage and calculates fee for an exit fill.
        - Exiting a LONG position means selling: price slips DOWN.
        - Exiting a SHORT position means buying to cover: price slips UP.
        Returns: (executed_price, fee_pct)
        """
        if position_side.upper() == "SHORT":
            # To close a short, you must buy back -> slippage pushes price UP
            executed_price = requested_price * (1.0 + self.slippage_rate)
        else:
            # To close a long, you must sell -> slippage pushes price DOWN
            executed_price = requested_price * (1.0 - self.slippage_rate)
        return executed_price, self.fee_rate

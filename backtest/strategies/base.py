from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class Signal:
    action: str  # "BUY", "SELL", "CLOSE", "HOLD"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0
    confidence: float = 1.0  # Optional score or calibrated probability
    reason: str = ""


class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    Receives strictly past data (bars up to t) and returns a Signal.
    """

    def __init__(self, name: str = "BaseStrategy"):
        self.name = name

    @abstractmethod
    def on_bar(self, current_bar: pd.Series, history_df: pd.DataFrame) -> Signal:
        """
        Invoked at the close of current_bar (timestamp t).
        history_df contains all historical candles up to and including current_bar.
        """
        pass

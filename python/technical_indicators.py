import sys
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any
import warnings
warnings.filterwarnings('ignore')

class TechnicalIndicators:
    """
    Lớp tính toán các chỉ báo kỹ thuật cho crypto
    """
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Dict[str, Any]:
        """
        Tính RSI (Relative Strength Index)
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        try:
            if len(prices) < period + 1:
                return {"error": "Không đủ dữ liệu để tính RSI"}
            
            df = pd.DataFrame({'price': prices})
            delta = df['price'].diff()
            
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            current_rsi = rsi.iloc[-1]
            
            # Phân tích RSI
            if current_rsi >= 70:
                signal = "OVERSOLD"
                message = "Vùng quá mua - Có thể bán"
            elif current_rsi <= 30:
                signal = "OVERBOUGHT"
                message = "Vùng quá bán - Có thể mua"
            else:
                signal = "NEUTRAL"
                message = "Vùng trung tính"
            
            return {
                "indicator": "RSI",
                "value": round(current_rsi, 2),
                "signal": signal,
                "message": message,
                "period": period,
                "history": rsi.dropna().round(2).tolist()[-10:]  # 10 giá trị gần nhất
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính RSI: {str(e)}"}
    
    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, Any]:
        """
        Tính MACD (Moving Average Convergence Divergence)
        MACD = EMA_fast - EMA_slow
        Signal Line = EMA của MACD
        Histogram = MACD - Signal Line
        """
        try:
            if len(prices) < slow_period + signal_period:
                return {"error": "Không đủ dữ liệu để tính MACD"}
            
            df = pd.DataFrame({'price': prices})
            
            # Tính EMA
            ema_fast = df['price'].ewm(span=fast_period).mean()
            ema_slow = df['price'].ewm(span=slow_period).mean()
            
            # Tính MACD
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal_period).mean()
            histogram = macd_line - signal_line
            
            current_macd = macd_line.iloc[-1]
            current_signal = signal_line.iloc[-1]
            current_histogram = histogram.iloc[-1]
            
            # Phân tích MACD
            if current_macd > current_signal and histogram.iloc[-2] < 0:
                signal = "BUY"
                message = "MACD cắt lên Signal - Tín hiệu mua"
            elif current_macd < current_signal and histogram.iloc[-2] > 0:
                signal = "SELL"
                message = "MACD cắt xuống Signal - Tín hiệu bán"
            elif current_macd > current_signal:
                signal = "BULLISH"
                message = "MACD trên Signal - Xu hướng tăng"
            else:
                signal = "BEARISH"
                message = "MACD dưới Signal - Xu hướng giảm"
            
            return {
                "indicator": "MACD",
                "macd": round(current_macd, 4),
                "signal": round(current_signal, 4),
                "histogram": round(current_histogram, 4),
                "trend": signal,
                "message": message,
                "history": {
                    "macd": macd_line.dropna().round(4).tolist()[-10:],
                    "signal": signal_line.dropna().round(4).tolist()[-10:],
                    "histogram": histogram.dropna().round(4).tolist()[-10:]
                }
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính MACD: {str(e)}"}
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2) -> Dict[str, Any]:
        """
        Tính Bollinger Bands
        Middle Band = SMA
        Upper Band = SMA + (std_dev * standard deviation)
        Lower Band = SMA - (std_dev * standard deviation)
        """
        try:
            if len(prices) < period:
                return {"error": "Không đủ dữ liệu để tính Bollinger Bands"}
            
            df = pd.DataFrame({'price': prices})
            
            # Tính SMA và standard deviation
            sma = df['price'].rolling(window=period).mean()
            std = df['price'].rolling(window=period).std()
            
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            
            current_price = prices[-1]
            current_upper = upper_band.iloc[-1]
            current_lower = lower_band.iloc[-1]
            current_middle = sma.iloc[-1]
            
            # Phân tích Bollinger Bands
            if current_price >= current_upper:
                signal = "OVERBOUGHT"
                message = "Giá chạm band trên - Có thể quá mua"
            elif current_price <= current_lower:
                signal = "OVERSOLD"
                message = "Giá chạm band dưới - Có thể quá bán"
            elif current_price > current_middle:
                signal = "BULLISH"
                message = "Giá trên đường giữa - Xu hướng tăng"
            else:
                signal = "BEARISH"
                message = "Giá dưới đường giữa - Xu hướng giảm"
            
            return {
                "indicator": "BOLLINGER_BANDS",
                "current_price": round(current_price, 2),
                "upper_band": round(current_upper, 2),
                "middle_band": round(current_middle, 2),
                "lower_band": round(current_lower, 2),
                "signal": signal,
                "message": message,
                "bandwidth": round(((current_upper - current_lower) / current_middle) * 100, 2)
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính Bollinger Bands: {str(e)}"}
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int = 21) -> Dict[str, Any]:
        """
        Tính EMA (Exponential Moving Average)
        """
        try:
            if len(prices) < period:
                return {"error": "Không đủ dữ liệu để tính EMA"}
            
            df = pd.DataFrame({'price': prices})
            ema = df['price'].ewm(span=period).mean()
            
            current_price = prices[-1]
            current_ema = ema.iloc[-1]
            
            # Phân tích EMA
            if current_price > current_ema:
                signal = "BULLISH"
                message = f"Giá trên EMA{period} - Xu hướng tăng"
            else:
                signal = "BEARISH"
                message = f"Giá dưới EMA{period} - Xu hướng giảm"
            
            return {
                "indicator": f"EMA_{period}",
                "current_price": round(current_price, 2),
                "ema_value": round(current_ema, 2),
                "signal": signal,
                "message": message,
                "history": ema.dropna().round(2).tolist()[-10:]
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính EMA: {str(e)}"}
    
    @staticmethod
    def calculate_stochastic(prices: List[float], highs: List[float], lows: List[float], k_period: int = 14, d_period: int = 3) -> Dict[str, Any]:
        """
        Tính Stochastic Oscillator
        %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA của %K
        """
        try:
            if len(prices) < k_period:
                return {"error": "Không đủ dữ liệu để tính Stochastic"}
            
            df = pd.DataFrame({
                'close': prices,
                'high': highs if highs else prices,
                'low': lows if lows else prices
            })
            
            # Tính %K
            lowest_low = df['low'].rolling(window=k_period).min()
            highest_high = df['high'].rolling(window=k_period).max()
            
            k_percent = ((df['close'] - lowest_low) / (highest_high - lowest_low)) * 100
            d_percent = k_percent.rolling(window=d_period).mean()
            
            current_k = k_percent.iloc[-1]
            current_d = d_percent.iloc[-1]
            
            # Phân tích Stochastic
            if current_k >= 80 and current_d >= 80:
                signal = "OVERBOUGHT"
                message = "Stochastic trong vùng quá mua"
            elif current_k <= 20 and current_d <= 20:
                signal = "OVERSOLD"
                message = "Stochastic trong vùng quá bán"
            elif current_k > current_d:
                signal = "BULLISH"
                message = "%K trên %D - Tín hiệu tăng"
            else:
                signal = "BEARISH"
                message = "%K dưới %D - Tín hiệu giảm"
            
            return {
                "indicator": "STOCHASTIC",
                "k_percent": round(current_k, 2),
                "d_percent": round(current_d, 2),
                "signal": signal,
                "message": message
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính Stochastic: {str(e)}"}
    
    @staticmethod
    def calculate_multiple_indicators(prices: List[float], indicators: List[str] = None) -> Dict[str, Any]:
        """
        Tính nhiều chỉ báo cùng lúc và đưa ra phân tích tổng hợp
        """
        if indicators is None:
            indicators = ['rsi', 'macd', 'bollinger', 'ema']
        
        results = {}
        
        for indicator in indicators:
            if indicator.lower() == 'rsi':
                results['rsi'] = TechnicalIndicators.calculate_rsi(prices)
            elif indicator.lower() == 'macd':
                results['macd'] = TechnicalIndicators.calculate_macd(prices)
            elif indicator.lower() == 'bollinger':
                results['bollinger'] = TechnicalIndicators.calculate_bollinger_bands(prices)
            elif indicator.lower() == 'ema':
                results['ema'] = TechnicalIndicators.calculate_ema(prices)
        
        # Phân tích tổng hợp
        signals = []
        for key, value in results.items():
            if 'signal' in value:
                signals.append(value['signal'])
            elif 'trend' in value:
                signals.append(value['trend'])
        
        # Đếm tín hiệu
        bullish_count = sum(1 for s in signals if s in ['BULLISH', 'BUY', 'OVERSOLD'])
        bearish_count = sum(1 for s in signals if s in ['BEARISH', 'SELL', 'OVERBOUGHT'])
        
        if bullish_count > bearish_count:
            overall_signal = "BULLISH"
            recommendation = "Xu hướng tăng - Có thể mua"
        elif bearish_count > bullish_count:
            overall_signal = "BEARISH"
            recommendation = "Xu hướng giảm - Có thể bán"
        else:
            overall_signal = "NEUTRAL"
            recommendation = "Tín hiệu trung tính - Quan sát thêm"
        
        results['summary'] = {
            "overall_signal": overall_signal,
            "recommendation": recommendation,
            "bullish_signals": bullish_count,
            "bearish_signals": bearish_count,
            "total_indicators": len(indicators)
        }
        
        return results

def main():
    try:
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Thiếu tham số. Cần: prices_json và indicator_name"}))
            return
        
        prices_json = sys.argv[1]
        indicator_name = sys.argv[2]
        
        # Parse prices
        prices = json.loads(prices_json)
        
        # Tạo instance
        ta = TechnicalIndicators()
        
        # Tính chỉ báo dựa trên tên
        if indicator_name.lower() == 'rsi':
            result = ta.calculate_rsi(prices)
        elif indicator_name.lower() == 'macd':
            result = ta.calculate_macd(prices)
        elif indicator_name.lower() == 'bollinger':
            result = ta.calculate_bollinger_bands(prices)
        elif indicator_name.lower() == 'ema':
            result = ta.calculate_ema(prices)
        elif indicator_name.lower() == 'stochastic':
            result = ta.calculate_stochastic(prices, prices, prices)  # Dùng prices làm high/low
        elif indicator_name.lower() == 'all':
            result = ta.calculate_multiple_indicators(prices)
        else:
            result = {"error": f"Chỉ báo '{indicator_name}' không được hỗ trợ"}
        
        print(json.dumps(result, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({"error": f"Lỗi: {str(e)}"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
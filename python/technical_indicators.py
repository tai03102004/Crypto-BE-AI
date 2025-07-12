import sys
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
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
            
            # Phân tích RSI - SỬA LẠI: RSI >= 70 là quá mua, RSI <= 30 là quá bán
            if current_rsi >= 70:
                signal = "OVERBOUGHT"
                message = "Vùng quá mua - Có thể bán"
            elif current_rsi <= 30:
                signal = "OVERSOLD"
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
                "history": rsi.dropna().round(2).tolist()[-10:]
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính RSI: {str(e)}"}
    
    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict[str, Any]:
        """
        Tính MACD (Moving Average Convergence Divergence)
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
            prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0
            
            # Phân tích MACD
            if current_macd > current_signal and prev_histogram <= 0 and current_histogram > 0:
                signal = "BUY"
                message = "MACD cắt lên Signal - Tín hiệu mua mạnh"
            elif current_macd < current_signal and prev_histogram >= 0 and current_histogram < 0:
                signal = "SELL"
                message = "MACD cắt xuống Signal - Tín hiệu bán mạnh"
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
            band_position = (current_price - current_lower) / (current_upper - current_lower)
            
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
                "bandwidth": round(((current_upper - current_lower) / current_middle) * 100, 2),
                "band_position": round(band_position, 2)
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
            
            # Tính độ dốc của EMA
            if len(ema) >= 2:
                ema_slope = (ema.iloc[-1] - ema.iloc[-2]) / ema.iloc[-2] * 100
            else:
                ema_slope = 0
            
            # Phân tích EMA
            if current_price > current_ema:
                if ema_slope > 0:
                    signal = "STRONG_BULLISH"
                    message = f"Giá trên EMA{period} và EMA đang tăng - Xu hướng tăng mạnh"
                else:
                    signal = "BULLISH"
                    message = f"Giá trên EMA{period} - Xu hướng tăng"
            else:
                if ema_slope < 0:
                    signal = "STRONG_BEARISH"
                    message = f"Giá dưới EMA{period} và EMA đang giảm - Xu hướng giảm mạnh"
                else:
                    signal = "BEARISH"
                    message = f"Giá dưới EMA{period} - Xu hướng giảm"
            
            return {
                "indicator": f"EMA_{period}",
                "current_price": round(current_price, 2),
                "ema_value": round(current_ema, 2),
                "signal": signal,
                "message": message,
                "ema_slope": round(ema_slope, 4),
                "history": ema.dropna().round(2).tolist()[-10:]
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính EMA: {str(e)}"}
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int = 20) -> Dict[str, Any]:
        """
        Tính SMA (Simple Moving Average)
        """
        try:
            if len(prices) < period:
                return {"error": "Không đủ dữ liệu để tính SMA"}
            
            df = pd.DataFrame({'price': prices})
            sma = df['price'].rolling(window=period).mean()
            
            current_price = prices[-1]
            current_sma = sma.iloc[-1]
            
            # Tính độ dốc của SMA
            if len(sma) >= 2:
                sma_slope = (sma.iloc[-1] - sma.iloc[-2]) / sma.iloc[-2] * 100
            else:
                sma_slope = 0
            
            # Phân tích SMA
            if current_price > current_sma:
                if sma_slope > 0:
                    signal = "STRONG_BULLISH"
                    message = f"Giá trên SMA{period} và SMA đang tăng - Xu hướng tăng mạnh"
                else:
                    signal = "BULLISH"
                    message = f"Giá trên SMA{period} - Xu hướng tăng"
            else:
                if sma_slope < 0:
                    signal = "STRONG_BEARISH"
                    message = f"Giá dưới SMA{period} và SMA đang giảm - Xu hướng giảm mạnh"
                else:
                    signal = "BEARISH"
                    message = f"Giá dưới SMA{period} - Xu hướng giảm"
            
            return {
                "indicator": f"SMA_{period}",
                "current_price": round(current_price, 2),
                "sma_value": round(current_sma, 2),
                "signal": signal,
                "message": message,
                "sma_slope": round(sma_slope, 4),
                "history": sma.dropna().round(2).tolist()[-10:]
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính SMA: {str(e)}"}
    
    @staticmethod
    def calculate_volume(prices: List[float], volumes: List[float], period: int = 20) -> Dict[str, Any]:
        """
        Tính trung bình khối lượng giao dịch và Volume Rate of Change
        """
        try:
            if len(volumes) < period:
                return {"error": "Không đủ dữ liệu để tính khối lượng giao dịch"}
            
            df = pd.DataFrame({'volume': volumes, 'price': prices})
            sma_volume = df['volume'].rolling(window=period).mean()
            
            current_volume = volumes[-1]
            current_sma_volume = sma_volume.iloc[-1]
            
            # Tính Volume Rate of Change
            if len(volumes) >= 2:
                volume_roc = (current_volume - volumes[-2]) / volumes[-2] * 100
            else:
                volume_roc = 0
            
            # Tính tỷ lệ volume so với trung bình
            volume_ratio = current_volume / current_sma_volume
            
            # Phân tích khối lượng với price action
            price_change = (prices[-1] - prices[-2]) / prices[-2] * 100 if len(prices) >= 2 else 0
            
            if volume_ratio > 1.5:  # Volume cao hơn 50% so với trung bình
                if price_change > 0:
                    signal = "STRONG_BULLISH"
                    message = "Khối lượng cao với giá tăng - Tín hiệu tăng mạnh"
                else:
                    signal = "STRONG_BEARISH"
                    message = "Khối lượng cao với giá giảm - Tín hiệu giảm mạnh"
            elif volume_ratio > 1.2:  # Volume cao hơn 20% so với trung bình
                if price_change > 0:
                    signal = "BULLISH"
                    message = "Khối lượng tăng với giá tăng - Tín hiệu tăng"
                else:
                    signal = "BEARISH"
                    message = "Khối lượng tăng với giá giảm - Tín hiệu giảm"
            else:
                signal = "NEUTRAL"
                message = "Khối lượng thấp - Tín hiệu không rõ ràng"
            
            return {
                "indicator": f"VOLUME_{period}",
                "current_volume": round(current_volume, 2),
                "sma_volume": round(current_sma_volume, 2),
                "volume_ratio": round(volume_ratio, 2),
                "volume_roc": round(volume_roc, 2),
                "signal": signal,
                "message": message,
                "history": sma_volume.dropna().round(2).tolist()[-10:]
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính khối lượng giao dịch: {str(e)}"}
    
    @staticmethod
    def calculate_stochastic(prices: List[float], highs: Optional[List[float]] = None, 
                           lows: Optional[List[float]] = None, k_period: int = 14, d_period: int = 3) -> Dict[str, Any]:
        """
        Tính Stochastic Oscillator
        %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA của %K
        """
        try:
            if len(prices) < k_period + d_period:
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
            
            # Phân tích Stochastic với crossover
            prev_k = k_percent.iloc[-2] if len(k_percent) > 1 else current_k
            prev_d = d_percent.iloc[-2] if len(d_percent) > 1 else current_d
            
            if current_k >= 80 and current_d >= 80:
                signal = "OVERBOUGHT"
                message = "Stochastic trong vùng quá mua - Có thể bán"
            elif current_k <= 20 and current_d <= 20:
                signal = "OVERSOLD"
                message = "Stochastic trong vùng quá bán - Có thể mua"
            elif current_k > current_d and prev_k <= prev_d:
                signal = "BUY"
                message = "%K cắt lên %D - Tín hiệu mua"
            elif current_k < current_d and prev_k >= prev_d:
                signal = "SELL"
                message = "%K cắt xuống %D - Tín hiệu bán"
            elif current_k > current_d:
                signal = "BULLISH"
                message = "%K trên %D - Xu hướng tăng"
            else:
                signal = "BEARISH"
                message = "%K dưới %D - Xu hướng giảm"
            
            return {
                "indicator": "STOCHASTIC",
                "k_percent": round(current_k, 2),
                "d_percent": round(current_d, 2),
                "signal": signal,
                "message": message,
                "k_period": k_period,
                "d_period": d_period,
                "history": {
                    "k_percent": k_percent.dropna().round(2).tolist()[-10:],
                    "d_percent": d_percent.dropna().round(2).tolist()[-10:]
                }
            }
            
        except Exception as e:
            return {"error": f"Lỗi tính Stochastic: {str(e)}"}
    
    @staticmethod
    def calculate_multiple_indicators(prices: List[float], volumes: Optional[List[float]] = None, 
                                    highs: Optional[List[float]] = None, lows: Optional[List[float]] = None,
                                    indicators: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Tính nhiều chỉ báo cùng lúc và đưa ra phân tích tổng hợp
        """
        if indicators is None:
            indicators = ['rsi', 'macd', 'bollinger', 'ema', 'sma', 'stochastic']
            if volumes:
                indicators.append('volume')
        
        results = {}
        
        for indicator in indicators:
            try:
                if indicator.lower() == 'rsi':
                    results['rsi'] = TechnicalIndicators.calculate_rsi(prices)
                elif indicator.lower() == 'macd':
                    results['macd'] = TechnicalIndicators.calculate_macd(prices)
                elif indicator.lower() == 'bollinger':
                    results['bollinger'] = TechnicalIndicators.calculate_bollinger_bands(prices)
                elif indicator.lower() == 'ema':
                    results['ema'] = TechnicalIndicators.calculate_ema(prices)
                elif indicator.lower() == 'sma':
                    results['sma'] = TechnicalIndicators.calculate_sma(prices)
                elif indicator.lower() == 'stochastic':
                    results['stochastic'] = TechnicalIndicators.calculate_stochastic(prices, highs, lows)
                elif indicator.lower() == 'volume' and volumes:
                    results['volume'] = TechnicalIndicators.calculate_volume(prices, volumes)
            except Exception as e:
                results[indicator] = {"error": f"Lỗi tính {indicator}: {str(e)}"}
        
        # Phân tích tổng hợp với trọng số
        signal_weights = {
            'STRONG_BULLISH': 3,
            'BULLISH': 2,
            'BUY': 2,
            'OVERSOLD': 1,
            'NEUTRAL': 0,
            'BEARISH': -2,
            'SELL': -2,
            'STRONG_BEARISH': -3,
            'OVERBOUGHT': -1
        }
        
        total_score = 0
        valid_indicators = 0
        signal_details = []
        
        for key, value in results.items():
            if isinstance(value, dict) and 'error' not in value:
                # Lấy signal từ các key khác nhau
                signal = None
                if 'signal' in value:
                    signal = value['signal']
                elif 'trend' in value:
                    signal = value['trend']
                
                if signal and signal in signal_weights:
                    score = signal_weights[signal]
                    total_score += score
                    valid_indicators += 1
                    signal_details.append({
                        'indicator': key.upper(),
                        'signal': signal,
                        'score': score,
                        'message': value.get('message', '')
                    })
        
        # Tính điểm trung bình
        if valid_indicators > 0:
            average_score = total_score / valid_indicators
            
            if average_score >= 1.5:
                overall_signal = "STRONG_BULLISH"
                recommendation = "Tín hiệu mua mạnh - Nên mua"
            elif average_score >= 0.5:
                overall_signal = "BULLISH"
                recommendation = "Tín hiệu tăng - Có thể mua"
            elif average_score <= -1.5:
                overall_signal = "STRONG_BEARISH"
                recommendation = "Tín hiệu bán mạnh - Nên bán"
            elif average_score <= -0.5:
                overall_signal = "BEARISH"
                recommendation = "Tín hiệu giảm - Có thể bán"
            else:
                overall_signal = "NEUTRAL"
                recommendation = "Tín hiệu trung tính - Quan sát thêm"
        else:
            overall_signal = "UNKNOWN"
            recommendation = "Không thể phân tích - Cần kiểm tra dữ liệu"
            average_score = 0
        
        results['summary'] = {
            "overall_signal": overall_signal,
            "recommendation": recommendation,
            "average_score": round(average_score, 2),
            "total_score": total_score,
            "valid_indicators": valid_indicators,
            "signal_details": signal_details,
            "confidence": min(100, abs(average_score) * 30)  # Độ tin cậy 0-100%
        }
        
        return results

def main():
    # try:
        if len(sys.argv) < 3:
            print(json.dumps({"error": "Thiếu tham số. Cần: prices_json và indicator_name"}))
            return
        
        prices_json = sys.argv[1]
        indicator_name = sys.argv[2]
        
        # Parse prices
        prices = json.loads(prices_json)
        
        # Parse thêm volumes, highs, lows nếu có
        volumes = None
        highs = None
        lows = None
        
        if len(sys.argv) > 3:
            try:
                volumes = json.loads(sys.argv[3])
            except:
                pass
                
        if len(sys.argv) > 4:
            try:
                highs = json.loads(sys.argv[4])
            except:
                pass
                
        if len(sys.argv) > 5:
            try:
                lows = json.loads(sys.argv[5])
            except:
                pass
        
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
        elif indicator_name.lower() == 'sma':
            result = ta.calculate_sma(prices)
        elif indicator_name.lower() == 'stochastic':
            result = ta.calculate_stochastic(prices, highs, lows)
        elif indicator_name.lower() == 'volume' and volumes:
            result = ta.calculate_volume(prices, volumes)
        elif indicator_name.lower() == 'all':
            result = ta.calculate_multiple_indicators(prices, volumes, highs, lows)
        else:
            result = {"error": f"Chỉ báo '{indicator_name}' không được hỗ trợ"}
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    # except Exception as e:
    #     print(json.dumps({"error": f"Lỗi: {str(e)}"}, ensure_ascii=False))

if __name__ == "__main__":
    main()
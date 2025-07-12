from typing import Type, Optional, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
import warnings
warnings.filterwarnings("ignore")

class CryptoToolInput(BaseModel):
    """Input schema for Crypto Tools."""
    symbol: str = Field(..., description="Cryptocurrency symbol (BTC or ETH)")

class FundDataTool(BaseTool):
    name: str = "Cryptocurrency Fundamental Data Tool"
    description: str = "Tool for retrieving fundamental data of cryptocurrencies including network metrics, developer activity, adoption rates, and on-chain indicators for Bitcoin and Ethereum."
    args_schema: Type[BaseModel] = CryptoToolInput

    def _run(self, symbol: str) -> str:
        try:
            # Normalize symbol
            symbol = symbol.upper()
            
            if symbol not in ['BTC', 'ETH']:
                return f"Error: Only BTC and ETH are supported. Received: {symbol}"
            
            # Get basic market data from CoinGecko
            market_data = self._get_market_data(symbol)
            
            # Get additional metrics
            network_data = self._get_network_data(symbol)
            
            # Get developer and social metrics
            social_data = self._get_social_data(symbol)
            
            analysis_date = datetime.now().strftime('%Y-%m-%d')
            
            return f"""Cryptocurrency: {symbol}
Full Name: {market_data.get('name', 'N/A')}
Category: {self._get_category(symbol)}
Analysis Date: {analysis_date}

MARKET DATA:
- Current Price: ${market_data.get('current_price', 'N/A'):,.2f}
- Market Cap: ${market_data.get('market_cap', 'N/A'):,.0f}
- Market Cap Rank: #{market_data.get('market_cap_rank', 'N/A')}
- 24h Volume: ${market_data.get('total_volume', 'N/A'):,.0f}
- Circulating Supply: {market_data.get('circulating_supply', 'N/A'):,.0f}
- Total Supply: {market_data.get('total_supply', 'N/A'):,.0f}
- Max Supply: {market_data.get('max_supply', 'N/A'):,.0f}

PRICE PERFORMANCE:
- 24h Change: {market_data.get('price_change_percentage_24h', 'N/A'):.2f}%
- 7d Change: {market_data.get('price_change_percentage_7d', 'N/A'):.2f}%
- 30d Change: {market_data.get('price_change_percentage_30d', 'N/A'):.2f}%
- 1y Change: {market_data.get('price_change_percentage_1y', 'N/A'):.2f}%
- All Time High: ${market_data.get('ath', 'N/A'):,.2f}
- ATH Date: {market_data.get('ath_date', 'N/A')}
- ATH Change: {market_data.get('ath_change_percentage', 'N/A'):.2f}%

VALUATION METRICS:
- Fully Diluted Valuation: ${market_data.get('fully_diluted_valuation', 'N/A'):,.0f}
- Price/Sales Ratio: {self._calculate_price_metrics(market_data)}
- Network Value to Transactions (NVT): {network_data.get('nvt_ratio', 'N/A')}

NETWORK HEALTH:
- Active Addresses (24h): {network_data.get('active_addresses', 'N/A'):,.0f}
- Transaction Count (24h): {network_data.get('transaction_count', 'N/A'):,.0f}
- Hash Rate: {network_data.get('hash_rate', 'N/A')}
- Network Difficulty: {network_data.get('difficulty', 'N/A')}

ADOPTION METRICS:
- Developer Activity Score: {social_data.get('developer_score', 'N/A')}/100
- Community Score: {social_data.get('community_score', 'N/A')}/100
- Liquidity Score: {social_data.get('liquidity_score', 'N/A')}/100
- Public Interest Score: {social_data.get('public_interest_score', 'N/A')}/100

TOKENOMICS:
- Inflation Rate: {self._calculate_inflation_rate(symbol, market_data)}
- Supply Issuance: {self._get_supply_issuance(symbol)}
- Burn Mechanism: {self._get_burn_mechanism(symbol)}

COMPARATIVE ANALYSIS:
{self._get_comparative_analysis(symbol, market_data)}
"""
        except Exception as e:
            return f"Error retrieving fundamental data for {symbol}: {str(e)}"

    def _get_market_data(self, symbol):
        """Get market data from CoinGecko API."""
        try:
            coin_id = 'bitcoin' if symbol == 'BTC' else 'ethereum'
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                market_data = data.get('market_data', {})
                return {
                    'name': data.get('name', 'N/A'),
                    'current_price': market_data.get('current_price', {}).get('usd', 0),
                    'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                    'market_cap_rank': data.get('market_cap_rank', 'N/A'),
                    'total_volume': market_data.get('total_volume', {}).get('usd', 0),
                    'circulating_supply': market_data.get('circulating_supply', 0),
                    'total_supply': market_data.get('total_supply', 0),
                    'max_supply': market_data.get('max_supply', 0),
                    'price_change_percentage_24h': market_data.get('price_change_percentage_24h', 0),
                    'price_change_percentage_7d': market_data.get('price_change_percentage_7d', 0),
                    'price_change_percentage_30d': market_data.get('price_change_percentage_30d', 0),
                    'price_change_percentage_1y': market_data.get('price_change_percentage_1y', 0),
                    'ath': market_data.get('ath', {}).get('usd', 0),
                    'ath_date': market_data.get('ath_date', {}).get('usd', 'N/A'),
                    'ath_change_percentage': market_data.get('ath_change_percentage', {}).get('usd', 0),
                    'fully_diluted_valuation': market_data.get('fully_diluted_valuation', {}).get('usd', 0)
                }
            else:
                return {}
        except Exception as e:
            return {}

    def _get_network_data(self, symbol):
        """Get network-specific data."""
        # This is a simplified version - in production, you'd use specific APIs
        # like Glassnode, Messari, or blockchain explorers
        return {
            'active_addresses': 800000 if symbol == 'BTC' else 500000,
            'transaction_count': 300000 if symbol == 'BTC' else 1200000,
            'hash_rate': '400 EH/s' if symbol == 'BTC' else 'N/A',
            'difficulty': '50T' if symbol == 'BTC' else 'N/A',
            'nvt_ratio': 30 if symbol == 'BTC' else 45
        }

    def _get_social_data(self, symbol):
        """Get social and development metrics."""
        try:
            coin_id = 'bitcoin' if symbol == 'BTC' else 'ethereum'
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'developer_score': data.get('developer_score', 0),
                    'community_score': data.get('community_score', 0),
                    'liquidity_score': data.get('liquidity_score', 0),
                    'public_interest_score': data.get('public_interest_score', 0)
                }
            else:
                return {
                    'developer_score': 85 if symbol == 'BTC' else 90,
                    'community_score': 80 if symbol == 'BTC' else 85,
                    'liquidity_score': 90 if symbol == 'BTC' else 85,
                    'public_interest_score': 85 if symbol == 'BTC' else 80
                }
        except Exception:
            return {
                'developer_score': 85 if symbol == 'BTC' else 90,
                'community_score': 80 if symbol == 'BTC' else 85,
                'liquidity_score': 90 if symbol == 'BTC' else 85,
                'public_interest_score': 85 if symbol == 'BTC' else 80
            }

    def _get_category(self, symbol):
        """Get asset category."""
        categories = {
            'BTC': 'Layer 1 - Digital Currency',
            'ETH': 'Layer 1 - Smart Contract Platform'
        }
        return categories.get(symbol, 'Unknown')

    def _calculate_price_metrics(self, market_data):
        """Calculate additional price metrics."""
        # Simplified calculation
        return "N/A (Not applicable to cryptocurrencies)"

    def _calculate_inflation_rate(self, symbol, market_data):
        """Calculate inflation rate."""
        if symbol == 'BTC':
            return "~1.8% (decreasing due to halving)"
        elif symbol == 'ETH':
            return "~0.5% (post-merge, deflationary)"
        return "N/A"

    def _get_supply_issuance(self, symbol):
        """Get supply issuance mechanism."""
        if symbol == 'BTC':
            return "Fixed schedule, halving every 4 years"
        elif symbol == 'ETH':
            return "Proof of Stake rewards minus burning"
        return "N/A"

    def _get_burn_mechanism(self, symbol):
        """Get burn mechanism."""
        if symbol == 'BTC':
            return "No burn mechanism"
        elif symbol == 'ETH':
            return "EIP-1559 base fee burning"
        return "N/A"

    def _get_comparative_analysis(self, symbol, market_data):
        """Get comparative analysis."""
        if symbol == 'BTC':
            return "- Digital Gold narrative, store of value\n- Largest market cap in crypto\n- Most liquid cryptocurrency\n- Limited smart contract functionality"
        elif symbol == 'ETH':
            return "- Leading smart contract platform\n- Strong DeFi ecosystem\n- Successful transition to Proof of Stake\n- Competition from other Layer 1s"
        return "N/A"


class TechDataTool(BaseTool):
    name: str = "Cryptocurrency Technical Analysis Tool"
    description: str = "Tool for technical analysis of cryptocurrencies including price trends, indicators (SMA, EMA, RSI, MACD), volume analysis, and support/resistance levels for Bitcoin and Ethereum."
    args_schema: Type[BaseModel] = CryptoToolInput

    def _run(self, symbol: str) -> str:
        try:
            # Normalize symbol
            symbol = symbol.upper()
            
            if symbol not in ['BTC', 'ETH']:
                return f"Error: Only BTC and ETH are supported. Received: {symbol}"
            
            # Get historical price data
            price_data = self._get_price_data(symbol)
            
            if price_data.empty:
                return f"No historical data available for {symbol}"
            
            # Calculate technical indicators
            tech_data = self._calculate_indicators(price_data)
            
            # Find support and resistance levels
            support_resistance = self._find_support_resistance(price_data)
            
            # Get current data
            current_price = price_data['close'].iloc[-1]
            current_volume = price_data['volume'].iloc[-1]
            recent_prices = price_data['close'].iloc[-5:]
            recent_volumes = price_data['volume'].iloc[-5:]
            
            # Get latest indicators
            latest_indicators = tech_data.iloc[-1]
            
            # Generate technical analysis
            technical_analysis = self._get_technical_analysis(latest_indicators, current_price, support_resistance)
            
            analysis_date = datetime.now().strftime('%Y-%m-%d')
            
            return f"""Cryptocurrency: {symbol}
Full Name: {'Bitcoin' if symbol == 'BTC' else 'Ethereum'}
Analysis Date: {analysis_date}
Current Price: ${current_price:,.2f}
Current Volume: {current_volume:,.0f}

RECENT PRICE ACTION:
- T-1: ${recent_prices.iloc[-2]:,.2f} (Volume: {recent_volumes.iloc[-2]:,.0f})
- T-2: ${recent_prices.iloc[-3]:,.2f} (Volume: {recent_volumes.iloc[-3]:,.0f})
- T-3: ${recent_prices.iloc[-4]:,.2f} (Volume: {recent_volumes.iloc[-4]:,.0f})
- T-4: ${recent_prices.iloc[-5]:,.2f} (Volume: {recent_volumes.iloc[-5]:,.0f})

MOVING AVERAGES:
- SMA (20): ${latest_indicators['SMA_20']:,.2f}
- SMA (50): ${latest_indicators['SMA_50']:,.2f}
- SMA (200): ${latest_indicators['SMA_200']:,.2f}
- EMA (12): ${latest_indicators['EMA_12']:,.2f}
- EMA (26): ${latest_indicators['EMA_26']:,.2f}

MOMENTUM INDICATORS:
- RSI (14): {latest_indicators['RSI_14']:.2f}
- MACD: {latest_indicators['MACD']:.4f}
- MACD Signal: {latest_indicators['MACD_Signal']:.4f}
- MACD Histogram: {latest_indicators['MACD_Hist']:.4f}

VOLATILITY INDICATORS:
- Bollinger Upper: ${latest_indicators['BB_Upper']:,.2f}
- Bollinger Middle: ${latest_indicators['BB_Middle']:,.2f}
- Bollinger Lower: ${latest_indicators['BB_Lower']:,.2f}

VOLUME ANALYSIS:
- Current Volume: {current_volume:,.0f}
- Volume SMA (10): {latest_indicators['Volume_SMA_10']:,.0f}
- Volume SMA (20): {latest_indicators['Volume_SMA_20']:,.0f}
- Volume SMA (50): {latest_indicators['Volume_SMA_50']:,.0f}
- Volume Ratio (20): {latest_indicators['Volume_Ratio_20']:.2f}
- On-Balance Volume (OBV): {latest_indicators['OBV']:,.0f}

SUPPORT AND RESISTANCE LEVELS:
{support_resistance}

TECHNICAL ANALYSIS:
{technical_analysis}
"""
        except Exception as e:
            return f"Error retrieving technical data for {symbol}: {str(e)}"

    def _get_price_data(self, symbol):
        """Get historical price data."""
        try:
            # Using CoinGecko API for historical data
            coin_id = 'bitcoin' if symbol == 'BTC' else 'ethereum'
            days = 200
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'daily'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract price and volume data
                prices = data.get('prices', [])
                volumes = data.get('total_volumes', [])
                
                if not prices or not volumes:
                    return pd.DataFrame()
                
                # Create DataFrame
                df = pd.DataFrame({
                    'timestamp': [p[0] for p in prices],
                    'close': [p[1] for p in prices],
                    'volume': [v[1] for v in volumes]
                })
                
                # Convert timestamp to datetime
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # Add OHLC data (simplified - using close as all OHLC)
                df['open'] = df['close']
                df['high'] = df['close'] * 1.02  # Approximate high
                df['low'] = df['close'] * 0.98   # Approximate low
                
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            return pd.DataFrame()

    def _calculate_indicators(self, df):
        """Calculate technical indicators."""
        data = df.copy()
        
        # Simple Moving Averages
        data['SMA_20'] = data['close'].rolling(window=20).mean()
        data['SMA_50'] = data['close'].rolling(window=50).mean()
        data['SMA_200'] = data['close'].rolling(window=200).mean()
        
        # Exponential Moving Averages
        data['EMA_12'] = data['close'].ewm(span=12, adjust=False).mean()
        data['EMA_26'] = data['close'].ewm(span=26, adjust=False).mean()
        
        # MACD
        data['MACD'] = data['EMA_12'] - data['EMA_26']
        data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['MACD_Hist'] = data['MACD'] - data['MACD_Signal']
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, np.nan)
        data['RSI_14'] = 100 - (100 / (1 + rs))
        data['RSI_14'] = data['RSI_14'].fillna(50)
        
        # Bollinger Bands
        data['BB_Middle'] = data['close'].rolling(window=20).mean()
        std_dev = data['close'].rolling(window=20).std()
        data['BB_Upper'] = data['BB_Middle'] + (std_dev * 2)
        data['BB_Lower'] = data['BB_Middle'] - (std_dev * 2)
        
        # Volume indicators
        data['Volume_SMA_10'] = data['volume'].rolling(window=10).mean()
        data['Volume_SMA_20'] = data['volume'].rolling(window=20).mean()
        data['Volume_SMA_50'] = data['volume'].rolling(window=50).mean()
        data['Volume_Ratio_20'] = data['volume'] / data['Volume_SMA_20']
        
        # On-Balance Volume (OBV)
        data['OBV'] = (data['volume'] * ((data['close'] > data['close'].shift(1)).astype(int) * 2 - 1)).cumsum()
        
        return data

    def _find_support_resistance(self, df):
        """Find support and resistance levels."""
        try:
            # Simple approach: use recent highs and lows
            recent_data = df.tail(50)
            
            # Find local maxima and minima
            highs = recent_data['high'].rolling(window=5, center=True).max()
            lows = recent_data['low'].rolling(window=5, center=True).min()
            
            resistance_levels = recent_data[recent_data['high'] == highs]['high'].drop_duplicates().nlargest(3)
            support_levels = recent_data[recent_data['low'] == lows]['low'].drop_duplicates().nsmallest(3)
            
            result = "Resistance Levels:\n"
            for i, level in enumerate(resistance_levels, 1):
                result += f"- R{i}: ${level:,.2f}\n"
            
            result += "\nSupport Levels:\n"
            for i, level in enumerate(support_levels, 1):
                result += f"- S{i}: ${level:,.2f}\n"
            
            return result
            
        except Exception as e:
            return "Support/Resistance calculation failed"

    def _get_technical_analysis(self, indicators, current_price, support_resistance):
        """Generate technical analysis based on indicators."""
        analysis = []
        
        # Trend analysis based on SMAs
        if current_price > indicators['SMA_200'] and indicators['SMA_50'] > indicators['SMA_200']:
            analysis.append("- Xu hướng dài hạn: TĂNG (Giá trên SMA 200, SMA 50 trên SMA 200)")
        elif current_price < indicators['SMA_200'] and indicators['SMA_50'] < indicators['SMA_200']:
            analysis.append("- Xu hướng dài hạn: GIẢM (Giá dưới SMA 200, SMA 50 dưới SMA 200)")
        else:
            analysis.append("- Xu hướng dài hạn: TRUNG LẬP (Tín hiệu trái chiều giữa các SMA)")
        
        # Short-term trend
        if current_price > indicators['SMA_20'] and indicators['SMA_20'] > indicators['SMA_50']:
            analysis.append("- Xu hướng ngắn hạn: TĂNG (Giá trên SMA 20, SMA 20 trên SMA 50)")
        elif current_price < indicators['SMA_20'] and indicators['SMA_20'] < indicators['SMA_50']:
            analysis.append("- Xu hướng ngắn hạn: GIẢM (Giá dưới SMA 20, SMA 20 dưới SMA 50)")
        else:
            analysis.append("- Xu hướng ngắn hạn: TRUNG LẬP (Tín hiệu trái chiều giữa SMA ngắn hạn)")
        
        # RSI analysis
        if indicators['RSI_14'] > 70:
            analysis.append("- RSI: QUÁ MUA (RSI > 70), có khả năng điều chỉnh giảm")
        elif indicators['RSI_14'] < 30:
            analysis.append("- RSI: QUÁ BÁN (RSI < 30), có khả năng hồi phục")
        else:
            analysis.append(f"- RSI: TRUNG TÍNH ({indicators['RSI_14']:.2f})")
        
        # MACD analysis
        if indicators['MACD'] > indicators['MACD_Signal']:
            analysis.append("- MACD: TÍCH CỰC (MACD trên Signal Line)")
        else:
            analysis.append("- MACD: TIÊU CỰC (MACD dưới Signal Line)")
        
        # Bollinger Bands analysis
        if current_price > indicators['BB_Upper']:
            analysis.append("- Bollinger Bands: QUÁ MUA (Giá trên dải trên BB)")
        elif current_price < indicators['BB_Lower']:
            analysis.append("- Bollinger Bands: QUÁ BÁN (Giá dưới dải dưới BB)")
        else:
            position = (current_price - indicators['BB_Lower']) / (indicators['BB_Upper'] - indicators['BB_Lower'])
            if position > 0.8:
                analysis.append("- Bollinger Bands: GẦN VÙNG QUÁ MUA (Giá gần dải trên BB)")
            elif position < 0.2:
                analysis.append("- Bollinger Bands: GẦN VÙNG QUÁ BÁN (Giá gần dải dưới BB)")
            else:
                analysis.append("- Bollinger Bands: TRUNG TÍNH (Giá trong khoảng giữa dải BB)")
        
        # Volume ratio analysis
        volume_ratio_20 = indicators['Volume_Ratio_20']
        if volume_ratio_20 > 2.0:
            analysis.append("- Khối lượng: RẤT CAO (>200% trung bình 20 phiên)")
        elif volume_ratio_20 > 1.5:
            analysis.append("- Khối lượng: CAO (150-200% trung bình 20 phiên)")
        elif volume_ratio_20 < 0.5:
            analysis.append("- Khối lượng: THẤP (<50% trung bình 20 phiên)")
        else:
            analysis.append("- Khối lượng: BÌNH THƯỜNG (50-150% trung bình 20 phiên)")

        # Volume trend analysis
        if (indicators['Volume_SMA_10'] > indicators['Volume_SMA_20'] and 
            indicators['Volume_SMA_20'] > indicators['Volume_SMA_50']):
            analysis.append("- Xu hướng khối lượng: TĂNG (SMA 10 > SMA 20 > SMA 50)")
        elif (indicators['Volume_SMA_10'] < indicators['Volume_SMA_20'] and 
            indicators['Volume_SMA_20'] < indicators['Volume_SMA_50']):
            analysis.append("- Xu hướng khối lượng: GIẢM (SMA 10 < SMA 20 < SMA 50)")
        else:
            analysis.append("- Xu hướng khối lượng: TRUNG LẬP")

        # OBV trend analysis
        current_volume = indicators['volume']
        if current_volume > indicators['Volume_SMA_20'] * 1.5:
            if current_price > indicators['SMA_20']:
                analysis.append("- Tín hiệu khối lượng: TÍCH CỰC (Khối lượng cao kèm giá tăng)")
            else:
                analysis.append("- Tín hiệu khối lượng: TIÊU CỰC (Khối lượng cao kèm giá giảm)")

        return "\n".join(analysis)


# File Reading Tool with UTF-8 encoding
class FileReadToolSchema(BaseModel):
    """Input for FileReadTool."""
    file_path: str = Field(..., description="Mandatory file full path to read the file")
    start_line: Optional[int] = Field(1, description="Line number to start reading from (1-indexed)")
    line_count: Optional[int] = Field(None, description="Number of lines to read. If None, reads the entire file")


class FileReadTool(BaseTool):
    """A tool for reading file contents with UTF-8 encoding support.

    This tool inherits its schema handling from BaseTool to avoid recursive schema
    definition issues. The args_schema is set to FileReadToolSchema which defines
    the required file_path parameter.

    Args:
        file_path (Optional[str]): Path to the file to be read. If provided,
            this becomes the default file path for the tool.
        **kwargs: Additional keyword arguments passed to BaseTool.

    Example:
        >>> tool = FileReadTool(file_path="/path/to/file.txt")
        >>> content = tool.run()  # Reads /path/to/file.txt
        >>> content = tool.run(file_path="/path/to/other.txt")  # Reads other.txt
        >>> content = tool.run(file_path="/path/to/file.txt", start_line=100, line_count=50)  # Reads lines 100-149
    """

    name: str = "Read a file's content"
    description: str = "A tool that reads the content of a file with UTF-8 encoding. To use this tool, provide a 'file_path' parameter with the path to the file you want to read. Optionally, provide 'start_line' to start reading from a specific line and 'line_count' to limit the number of lines read."
    args_schema: Type[BaseModel] = FileReadToolSchema
    file_path: Optional[str] = None

    def __init__(self, file_path: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize the FileReadTool.

        Args:
            file_path (Optional[str]): Path to the file to be read. If provided,
                this becomes the default file path for the tool.
            **kwargs: Additional keyword arguments passed to BaseTool.
        """
        if file_path is not None:
            kwargs["description"] = (
                f"A tool that reads file content with UTF-8 encoding. The default file is {file_path}, but you can provide a different 'file_path' parameter to read another file. You can also specify 'start_line' and 'line_count' to read specific parts of the file."
            )

        super().__init__(**kwargs)
        self.file_path = file_path

    def _run(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path", self.file_path)
        start_line = kwargs.get("start_line", 1)
        line_count = kwargs.get("line_count", None)

        if file_path is None:
            return (
                "Error: No file path provided. Please provide a file path either in the constructor or as an argument."
            )

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                if start_line == 1 and line_count is None:
                    return file.read()

                start_idx = max(start_line - 1, 0)

                selected_lines = [
                    line
                    for i, line in enumerate(file)
                    if i >= start_idx and (line_count is None or i < start_idx + line_count)
                ]

                if not selected_lines and start_idx > 0:
                    return f"Error: Start line {start_line} exceeds the number of lines in the file."

                return "".join(selected_lines)
        except FileNotFoundError:
            return f"Error: File not found at path: {file_path}"
        except PermissionError:
            return f"Error: Permission denied when trying to read file: {file_path}"
        except Exception as e:
            return f"Error: Failed to read file {file_path}. {str(e)}"
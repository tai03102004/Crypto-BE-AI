import axios from 'axios';
// AI Analysis service 
class AIAnalysisService {
    constructor() {
        this.baseURL = "https://api.intelligence.io.solutions/api/v1";
    }

    async analyzeMarketData(cryptoData, technicalIndicators, historicalData) {
        try {
            this.apiKey = process.env.IOINTELLIGENCE_API_KEY;

            if (!this.apiKey) {
                throw new Error('API key is not set');
            }
            const prompt = this.createEnhancedAnalysisPrompt(cryptoData, technicalIndicators, historicalData);

            const response = await axios.post(`${this.baseURL}/chat/completions`, {
                model: "meta-llama/Llama-3.3-70B-Instruct",
                messages: [{
                        role: 'system',
                        content: `Bạn là một chuyên gia phân tích cryptocurrency và trading. 
                        Hãy đưa ra phân tích chi tiết và CỤ THỂ các tín hiệu giao dịch với giá rõ ràng.
                        Luôn bao gồm: Entry Point, Stop Loss, Take Profit, và Timeframe.
                        Phân tích dựa trên cả technical analysis và market context.`
                    },
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                stream: false,
                max_completion_tokens: 500,
                temperature: 0.3
            }, {
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json'
                }
            });

            const aiAnalysis = response.data.choices[0].message.content;

            // Parse AI response to extract trading signals
            const tradingSignals = this.extractTradingSignals(aiAnalysis, cryptoData);

            return {
                analysis: aiAnalysis,
                tradingSignals: tradingSignals
            };

        } catch (error) {
            console.error('Error in enhanced AI analysis:', error.message);
            return {
                analysis: 'Không thể thực hiện phân tích AI tại thời điểm này.',
                tradingSignals: []
            };
        }
    }

    createEnhancedAnalysisPrompt(cryptoData, indicators, historicalData) {
        const formattedHistoricalData = this.formatHistoricalData(historicalData);
        return `
            PHÂN TÍCH CRYPTO VÀ TÍN HIỆU GIAO DỊCH

            === DỮ LIỆU HIỆN TẠI ===
            ${JSON.stringify(cryptoData, null, 2)}

            === CHỈ BÁO KỸ THUẬT ===
            ${JSON.stringify(indicators, null, 2)}

            === DỮ LIỆU LỊCH SỬ 30 NGÀY ===
            ${formattedHistoricalData ? JSON.stringify(formattedHistoricalData, null, 2) : 'Không có dữ liệu lịch sử'}

            === YÊU CẦU PHÂN TÍCH ===

            1. **PHÂN TÍCH XU HƯỚNG**:
            - Xu hướng ngắn hạn (1-3 ngày)
            - Xu hướng trung hạn (1-2 tuần)
            - Xu hướng dài hạn (1-3 tháng)

            2. **ĐÁNH GIÁ CHỈ BÁO KỸ THUẬT**:
            - RSI: Vùng quá mua/quá bán
            - MACD: Tín hiệu mua/bán
            - Support/Resistance levels
            - Sử dụng đường EMA phân tích 

            3. **TÍN HIỆU GIAO DỊCH CỤ THỂ** (cho từng coin):
            - **Action**: BUY/SELL/HOLD
            - **Entry Point**: Giá vào lệnh cụ thể ($)
            - **Stop Loss**: Giá cắt lỗ ($) và % risk
            - **Take Profit 1**: Mục tiêu chốt lời ngắn hạn ($)
            - **Take Profit 2**: Mục tiêu chốt lời dài hạn ($)
            - **Timeframe**: Khung thời gian hold (hours/days/weeks)
            - **Position Size**: Khuyến nghị % portfolio
            - **Risk Level**: LOW/MEDIUM/HIGH

            4. **CẢNH BÁO RỦI RO**:
            - Điều kiện hủy lệnh
            - Sự kiện có thể ảnh hưởng
            - Mức độ tin cậy của tín hiệu

            5. **MARKET CONTEXT**:
            - Tình hình thị trường chung
            - Factors có thể ảnh hưởng
            - Correlation với Bitcoin, Ethereum

            Hãy trả lời bằng tiếng Việt, chi tiết và cụ thể với số liệu rõ ràng (minh chứng đúng).
            Tránh sử dụng từ ngữ chung chung, hãy đi vào chi tiết cụ thể.
            Tránh lặp lại thông tin, hãy cung cấp phân tích mới mẻ và sâu sắc.
            Trình bày rõ ràng, dễ hiểu và có cấu trúc logic, gạch đầu dòng và thụt lề đúng.
        `;
    }

    formatHistoricalData(historicalData) {
        if (!historicalData) return 'Không có dữ liệu lịch sử';

        const formatted = {};

        Object.keys(historicalData).forEach(coinId => {
            const data = historicalData[coinId];
            if (data && data.prices) {
                const prices = data.prices.slice(-7); // 7 ngày gần nhất cho AI
                formatted[coinId] = {
                    recent_prices: prices.map(([timestamp, price]) => ({
                        date: new Date(timestamp).toISOString().split('T')[0],
                        price: price
                    })),
                    price_change_7d: this.calculatePriceChange(prices),
                    volatility: this.calculateVolatility(prices)
                };
            }
        });

        return JSON.stringify(formatted, null, 2);
    }

    calculatePriceChange(prices) {
        if (prices.length < 2) return 0;
        const firstPrice = prices[0][1];
        const lastPrice = prices[prices.length - 1][1];
        return ((lastPrice - firstPrice) / firstPrice * 100).toFixed(2);
    }

    calculateVolatility(prices) {
        if (prices.length < 2) return 0;
        const returns = [];
        for (let i = 1; i < prices.length; i++) {
            const return_rate = (prices[i][1] - prices[i - 1][1]) / prices[i - 1][1];
            returns.push(return_rate);
        }

        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length;
        return Math.sqrt(variance).toFixed(4);
    }


    extractTradingSignals(aiAnalysis, cryptoData) {
        const signals = [];
        const coins = Object.keys(cryptoData);

        coins.forEach(coinId => {
            const currentPrice = cryptoData[coinId].usd;

            // Regex patterns to extract trading signals from AI response
            const entryPattern = new RegExp(`${coinId}.*?entry.*?\\$?([0-9,]+(?:\\.[0-9]+)?)`, 'i');
            const stopLossPattern = new RegExp(`${coinId}.*?stop.*?loss.*?\\$?([0-9,]+(?:\\.[0-9]+)?)`, 'i');
            const takeProfitPattern = new RegExp(`${coinId}.*?take.*?profit.*?\\$?([0-9,]+(?:\\.[0-9]+)?)`, 'i');
            const actionPattern = new RegExp(`${coinId}.*?(BUY|SELL|HOLD)`, 'i');

            const entryMatch = aiAnalysis.match(entryPattern);
            const stopLossMatch = aiAnalysis.match(stopLossPattern);
            const takeProfitMatch = aiAnalysis.match(takeProfitPattern);
            const actionMatch = aiAnalysis.match(actionPattern);

            if (actionMatch) {
                const signal = {
                    coin: coinId,
                    action: actionMatch[1].toUpperCase(),
                    currentPrice: currentPrice,
                    entryPoint: entryMatch ? parseFloat(entryMatch[1].replace(',', '')) : currentPrice,
                    stopLoss: stopLossMatch ? parseFloat(stopLossMatch[1].replace(',', '')) : null,
                    takeProfit: takeProfitMatch ? parseFloat(takeProfitMatch[1].replace(',', '')) : null,
                    timestamp: new Date(),
                    confidence: this.calculateConfidence(aiAnalysis, coinId)
                };

                // Calculate risk/reward ratio
                if (signal.stopLoss && signal.takeProfit) {
                    const risk = Math.abs(signal.entryPoint - signal.stopLoss);
                    const reward = Math.abs(signal.takeProfit - signal.entryPoint);
                    signal.riskRewardRatio = (reward / risk).toFixed(2);
                }

                signals.push(signal);
            }
        });

        return signals;
    }

    calculateConfidence(aiAnalysis, coinId) {
        // Simple confidence calculation based on keywords
        const confidenceKeywords = [
            'chắc chắn', 'rõ ràng', 'mạnh mẽ', 'tin cậy', 'đáng tin',
            'rủi ro thấp', 'tín hiệu tốt', 'xu hướng rõ', 'support mạnh'
        ];

        const lowConfidenceKeywords = [
            'không chắc', 'rủi ro cao', 'biến động', 'thận trọng', 'cảnh báo',
            'khó dự đoán', 'không rõ', 'chưa chắc chắn'
        ];

        let confidence = 50; // Base confidence

        confidenceKeywords.forEach(keyword => {
            if (aiAnalysis.toLowerCase().includes(keyword)) {
                confidence += 10;
            }
        });

        lowConfidenceKeywords.forEach(keyword => {
            if (aiAnalysis.toLowerCase().includes(keyword)) {
                confidence -= 10;
            }
        });

        return Math.max(0, Math.min(100, confidence));
    }
    calculateConfidence(aiAnalysis, coinId) {
        // Simple confidence calculation based on keywords
        const confidenceKeywords = [
            'chắc chắn', 'rõ ràng', 'mạnh mẽ', 'tin cậy', 'đáng tin',
            'rủi ro thấp', 'tín hiệu tốt', 'xu hướng rõ', 'support mạnh'
        ];

        const lowConfidenceKeywords = [
            'không chắc', 'rủi ro cao', 'biến động', 'thận trọng', 'cảnh báo',
            'khó dự đoán', 'không rõ', 'chưa chắc chắn'
        ];

        let confidence = 50; // Base confidence

        confidenceKeywords.forEach(keyword => {
            if (aiAnalysis.toLowerCase().includes(keyword)) {
                confidence += 10;
            }
        });

        lowConfidenceKeywords.forEach(keyword => {
            if (aiAnalysis.toLowerCase().includes(keyword)) {
                confidence -= 10;
            }
        });

        return Math.max(0, Math.min(100, confidence));
    }
}

export default new AIAnalysisService();
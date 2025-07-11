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
                        content: `
                            You are a professional cryptocurrency trading analyst.
                            Use technical analysis + market context to provide detailed, high-quality trade setups.
                            Output must be concise, clear, and structured.`
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
            DATA:
                - Current Price Data:
                ${JSON.stringify(cryptoData, null, 2)}
                
                - Technical Indicators:
                ${JSON.stringify(indicators, null, 2)}
                
                - 30-Day Historical Data:
                ${formattedHistoricalData || 'No data available'}
            
            TASK:
                Analyze ALL crypto assets provided in the data and generate trade setups for EACH coin.
                
                **IMPORTANT FORMATTING RULES:**
                - Use clear section headers with emojis
                - Keep explanations concise (max 2 sentences per point)
                - Use bullet points for key data
                - Structure response in exactly this format:
                
                ## 📊 Market Overview
                Brief 1-2 sentence summary of current market conditions.
                
                ## 🎯 Trade Setup: [COIN_NAME]
                **Signal:** [BUY/SELL/HOLD] 
                **Confidence:** [X%]
                
                ### 📈 Technical Analysis
                • **Trend:** [Short description]
                • **RSI:** [Value] - [Interpretation]
                • **MACD:** [Interpretation]
                • **Support/Resistance:** [Levels]
                
                ### 💰 Trade Parameters
                • **Entry:** $[price]
                • **Stop Loss:** $[price] 
                • **Take Profit 1:** $[price]
                • **Take Profit 2:** $[price]
                • **Position Size:** [X%]
                • **Timeframe:** [duration]
                
                ### ⚠️ Risk Assessment
                • **Risk Level:** [Low/Medium/High]
                • **Key Risks:** [Brief points]
                • **Invalidation:** [Conditions]
                
                Keep each section concise and data-driven. Maximum 300 words total.
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
            'confident',
            'clear signal',
            'strong trend',
            'reliable',
            'low risk',
            'confirmed setup',
            'high probability',
            'strong support',
            'momentum building',
            'bullish confirmation'
        ];

        const lowConfidenceKeywords = [
            'uncertain',
            'high risk',
            'volatile',
            'caution advised',
            'weak signal',
            'unconfirmed',
            'hard to predict',
            'no clear direction',
            'unstable conditions',
            'reversal warning'
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
            'certain',
            'clear',
            'strong',
            'reliable',
            'trustworthy',
            'low risk',
            'good signal',
            'clear trend',
            'strong support'
        ];

        const lowConfidenceKeywords = [
            'uncertain',
            'high risk',
            'volatile',
            'cautious',
            'warning',
            'unpredictable',
            'unclear',
            'not yet confirmed'
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
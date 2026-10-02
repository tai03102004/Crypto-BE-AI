import axios from 'axios';
import {
    predictLSTM
} from "./LSTMForecast.service.js";

// AI Analysis service 
class AIAnalysisService {
    constructor() {
        this.baseURL = "https://api.intelligence.io.solutions/api/v1";
        this.timeout = 60000;
    }

    async analyzeMarketData(cryptoData, technicalIndicators, historicalData) {
        try {
            this.apiKey = process.env.IOINTELLIGENCE_API_KEY;

            if (!this.apiKey) {
                throw new Error('API key is not set');
            }

            const [lstmForecast, formattedHistoricalData] = await Promise.all([
                predictLSTM(),
                this.formatHistoricalDataAsync(historicalData)
            ]);

            // console.log("🔮 LSTM forecast:", lstmForecast);

            const prompt = this.createOptimizedPrompt(cryptoData, technicalIndicators, formattedHistoricalData, lstmForecast);

            const response = await axios.post(`${this.baseURL}/chat/completions`, {
                model: "meta-llama/Llama-3.3-70B-Instruct",
                messages: [{
                        role: 'system',
                        content: `You are a professional cryptocurrency trading analyst. 
                        Provide concise, structured trade setups. 
                        Be direct and data-driven. Maximum 350 words.`
                    },
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                stream: false,
                max_completion_tokens: 400,
                temperature: 0.3,
                top_p: 0.9,
                frequency_penalty: 0.1

            }, {
                headers: {
                    'Authorization': `Bearer ${this.apiKey}`,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout: this.timeout,
                maxRedirects: 3,
                validateStatus: function (status) {
                    return status >= 200 && status < 300;
                }
            });

            const aiAnalysis = response.data.choices[0].message.content;

            return {
                analysis: aiAnalysis,
                lstmForecast
            };

        } catch (error) {
            console.error('Error in enhanced AI analysis:', error.message);
            return {
                analysis: 'Không thể thực hiện phân tích AI tại thời điểm này.',
            };
        }
    }

    createOptimizedPrompt(cryptoData, indicators, historicalData, lstmForecast) {
        const mlForecastText = `
            === Machine Learning Forecast ===
            [Bitcoin]
            - Next Day: $${lstmForecast.btc.next_day.toFixed(2)}
            - 7-Day:
            ${lstmForecast.btc.multi_step.map((p, i) => `Day ${i+1}: $${p.toFixed(2)}`).join("\n")}

            [Ethereum]
            - Next Day: $${lstmForecast.eth.next_day.toFixed(2)}
            - 7-Day:
            ${lstmForecast.eth.multi_step.map((p, i) => `Day ${i+1}: $${p.toFixed(2)}`).join("\n")}
        `;

        return `
            ANALYSIS DATA (Use for analysis but DO NOT include in response):
            ===================================================================
            Current Prices: ${JSON.stringify(cryptoData, null, 2)}
            Technical Indicators: ${JSON.stringify(indicators, null, 2)}
            Historical Data (30 days): ${historicalData|| 'No data available'}
            ${mlForecastText}
            ===================================================================
            TASK:
            Generate concise, professional trade setups for each coin using the data above.

            **ANALYSIS REQUIREMENTS:**
            - Use historical price patterns to identify trends
            - Incorporate ML forecast predictions in your strategy
            - Consider technical indicators for entry/exit points
            - Factor in market sentiment and volatility **only if such data is available; otherwise prioritize technical indicators and ML forecast**

            **RESPONSE FORMAT (EXACTLY):**
            
            ## 📊 Market Overview
            Brief 1-2 sentence summary of current market conditions based on data analysis.
            
            ## 🎯 Trade Setup: [COIN_NAME]
            **Signal:** [BUY/SELL/HOLD] 
            **Confidence:** [X%] (based on strength of technical signals + alignment with ML forecast.
                Use scale: 
                - 70–80% = moderate confidence (some alignment)
                - 80–90% = strong confidence
                - >90% = very strong confidence, high confluence)
            
            ### 📈 Technical Analysis
            • **Trend:** [Analysis based on historical data]
            • **RSI:** [Value] - [Interpretation]
            • **MACD:** [Interpretation]
            • **Support/Resistance:** [Key levels from historical data]
            • **Price Action:** [Pattern analysis]
            
            ### 💰 Trade Parameters
            • **Entry:** $[price] (based on technical levels)
            • **Stop Loss:** $[price] (risk management)
            • **Take Profit 1:** $[price] (conservative target)
            • **Take Profit 2:** $[price] (aggressive target)
            • **Position Size:** [X%] of portfolio
            • **Timeframe:** [duration]
            
            ### 🤖 ML Forecast Integration
            • **Short-term Outlook:** [Based on ML predictions]
            • **Strategy Alignment:** [How forecast supports trade setup]
            
            ### ⚠️ Risk Assessment
            • **Risk Level:** [Low/Medium/High]
            • **Key Risks:** [Market factors to watch]
            • **Invalidation:** [Conditions that cancel setup]

            **CONSTRAINTS:**
            - Maximum 350 words total
            - Focus on actionable insights
            - Use data-driven analysis only
            - DO NOT repeat raw data in response
        `;
    }

    async formatHistoricalDataAsync(historicalData) {
        return new Promise((resolve) => {
            if (!historicalData) {
                resolve('No historical data');
                return;
            }

            const formatted = {};
            const coins = Object.keys(historicalData);

            coins.forEach(coinId => {
                const data = historicalData[coinId];
                if (data && data.prices) {
                    const prices = data.prices.slice(-5);
                    formatted[coinId] = {
                        recent_trend: this.calculateTrend(prices),
                        volatility: this.calculateVolatility(prices),
                        price_change: this.calculatePriceChange(prices)
                    };
                }
            });

            resolve(JSON.stringify(formatted));
        });
    }

    calculateTrend(prices) {
        if (prices.length < 2) return 'neutral';
        const firstPrice = prices[0][1];
        const lastPrice = prices[prices.length - 1][1];
        const change = ((lastPrice - firstPrice) / firstPrice * 100);

        if (change > 2) return 'bullish';
        if (change < -2) return 'bearish';
        return 'neutral';
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

    static cache = new Map();
    static cacheTimeout = 5 * 60 * 1000; // 5 phút

    async getCachedAnalysis(cacheKey) {
        const cached = AIAnalysisService.cache.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < AIAnalysisService.cacheTimeout) {
            return cached.data;
        }
        return null;
    }

    setCachedAnalysis(cacheKey, data) {
        AIAnalysisService.cache.set(cacheKey, {
            data: data,
            timestamp: Date.now()
        });
    }
}

export default new AIAnalysisService();
import axios from 'axios';
import cron from 'node-cron';
import {
    spawn
} from 'child_process';
import path from 'path';


import {
    Telegraf
} from 'telegraf';
import coinGeckoService from './CoinGecko.service.js';
import {
    fileURLToPath
} from 'url';
/**
 * AI Agent Service Class
 */

const __filename = fileURLToPath(
    import.meta.url);
const __dirname = path.dirname(__filename);
class AIAnalysisService {

    constructor() {
        this.pythonScriptPath = path.join(__dirname, '../python/technical_indicators.py');
        this.priceCache = new Map();
        this.bot = null;
        this.aiAgent = null;
        this.cronJobs = [];
        this.isRunning = false;
        this.previousPrices = {};
        this.defaultConfig = {
            alertThresholds: {
                priceChange: 5,
                volume: 20,
                rsiOverbought: 70,
                rsiOversold: 30
            },
            checkInterval: '*/30 * * * *',
            quickCheckInterval: '*/5 * * * *',
            supportedCoins: ['bitcoin', 'ethereum'],
            aiInstructions: 'You are a cryptocurrency analysis expert. Analyze the market data and provide an accurate and concise insight in English.',
        };
    }

    /**
     * Initialize service with configuration
     * @param {Object} config - Config service
     */
    init(config) {
        this.config = {
            ...this.defaultConfig,
            ...config
        };

        // Khởi tạo AI Agent
        this.aiAgent = {
            name: this.config.aiName || "Crypto Analysis Agent",
            instructions: this.config.aiInstructions || "You are an assistant professional cryptocurrency trading analyst.",
            model: this.config.aiModel || "meta-llama/Llama-3.3-70B-Instruct",
            apiKey: this.config.aiApiKey || 'io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6Ijc1NjNiM2I4LWU3OTEtNGFjMi04YTY1LTg0ZjU3ODkyNDM5NSIsImV4cCI6NDkwNTIwMjQ4Nn0.hYGWdOQVRdbhUYF_IQD1Qd-HNOg7i9NRmhj1PMkDHtS-hK5C0JMqVBF8O31URDswDEVdQIdM2p3is-TXpwxjRw',
            baseUrl: this.config.aiBaseUrl || "https://api.intelligence.io.solutions/api/v1",
            headers: {
                'Authorization': `Bearer ${this.config.aiApiKey}`,
                'Content-Type': 'application/json'
            }
        };

        // Khởi tạo Telegram Bot
        this.bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);

        console.log('✅ AIAnalysisService initialized');
        return this;
    }

    /**
     * Data Analysis with AI
     * @param {string} data - Data to be analyzed
     * @returns {Promise<string>} - Analysis results
     */
    async analyzeWithAI(data) {
        try {
            const payload = {
                model: this.aiAgent.model,
                messages: [{
                        role: 'system',
                        content: this.aiAgent.instructions
                    },
                    {
                        role: 'user',
                        content: data
                    }
                ],
                max_tokens: 500,
                temperature: 0.7
            };

            const response = await axios.post(
                `${this.aiAgent.baseUrl}/chat/completions`,
                payload, {
                    headers: this.aiAgent.headers,
                    timeout: 30000
                }
            );

            return response.data.choices[0].message.content;
        } catch (error) {
            console.error('❌ AI Analysis Error:', error.message);
            return 'Errors in AI data analysis';
        }
    }

    /**
     * Check warning conditions
     * @param {string} symbol 
     * @param {number} currentPrice 
     * @param {number} priceChange24h 
     * @param {Object} techData 
     * @returns {boolean}
     */
    shouldSendAlert(symbol, currentPrice, priceChange24h, techData) {
        const {
            alertThresholds
        } = this.config;

        return [
            Math.abs(priceChange24h) > alertThresholds.priceChange,
            techData.rsi > alertThresholds.rsiOverbought,
            techData.rsi < alertThresholds.rsiOversold,
            Math.abs(techData.macd) > 5
        ].some(condition => condition);
    }

    /**
     * Warning message format
     * @param {string} symbol 
     * @param {Object} priceData 
     * @param {Object} techData 
     * @param {string} aiAnalysis 
     * @returns {string} 
     */
    formatAlertMessage(symbol, priceData, techData, aiAnalysis) {
        const coinData = priceData[symbol];
        const emoji = coinData.usd_24h_change > 0 ? '🟢' : '🔴';
        const trend = coinData.usd_24h_change > 0 ? 'BULLISH' : 'BEARISH';
        const coinName = symbol.charAt(0).toUpperCase() + symbol.slice(1);

        return `
            ${emoji} <b>Warming ${coinName.toUpperCase()}</b>

            💰 <b>Price:</b> $${coinData.usd.toFixed(2)}
            📊 <b>24h:</b> ${coinData.usd_24h_change.toFixed(2)}% (${trend})
            📈 <b>Volume:</b> $${(coinData.usd_24h_vol / 1000000).toFixed(2)}M
            💎 <b>Cap:</b> $${(coinData.usd_market_cap / 1000000000).toFixed(2)}B

            📋 <b>Technical indicators:</b>
            • RSI: ${techData.rsi} ${techData.rsi > 70 ? '🔴' : techData.rsi < 30 ? '🟢' : '🟡'}
            • MACD: ${techData.macd.toFixed(2)}
            • EMA: $${techData.ema.toFixed(2)}
            • SMA: $${techData.sma.toFixed(2)}
            • Volume: $${techData.volume.toFixed(2)} ${techData.volume_signal === 'HIGH' ? '🔴' : '🟢'}
            • Bollinger Bands: $${techData.bollinger.upper.toFixed(2)} / $${techData.bollinger.lower.toFixed(2)} / $${techData.bollinger.middle.toFixed(2)}
            • Stochastic: K=${techData.stochastic.k} D=${techData.stochastic.d} ${techData.stochastic.signal === 'OVERBOUGHT' ? '🔴' : techData.stochastic.signal === 'OVERSOLD' ? '🟢' : '🟡'}
            • Summary: ${techData.summary.overall_signal} - ${techData.summary.recommendation} (${techData.summary.confidence}%)

            🤖 <b>AI Analysis:</b>
            ${aiAnalysis}

            ⏰ <i>${new Date().toLocaleString('vi-VN')}</i>
        `.trim();
    }

    /**
     * Send Message Telegram
     * @param {string} message 
     * @param {string} chatId 
     */
    async sendTelegramMessage(message, chatId = null) {
        try {
            await this.bot.telegram.sendMessage(
                chatId || this.config.chatId,
                message, {
                    parse_mode: 'HTML',
                    disable_web_page_preview: true
                }
            );
            console.log('✅ Message sent successfully');
        } catch (error) {
            console.error('❌ Telegram send error:', error.message);
            throw new Error('Telegram message sending error');
        }
    }

    async runPythonScript(prices, indicator, volumes = null, highs = null, lows = null) {
        return new Promise((resolve, reject) => {
            const args = [
                this.pythonScriptPath,
                JSON.stringify(prices),
                indicator
            ];

            if (volumes) {
                args.push(JSON.stringify(volumes));
            }

            if (highs) {
                args.push(JSON.stringify(highs));
            }

            if (lows) {
                args.push(JSON.stringify(lows));
            }

            const pythonProcess = spawn('python', args);

            let dataString = '';
            let errorString = '';

            pythonProcess.stdout.on('data', (data) => {
                dataString += data.toString();
                console.log("Python Output:", dataString);
            });

            pythonProcess.stderr.on('data', (data) => {
                errorString += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code === 0) {
                    try {
                        const result = JSON.parse(dataString);
                        resolve(result);
                    } catch (error) {
                        reject(new Error(`Error parse JSON: ${error.message}`));
                    }
                } else {
                    reject(new Error(`Python script failed: ${errorString}`));
                }
            });

            pythonProcess.on('error', (error) => {
                reject(new Error(`Error run Python: ${error.message}`));
            });
        });
    }

    async getPriceData(symbol) {
        try {
            if (this.priceCache.has(symbol)) {
                const cachedData = this.priceCache.get(symbol);
                if (Date.now() - cachedData.timestamp < 3600000) {
                    return cachedData.data;
                } else {
                    console.log(`🔄 Cập nhật cache cho ${symbol}`)
                    this.priceCache.delete(symbol);
                }
            }

            const infoCoin = await coinGeckoService.getAllInfoCoin([symbol]);
            const priceCoin = await coinGeckoService.getHistoricalDataForCoins(symbol, 100);
            const prices = priceCoin[symbol].prices.map(([_, price]) => price);

            const dataCoin = {};

            for (let i = 0; i < infoCoin.length; i++) {
                const coin = infoCoin[i];
                dataCoin[symbol] = {
                    current_price: coin.current_price,
                    volumes: coin.total_volume,
                    highs: coin.high_24h,
                    lows: coin.low_24h,
                    prices: prices
                }
            }

            this.priceCache.set(symbol, {
                data: dataCoin,
                timestamp: Date.now()
            });

            return dataCoin;

        } catch (error) {
            throw new Error(`Lỗi lấy dữ liệu giá: ${error.message}`);
        }
    }


    /**
     * Calculating single technical indicator
     * @param {string} symbol - Coin symbol
     * @param {string} indicator - Technical indicator name
     * @returns {Promise<Object>} - Calculation result
     * */
    async calculateSingleIndicator(symbol, indicator) {
        try {
            const priceData = await this.getPriceData(symbol);

            const result = await this.runPythonScript(
                priceData.prices,
                indicator,
                priceData.volumes,
                priceData.highs,
                priceData.lows
            );

            return result;
        } catch (error) {
            throw new Error(`Lỗi tính ${indicator}: ${error.message}`);
        }
    }

    /**
     * Calculate all technical indicators
     * @param {string} symbol - Coin symbol
     * @returns {Promise<Object>} - Calculation result
     * */
    async calculateAllIndicators(symbol) {
        try {
            const priceData = await this.getPriceData([symbol]);

            const result = await this.runPythonScript(
                priceData[symbol].prices,
                'all',
                priceData[symbol].volumes,
                priceData[symbol].highs,
                priceData[symbol].lows
            );

            return result;
        } catch (error) {
            throw new Error(`Error calculating all indicators: ${error.message}`);
        }
    }


    async getTechnicalIndicators(symbol) {
        try {
            const allIndicators = await this.calculateAllIndicators([symbol]);

            if (allIndicators.error) {
                throw new Error(allIndicators.error);
            }

            const formattedResult = {
                // RSI
                rsi: allIndicators.rsi?.value || 50,
                rsi_signal: allIndicators.rsi?.signal || 'NEUTRAL',
                rsi_message: allIndicators.rsi?.message || '',

                // MACD
                macd: allIndicators.macd?.macd || 0,
                macd_signal: allIndicators.macd?.signal || 0,
                macd_histogram: allIndicators.macd?.histogram || 0,
                macd_trend: allIndicators.macd?.trend || 'NEUTRAL',
                macd_message: allIndicators.macd?.message || '',

                // EMA
                ema: allIndicators.ema?.ema_value || 45000,
                ema_signal: allIndicators.ema?.signal || 'NEUTRAL',
                ema_message: allIndicators.ema?.message || '',

                // SMA
                sma: allIndicators.sma?.sma_value || 45000,
                sma_signal: allIndicators.sma?.signal || 'NEUTRAL',
                sma_message: allIndicators.sma?.message || '',

                // Volume
                volume: allIndicators.volume?.current_volume || 1000000000,
                volume_signal: allIndicators.volume?.signal || 'NEUTRAL',
                volume_message: allIndicators.volume?.message || '',

                // Bollinger Bands
                bollinger: {
                    upper: allIndicators.bollinger?.upper_band || 50000,
                    lower: allIndicators.bollinger?.lower_band || 40000,
                    middle: allIndicators.bollinger?.middle_band || 45000,
                    signal: allIndicators.bollinger?.signal || 'NEUTRAL',
                    message: allIndicators.bollinger?.message || ''
                },

                // Stochastic
                stochastic: {
                    k: allIndicators.stochastic?.k_percent || 50,
                    d: allIndicators.stochastic?.d_percent || 50,
                    signal: allIndicators.stochastic?.signal || 'NEUTRAL',
                    message: allIndicators.stochastic?.message || ''
                },

                // Tổng hợp
                summary: allIndicators.summary || {
                    overall_signal: 'NEUTRAL',
                    recommendation: 'Quan sát thêm',
                    confidence: 0
                },

                // Metadata
                timestamp: Date.now(),
                symbol: symbol
            };

            return formattedResult;

        } catch (error) {
            console.error(`Error getTechnicalIndicators with ${symbol}:`, error);

            // Fallback Data if error occurs
            return {
                rsi: Math.floor(Math.random() * 100),
                macd: (Math.random() - 0.5) * 10,
                ema: Math.floor(Math.random() * 50000),
                volume: Math.floor(Math.random() * 1000000000),
                bollinger: {
                    upper: Math.floor(Math.random() * 60000),
                    lower: Math.floor(Math.random() * 40000)
                },
                sma: Math.floor(Math.random() * 45000),
                stochastic: {
                    k: Math.floor(Math.random() * 100),
                    d: Math.floor(Math.random() * 100)
                },
                error: error.message
            };
        }
    }


    async getSingleIndicator(symbol, indicator) {
        try {
            const result = await this.calculateSingleIndicator(symbol, indicator);
            return result;
        } catch (error) {
            console.error(`Eror getSingleIndicator ${indicator} with ${symbol}:`, error);
            throw error;
        }
    }



    /**
     * Analyze and send alert
     * @param {string} symbol - Symbol coin
     * @param {boolean} forceAlert - Force alert sending
     */
    async analyzeAndAlert(symbol, forceAlert = false) {
        try {
            console.log(`🔍 Analyzing ${symbol}...`);

            const [priceData, techData] = await Promise.all([
                coinGeckoService.getCryptoPrices([symbol]),
                this.getTechnicalIndicators(symbol)
            ]);

            const currentPrice = priceData[symbol].usd;
            const priceChange24h = priceData[symbol].usd_24h_change || 0;

            const shouldAlert = forceAlert || this.shouldSendAlert(symbol, currentPrice, priceChange24h, techData);

            if (shouldAlert) {
                const analysisData = `
                        Analyze ${symbol.toUpperCase()}:
                        - Price: $${currentPrice.toFixed(2)}
                        - 24h Change: ${priceChange24h.toFixed(2)}%
                        - Volume: $${(priceData[symbol].usd_24h_vol / 1000000).toFixed(2)}M
                        - RSI: ${techData.rsi}
                        - MACD: ${techData.macd.toFixed(2)}
                        - EMA: ${techData.ema}
                        - SMA: ${techData.sma}
                        Analyze and give a brief comment.
                `;

                console.log("analysisData:", analysisData);

                const aiAnalysis = await this.analyzeWithAI(analysisData);
                const alertMessage = this.formatAlertMessage(symbol, priceData, techData, aiAnalysis);

                await this.sendTelegramMessage(alertMessage);
                this.previousPrices[symbol] = currentPrice;

                console.log(`✅ Alert sent for ${symbol}`);
                return {
                    success: true,
                    message: 'Warning has been sent',
                };
            } else {
                console.log(`ℹ️ No alert needed for ${symbol}`);
                return {
                    success: false,
                    message: 'No Warming needed',
                };
            }
        } catch (error) {
            console.error(`❌ Error analyzing ${symbol}:`, error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get market status
     * @returns {Promise<Object>} - Market status
     */
    async getMarketStatus() {
        try {
            const results = await Promise.all(
                this.config.supportedCoins.map(coin => coinGeckoService.getCryptoPrices([coin]))
            );

            const marketData = {};
            results.forEach((data, index) => {
                const coin = this.config.supportedCoins[index];
                console.log("data: ", data);
                marketData[coin] = {
                    price: data[coin].usd,
                    change24h: data[coin].usd_24h_change,
                    volume: data[coin].usd_24h_vol,
                    marketCap: data[coin].usd_market_cap
                };
            });

            return {
                success: true,
                data: marketData
            };
        } catch (error) {
            console.error('❌ Error getting market status:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Setup Telegram commands
     */
    setupTelegramCommands() {
        this.bot.command('start', (ctx) => {
            ctx.reply('🚀 Crypto Alert Bot is ready!\n\n/help - See instructions');
        });

        this.bot.command('status', async (ctx) => {
            const result = await this.getMarketStatus();
            if (result.success) {
                let message = '📊 <b>Market Status:</b>\n\n';
                Object.entries(result.data).forEach(([coin, data]) => {
                    const emoji = coin === 'bitcoin' ? '🟡' : '🔵';
                    const name = coin === 'bitcoin' ? 'Bitcoin' : 'Ethereum';
                    console.log(data);
                    message += `${emoji} <b>${name}:</b> $${data.price !== 'N/A' ? data.price.toFixed(2) : 'N/A'} (${data.change24h !== 'N/A' ? data.change24h.toFixed(2) : 'N/A'}%)\n`;
                });
                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } else {
                ctx.reply('❌ Error getting market data');
            }
        });

        this.bot.command('analyze', async (ctx) => {
            const args = ctx.message.text.split(' ');
            const symbol = args[1] || 'bitcoin';

            if (!this.config.supportedCoins.includes(symbol)) {
                ctx.reply(`❌ Not supported "${symbol}". Supported: ${this.config.supportedCoins.join(', ')}`);
                return;
            }

            ctx.reply(`🔍 Analyzing ${symbol}...`);
            const result = await this.analyzeAndAlert(symbol, true);

            if (!result.success && result.error) {
                ctx.reply(`❌ Warming: ${result.error}`);
            }
        });

        this.bot.command('help', (ctx) => {
            const help = `
                🤖 <b>Crypto Alert Bot</b>
                    <b>Command:</b>
                    /start - Start
                    /status - Market status
                    /analyze [coin] - Coin analysis
                    /help - Instructions

                <b>Support:</b> ${this.config.supportedCoins.join(', ')}
            `;
            ctx.reply(help, {
                parse_mode: 'HTML'
            });
        });
    }

    /**
     * Setup scheduler
     */
    setupScheduler() {
        const mainJob = cron.schedule(this.config.checkInterval, async () => {
            console.log('🔄 Scheduled analysis...');
            for (const coin of this.config.supportedCoins) {
                await this.analyzeAndAlert(coin);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        });

        const quickJob = cron.schedule(this.config.quickCheckInterval, async () => {
            console.log('⚡ Quick check...');
        });

        this.cronJobs = [mainJob, quickJob];
    }

    async start() {
        try {
            if (this.isRunning) {
                console.log('⚠️ Service is runing');
                return {
                    success: false,
                    message: 'Service is running'
                };
            }

            if (!this.config) {
                throw new Error('Configuration not initialized. Call init() first');
            }

            this.setupTelegramCommands();
            this.setupScheduler();

            await this.bot.launch();
            this.isRunning = true;

            console.log('🚀 AIAnalysisService started');

            await this.sendTelegramMessage('🤖 Crypto Alert Bot has started!');

            return {
                success: true,
                message: 'Service has started'
            };
        } catch (error) {
            console.error('❌ Error starting service:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    async stop() {
        try {
            if (!this.isRunning) {
                console.log('⚠️ Service not running');
                return {
                    success: false,
                    message: 'Service not running'
                };
            }

            this.cronJobs.forEach(job => job.destroy());
            this.cronJobs = [];

            this.bot.stop();
            this.isRunning = false;

            console.log('🛑 AIAnalysisService stopped');
            return {
                success: true,
                message: 'Service stop'
            };
        } catch (error) {
            console.error('❌ Error stopping service:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    getStatus() {
        return {
            isRunning: this.isRunning,
            config: this.config ? 'Configured' : 'Not configured',
            supportedCoins: this.config?.supportedCoins || [],
            cronJobs: this.cronJobs.length
        };
    }
}

export default new AIAnalysisService();

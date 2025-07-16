import axios from 'axios';
import cron from 'node-cron';

import {
    Telegraf
} from 'telegraf';

import coinGeckoService from './CoinGecko.service.js';
import technicalIndicators from './TechnicalAnalysis.service.js';
import AlertSystem from './AlertSystem.service.js';
import {
    getAlerts,
    setAlerts
} from '../data/alerts.js';

/**
 * AI Agent Service Class
 */

class AIAnalysisService {

    constructor() {
        this.bot = null;
        this.aiAgent = null;
        this.cronJobs = [];
        this.isRunning = false;
        this.previousPrices = {};
        this.alertSystem = AlertSystem;

        this.defaultConfig = {
            checkInterval: '*/30 * * * *',
            quickCheckInterval: '*/5 * * * *',
            supportedCoins: ['bitcoin', 'ethereum'],
            aiInstructions: 'You are a cryptocurrency analysis expert. Analyze the market data and provide trading signals and market insights.',
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

        // Initialize AI Agent
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
            const enhancedPrompt = `
                ${this.aiAgent.instructions}
                
                Based on the following data, provide:
                1. Market analysis
                2. Trading signals (if any) with entry point, stop loss, take profit
                3. Risk assessment
                
                Data: ${data}
                
                Please format the response in **clear, human-readable format** using Markdown. Highlight important sections like:

                ### 🔍 Market Analysis
- A             brief but insightful analysis of the market trend

                ### 📈 Trading Signals
                Provide 1–3 trading signals (if applicable). For each signal, include:
                - **Action**: One of BUY, SELL, or HOLD
                - **Confidence**: A number between 0 and 1 (e.g. 0.85)
                - **Entry Point**: Suggested price to enter
                - **Stop Loss**: Suggested stop loss price
                - **Take Profit**: Suggested take profit target
                - **Reasoning**: Explain why this signal is generated, based on technical indicators or trend
                
                **Risk Assessment**
                - Short bullet points

                **Summary**
                - Final thoughts or advice
            `;

            const payload = {
                model: this.aiAgent.model,
                messages: [{
                        role: 'system',
                        content: enhancedPrompt
                    },
                    {
                        role: 'user',
                        content: data
                    }
                ],
                max_tokens: 800,
                temperature: 0.7
            };

            const response = await axios.post(
                `${this.aiAgent.baseUrl}/chat/completions`,
                payload, {
                    headers: this.aiAgent.headers,
                    timeout: 30000
                }
            );

            const content = response.data.choices[0].message.content;

            if (content.includes("### 📈 Trading Signals")) {
                const signalRegex = /\*\*Action\*\*: (BUY|SELL|HOLD)[\s\S]*?\*\*Confidence\*\*: ([0-9.]+)[\s\S]*?\*\*Entry Point\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Stop Loss\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Take Profit\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Reasoning\*\*: (.+?)(?:\n|$)/g;
                const matches = [...content.matchAll(signalRegex)];
                const parsedSignals = matches.map(match => ({
                    action: match[1],
                    confidence: parseFloat(match[2]),
                    entryPoint: parseFloat(match[3].replace(/,/g, '')),
                    stopLoss: parseFloat(match[4].replace(/,/g, '')),
                    takeProfit: parseFloat(match[5].replace(/,/g, '')),
                    reasoning: match[6].trim()
                }));

                return {
                    analysis: content,
                    signals: parsedSignals,
                    summary: "Extracted from Markdown"
                };
            } else {
                return {
                    analysis: content,
                    signals: [],
                    summary: "Extracted from Markdown"
                };
            }
        } catch (error) {
            console.error('❌ AI Analysis Error:', error.message);
            return {
                analysis: 'Error in AI analysis',
                signals: [],
                summary: 'Analysis failed'
            };
        }
    }

    /**
     * Warning message format
     * @param {string} symbol 
     * @param {Object} priceData 
     * @param {Object} techData 
     * @param {string} aiAnalysis 
     * @param {Array} alerts
     * @returns {string} 
     */
    formatAlertMessage(symbol, priceData, techData, aiResult, alerts) {
        const coinData = priceData[symbol];
        const emoji = coinData.usd_24h_change > 0 ? '🟢' : '🔴';
        const trend = coinData.usd_24h_change > 0 ? 'BULLISH' : 'BEARISH';
        const coinName = symbol.charAt(0).toUpperCase() + symbol.slice(1);

        let message = `
            ${emoji} <b>${coinName.toUpperCase()} Analysis</b>

            💰 <b>Price:</b> $${coinData.usd.toFixed(2)}
            📊 <b>24h:</b> ${coinData.usd_24h_change.toFixed(2)}% (${trend})
            📈 <b>Volume:</b> $${(coinData.usd_24h_vol / 1000000).toFixed(2)}M
            💎 <b>Market Cap:</b> $${(coinData.usd_market_cap / 1000000000).toFixed(2)}B

            📋 <b>Technical Indicators:</b>
            • RSI: ${techData.rsi} ${techData.rsi > 70 ? '🔴' : techData.rsi < 30 ? '🟢' : '🟡'}
            • MACD: ${techData.macd.toFixed(2)}
            • EMA: $${techData.ema.toFixed(2)}
            • SMA: $${techData.sma.toFixed(2)}
            • Volume: $${techData.volume.toFixed(2)} ${techData.volume_signal === 'HIGH' ? '🔴' : '🟢'}
            • Bollinger Bands: $${techData.bollinger.upper.toFixed(2)} / $${techData.bollinger.lower.toFixed(2)} / $${techData.bollinger.middle.toFixed(2)}
            • Stochastic: K=${techData.stochastic.k} D=${techData.stochastic.d} ${techData.stochastic.signal === 'OVERBOUGHT' ? '🔴' : techData.stochastic.signal === 'OVERSOLD' ? '🟢' : '🟡'}
            • Summary: ${techData.summary.overall_signal} (${techData.summary.confidence}%)
        `.trim();

        if (alerts && alerts.length > 0) {
            message += '\n\n🚨 <b>Alerts:</b>';
            alerts.forEach(alert => {
                const alertEmoji = this.getAlertEmoji(alert.type, alert.severity);
                message += `\n${alertEmoji} ${alert.message}`;
                if (alert.recommendation) {
                    message += `\n   💡 ${alert.recommendation}`;
                }
            });
            setAlerts(alerts);
        }

        if (aiResult.analysis) {
            message += `\n\n🤖 <b>AI Analysis:</b>\n${aiResult.analysis}`;
        }

        if (aiResult.signals && aiResult.signals.length > 0) {
            message += '\n\n📊 <b>Trading Signals:</b>';
            aiResult.signals.forEach(signal => {
                const signalEmoji = signal.action === 'BUY' ? '🟢' : signal.action === 'SELL' ? '🔴' : '🟡';
                message += `\n${signalEmoji} <b>${signal.action}</b> (${(signal.confidence * 100).toFixed(0)}%)`;
                if (signal.entryPoint) message += `\n   🎯 Entry: $${signal.entryPoint}`;
                if (signal.stopLoss) message += `\n   🛑 Stop Loss: $${signal.stopLoss}`;
                if (signal.takeProfit) message += `\n   🎯 Take Profit: $${signal.takeProfit}`;
                if (signal.reasoning) message += `\n   💭 ${signal.reasoning}`;
            });
        }

        message += `\n\n⏰ <i>${new Date().toLocaleString('vi-VN')}</i>`;
        return message;
    }

    getAlertEmoji(type, severity) {
        const severityEmojis = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '🟡',
            'LOW': 'ℹ️'
        };

        const typeEmojis = {
            'PRICE_CHANGE': '📈',
            'RSI_OVERBOUGHT': '🔴',
            'RSI_OVERSOLD': '🟢',
            'ENTRY_OPPORTUNITY': '🎯',
            'STOP_LOSS_ALERT': '🛑',
            'TAKE_PROFIT_ALERT': '💰',
            'SIGNAL_EXPIRY': '⏰'
        };

        return typeEmojis[type] || severityEmojis[severity] || '📊';
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
                technicalIndicators.getTechnicalIndicators(symbol)
            ]);

            const currentPrice = priceData[symbol].usd;
            const previousPrice = this.previousPrices[symbol];


            const alerts = this.alertSystem.checkAlerts(
                symbol,
                priceData[symbol],
                previousPrice ? {
                    usd: previousPrice
                } : null,
                techData,
            );

            console.log(`Alerts for ${symbol}:`, alerts);

            const analysisData = `
                Analyze ${symbol.toUpperCase()}:
                - Current Price: $${currentPrice.toFixed(2)}
                - 24h Change: ${priceData[symbol].usd_24h_change.toFixed(2)}%
                - Volume: $${(priceData[symbol].usd_24h_vol / 1000000).toFixed(2)}M
                - Technical Summary: ${techData.summary.overall_signal}
                - Active Alerts: ${alerts.length > 0 ? alerts.map(a => a.type).join(', ') : 'None'}
                
                Provide analysis and trading recommendations.
            `;

            const aiResult = await this.analyzeWithAI(analysisData);
            if (aiResult.signals && aiResult.signals.length > 0) {
                const tradingSignals = aiResult.signals.map(signal => ({
                    ...signal,
                    coin: symbol,
                    timestamp: new Date()
                }));
                console.log(`Trading signals for ${symbol}:`, tradingSignals);
                this.alertSystem.setTradingSignals(tradingSignals);
            }
            const shouldAlert = forceAlert ||
                alerts.length > 0 ||
                (aiResult.signals && aiResult.signals.length > 0) ||
                Math.abs(priceData[symbol].usd_24h_change) > 5;

            if (shouldAlert) {
                const alertMessage = this.formatAlertMessage(symbol, priceData, techData, aiResult, alerts);
                await this.sendTelegramMessage(alertMessage);
                this.previousPrices[symbol] = currentPrice;

                console.log(`✅ Alert sent for ${symbol} (${alerts.length} alerts, ${aiResult.signals?.length || 0} signals)`);
                return {
                    success: true,
                    message: 'Alert sent successfully',
                    alertCount: alerts.length,
                    signalCount: aiResult.signals?.length || 0
                };
            } else {
                console.log(`ℹ️ No alert needed for ${symbol}`);
                return {
                    success: false,
                    message: 'No alert needed'
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
                marketData[coin] = {
                    price: data[coin].usd,
                    change24h: data[coin].usd_24h_change,
                    volume: data[coin].usd_24h_vol,
                    marketCap: data[coin].usd_market_cap
                };
            });

            const activeSignals = this.alertSystem.getActiveSignals();

            return {
                success: true,
                data: marketData,
                activeSignals: activeSignals.length,
                signals: activeSignals
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
                    message += `${emoji} <b>${name}:</b> $${data.price.toFixed(2)} (${data.change24h.toFixed(2)}%)\n`;
                });

                if (result.activeSignals > 0) {
                    message += `\n📊 <b>Active Trading Signals:</b> ${result.activeSignals}`;
                }

                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } else {
                ctx.reply('❌ Error getting market data');
            }
        });

        this.bot.command('signals', (ctx) => {
            const activeSignals = this.alertSystem.getActiveSignals();
            console.log(`Active signals: ${activeSignals}`);
            if (activeSignals.length === 0) {
                ctx.reply('📊 No active trading signals');
                return;
            }

            let message = '📊 <b>Active Trading Signals:</b>\n\n';
            activeSignals.forEach(signal => {
                const emoji = signal.action === 'BUY' ? '🟢' : signal.action === 'SELL' ? '🔴' : '🟡';
                message += `${emoji} <b>${signal.coin.toUpperCase()}</b> - ${signal.action}\n`;
                if (signal.entryPoint) message += `   🎯 Entry: $${signal.entryPoint}\n`;
                if (signal.stopLoss) message += `   🛑 Stop: $${signal.stopLoss}\n`;
                if (signal.takeProfit) message += `   💰 Target: $${signal.takeProfit}\n`;
                if (signal.reasoning) message += `   💭 ${signal.reasoning}\n`;
                message += `   ⏰ ${new Date(signal.createdAt).toLocaleString('vi-VN')}\n\n`;
            });

            ctx.reply(message, {
                parse_mode: 'HTML'
            });
        });

        this.bot.command('analyze', async (ctx) => {
            const args = ctx.message.text.split(' ');
            const symbol = args[1] || 'bitcoin';

            if (!this.config.supportedCoins.includes(symbol)) {
                ctx.reply(`❌ "${symbol}" not supported. Available: ${this.config.supportedCoins.join(', ')}`);
                return;
            }

            ctx.reply(`🔍 Analyzing ${symbol}...`);
            const result = await this.analyzeAndAlert(symbol, true);

            if (!result.success && result.error) {
                ctx.reply(`❌ Error: ${result.error}`);
            }
        });

        this.bot.command('help', (ctx) => {
            const help = `
                🤖 <b>Crypto Alert Bot</b>
                    <b>Command:</b>
                    /start - Start
                    /status - Market status
                    /signals - View all active trading signals
                    /analyze [coin] - Coin analysis
                    /help - Instructions

                <b>Support:</b> ${this.config.supportedCoins.join(', ')}
                <b>Features:</b>
                • Real-time price alerts
                • Technical indicator monitoring
                • AI-powered analysis
                • Trading signal generation
                • Risk management alerts
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
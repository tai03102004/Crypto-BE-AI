import axios from 'axios';
import cron from 'node-cron';

import {
    Telegraf
} from 'telegraf';

import coinGeckoService from '../services/CoinGecko.service.js';
import technicalIndicators from '../services/TechnicalAnalysis.service.js';
import AlertSystem from '../services/AlertSystem.service.js';
import {
    getAlerts,
    setAlerts
} from '../data/alerts.js';
import EventEmitter from 'events';
import BinanceLiveTrading from '../services/BinanceService.service.js';

/**
 * AI Agent Service Class
 */

class AIAnalysisAgent extends EventEmitter {

    constructor() {
        super();
        this.bot = null;
        this.aiAgent = null;
        this.cronJobs = [];
        this.isRunning = false;
        this.previousPrices = {};
        this.alertSystem = AlertSystem;
        this.orchestrator = null;
        this.binanceLive = BinanceLiveTrading;

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

    // Add method to handle external events
    handleNewsUpdate(newsData) {
        console.log('📰 Received news update:', newsData.sentiment);
        // Update analysis based on news sentiment
        this.lastNewsSentiment = newsData.sentiment;
    }
    updateMarketData(marketData) {
        console.log(`📊 Market data updated for ${marketData.symbol}`);
        // Store latest market data for analysis
        this.latestMarketData = marketData;
    }
    setOrchestrator(orchestrator) {
        this.orchestrator = orchestrator;
        console.log('🔗 Orchestrator reference set in AnalysisAgent');
    }

    /**
     * Data Analysis with AI
     * @param {string} data - Data to be analyzed
     * @returns {Promise<string>} - Analysis results
     */
    async analyzeWithAI(data) {
        // try {
        let enhancedData = data;
        if (this.lastNewsSentiment) {
            enhancedData += `\n\nNews Sentiment: ${this.lastNewsSentiment}`;
        }
        const enhancedPrompt = `
                ${this.aiAgent.instructions}
                
                Based on the following data, provide:
                1. Market analysis (consider news sentiment if provided)
                2. Trading signals (if any) with entry point, stop loss, take profit
                3. Risk assessment
                
                Data: ${enhancedData}
                
                Please format the response in **clear, human-readable format** using Markdown. Highlight important sections like:

                ### 🔍 Market Analysis
                - A brief but insightful analysis of the market trend

                ### 📈 Trading Signals
                Provide 1–3 trading signals (if applicable). For each signal, include:
                - **Coin**: The coin symbol (BTC or ETH)
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

        console.log("🔍 AI Analysis Result:", content);

        if (content.includes("### 📈 Trading Signals")) {
            const signalRegex = /\*\*Action\*\*: (BUY|SELL|HOLD)[\s\S]*?\*\*Confidence\*\*: ([0-9.]+)[\s\S]*?\*\*Entry Point\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Stop Loss\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Take Profit\*\*: \$?([0-9,.]+)[\s\S]*?\*\*Reasoning\*\*: (.+?)(?:\n|$)/g;
            const matches = [...content.matchAll(signalRegex)];
            const parsedSignals = matches.map(match => ({
                coin: match[0].includes('BTC') ? 'bitcoin' : 'ethereum',
                action: match[1],
                confidence: parseFloat(match[2]),
                entryPoint: parseFloat(match[3].replace(/,/g, '')),
                stopLoss: parseFloat(match[4].replace(/,/g, '')),
                takeProfit: parseFloat(match[5].replace(/,/g, '')),
                reasoning: match[6].trim(),
                timestamp: Date.now()
            }));

            parsedSignals.forEach(signal => {
                this.emit('tradingSignal', signal);
            });

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
        // } catch (error) {
        //     console.error('❌ AI Analysis Error:', error.message);
        //     return {
        //         analysis: 'Error in AI analysis',
        //         signals: [],
        //         summary: 'Analysis failed'
        //     };
        // }
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
        // try {
        console.log(`⛔ Analysis DISABLED for ${symbol} - emergency mode`);
        // const marketData = await this.getMarketData(symbol);

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
                coin: symbol,
                action: signal.action,
                confidence: signal.confidence,
                entryPoint: signal.entryPoint,
                stopLoss: signal.stopLoss,
                takeProfit: signal.takeProfit,
                timestamp: new Date(),
                analysis: aiResult.analysis
            }));
            this.alertSystem.setTradingSignals(tradingSignals);
            tradingSignals.forEach(signal => {
                console.log(`📤 Emitting trading signal: ${signal.action} ${signal.coin} (confidence: ${signal.confidence})`);
                this.emit('tradingSignal', signal);
            });
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
        // } catch (error) {
        //     console.error(`❌ Error analyzing ${symbol}:`, error.message);
        //     return {
        //         success: false,
        //         error: error.message
        //     };
        // }
    }

    /**
     * Send Message Telegram
     * @param {string} message 
     * @param {string} chatId 
     */
    async sendTelegramMessage(message, chatId = process.env.TELEGRAM_CHAT_ID) {
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

        this.bot.command('portfolio', async (ctx) => {
            try {
                if (!this.orchestrator) {
                    ctx.reply('❌ System not fully initialized');
                    return;
                }
                if (!this.orchestrator?.agents?.trading) {
                    ctx.reply('❌ Trading agent not available');
                    return;
                }

                const portfolio = this.orchestrator.agents.trading.getPortfolioStatus();

                let message = `📊 <b>PORTFOLIO STATUS</b>\n\n`;
                message += `💰 <b>Realized P&L:</b> $${portfolio.totalRealizedPnL.toFixed(2)}\n`;
                message += `💹 <b>Unrealized P&L:</b> $${portfolio.totalUnrealizedPnL.toFixed(2)}\n`;
                message += `🎯 <b>Win Rate:</b> ${portfolio.winRate}%\n`;
                message += `📊 <b>Total Trades:</b> ${portfolio.totalTrades}\n\n`;

                if (portfolio.positions.length > 0) {
                    message += `🔄 <b>OPEN POSITIONS (${portfolio.positions.length}):</b>\n`;
                    portfolio.positions.forEach(pos => {
                        const pnl = pos.unrealizedPnL;
                        const emoji = pnl && pnl.isProfit ? '🟢' : '🔴';
                        message += `${emoji} ${pos.symbol}: $${pos.currentPrice.toFixed(2)} `;
                        if (pnl) {
                            message += `(${pnl.percentage.toFixed(2)}%)\n`;
                        } else {
                            message += '\n';
                        }
                    });
                } else {
                    message += `📭 <i>No open positions</i>`;
                }

                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } catch (error) {
                ctx.reply(`❌ Error: ${error.message}`);
            }
        });

        this.bot.command('pnl', async (ctx) => {
            try {
                if (!this.orchestrator?.agents?.trading) {
                    ctx.reply('❌ Trading agent not available');
                    return;
                }
                const portfolio = this.orchestrator.agents.trading.getPortfolioStatus();
                const stats = this.orchestrator.agents.trading.tradingStats;

                const message = `📈 <b>P&L SUMMARY</b>\n\n` +
                    `💰 <b>Total P&L:</b> $${portfolio.totalRealizedPnL.toFixed(2)}\n` +
                    `📅 <b>Today's P&L:</b> $${stats.dailyPnL.toFixed(2)}\n` +
                    `💹 <b>Unrealized P&L:</b> $${portfolio.totalUnrealizedPnL.toFixed(2)}\n\n` +
                    `✅ <b>Winning Trades:</b> ${stats.winTrades}\n` +
                    `❌ <b>Losing Trades:</b> ${stats.lossTrades}\n` +
                    `🎯 <b>Win Rate:</b> ${portfolio.winRate}%\n` +
                    `📊 <b>Total Trades:</b> ${stats.totalTrades}`;

                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } catch (error) {
                ctx.reply(`❌ Error: ${error.message}`);
            }
        });

        // Add to AnalysisAgent setupTelegramCommands():

        this.bot.command('trades', async (ctx) => {
            try {
                if (!this.orchestrator?.agents?.trading) {
                    ctx.reply('❌ Trading agent not available');
                    return;
                }

                const history = this.orchestrator.agents.trading.orderHistory.slice(-10);

                if (history.length === 0) {
                    ctx.reply('📭 No recent trades');
                    return;
                }

                let message = `📊 <b>RECENT TRADES (${history.length})</b>\n\n`;

                history.forEach(trade => {
                    const emoji = trade.side === 'BUY' ? '🟢' : '🔴';
                    const time = new Date(trade.timestamp).toLocaleString();
                    message += `${emoji} <b>${trade.side}</b> ${trade.symbol}\n`;
                    message += `💰 $${trade.price} | ${trade.amount} | ${trade.mode}\n`;
                    message += `⏰ ${time}\n\n`;
                });

                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } catch (error) {
                ctx.reply(`❌ Error: ${error.message}`);
            }
        });

        this.bot.command('balance', async (ctx) => {
            try {
                if (!this.orchestrator?.agents?.trading) {
                    ctx.reply('❌ Trading agent not available');
                    return;
                }

                const tradingAgent = this.orchestrator.agents.trading;
                const status = tradingAgent.getStatus();

                let message = `💰 <b>ACCOUNT BALANCE</b>\n\n`;

                if (status.tradingMode === 'live') {
                    try {
                        if (!tradingAgent.binanceLive.exchange) {
                            console.log('🔧 Binance not initialized, initializing now...');
                            const initialized = await tradingAgent.binanceLive.initialize();
                            if (!initialized) {
                                ctx.reply('❌ Failed to connect to Binance');
                                return;
                            }
                        }
                        const liveBalance = await tradingAgent.binanceLive.getAccountBalance();
                        message += `🔴 <b>LIVE ACCOUNT</b>\n`;
                        message += `• USDT: $${liveBalance?.USDT?.toFixed(2) || '0.00'}\n`;
                        message += `• BTC: ${liveBalance?.BTC?.toFixed(8) }\n`;
                        message += `• ETH: ${liveBalance?.ETH?.toFixed(8) }\n`;
                    } catch (error) {
                        message += `❌ Failed to get live balance: ${error.message}`;
                    }
                } else {
                    console.log('👉 status.balance:', status.balance);

                    message += `📄 <b>PAPER TRADING</b>\n`;
                    message += `• USDT: $${status.balance?.USDT?.toFixed(2) }\n`;
                    message += `• BTC: ${status.balance?.BTC?.toFixed(8) }\n`;
                    message += `• ETH: ${status.balance?.ETH?.toFixed(8) }\n`;
                }

                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } catch (error) {
                ctx.reply(`❌ Error: ${error.message}`);
            }
        });

        // Auto trigger analysis để test
        this.bot.command('force_trade', async (ctx) => {
            ctx.reply('🔄 Forcing analysis to generate trades...');

            for (const coin of ['bitcoin', 'ethereum']) {
                await this.analyzeAndAlert(coin, true);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }

            ctx.reply('✅ Analysis completed - check for auto trades!');
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
                    /portfolio - View portfolio status
                    /pnl - View P&L summary
                    /trades - View recent trades
                    /balance - View account balance
                    /force_trade - Force analysis to generate trades
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
        if (this.config.enableScheduler === false) {
            console.log('📅 Scheduler DISABLED (manual mode)');
            this.cronJobs = [];
            return;
        }

        console.log('📅 Setting up autonomous analysis scheduler...');

        // Main analysis every 15 minutes
        const mainJob = cron.schedule('*/15 * * * *', async () => {
            console.log('🔄 Scheduled autonomous analysis...');
            for (const coin of this.config.supportedCoins) {
                await this.analyzeAndAlert(coin);
                await new Promise(resolve => setTimeout(resolve, 5000)); // 5s between coins
            }
        });

        // Quick market check every 5 minutes
        const quickJob = cron.schedule('*/5 * * * *', async () => {
            console.log('⚡ Quick market health check...');
            const marketStatus = await this.getMarketStatus();
            if (marketStatus.success && marketStatus.signals.length > 0) {
                console.log(`📊 ${marketStatus.signals.length} active signals detected`);
            }
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

export default new AIAnalysisAgent();
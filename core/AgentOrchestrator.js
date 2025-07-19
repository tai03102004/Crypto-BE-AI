import EventEmitter from 'events';
import MarketAgent from '../agents/MarketAgent.js';
import AIAnalysisAgent from '../agents/AnalysisAgent.js';
import TradingAgent from '../agents/TradingAgent.js';
import NewsAgent from '../agents/NewsAgent.js';
import RiskManager from '../agents/RiskManager.js';

class AgentOrchestrator extends EventEmitter {
    constructor() {
        super();
        this.agents = {};
        this.eventBus = new EventEmitter();
        this.isRunning = false;
        this.lastAnalysisTime = new Map();
        this.config = {
            symbols: ['BTCUSDT', 'ETHUSDT'],
            supportedCoins: ['bitcoin', 'ethereum'],
            riskLevel: "medium",
            tradingMode: 'paper', // paper or live
        }
    }

    async initialize() {
        console.log('🚀 Initializing Agent Orchestrator...');

        try {
            // Initialize all agents
            this.agents.market = new MarketAgent();
            const sharedConfig = {
                telegramToken: process.env.TELEGRAM_BOT_TOKEN,
                chatId: process.env.CHAT_ID,
                aiApiKey: process.env.IOINTELLIGENCE_API_KEY,
                aiModel: 'meta-llama/Llama-3.3-70B-Instruct',
                aiBaseUrl: 'https://api.intelligence.io.solutions/api/v1',
                supportedCoins: ['bitcoin', 'ethereum'],
                alertThresholds: {
                    priceChange: 5,
                    rsiOverbought: 70,
                    rsiOversold: 30
                }
            };

            // Khởi tạo và chạy
            this.agents.trading = new TradingAgent();
            this.agents.news = new NewsAgent();
            this.agents.risk = new RiskManager();

            if (AIAnalysisAgent.init) {
                AIAnalysisAgent.init(sharedConfig);
            }
            this.agents.analysis = AIAnalysisAgent;

            // Setup communication between agents
            this.setupAgentCommunication();

            // Start all agents
            await this.startAllAgents();

            console.log('✅ All agents initialized and running');
            return {
                success: true,
                message: 'System started successfully'
            };

        } catch (error) {
            console.error('❌ Failed to initialize agents:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    setupAgentCommunication() {
        console.log('🔇 ALL AGENT COMMUNICATION DISABLED');
        // Market Agent -> Analysis Agent
        if (this.agents.market && this.agents.analysis) {
            this.agents.market.on('priceUpdate', (data) => {
                // Trigger analysis when significant price changes occur
                if (Math.abs(data.change24h) > 2) {
                    const coinId = this.convertSymbolToCoinId(data.symbol);
                    if (this.agents.analysis.analyzeAndAlert) {
                        this.agents.analysis.analyzeAndAlert(coinId, false);
                    }
                }
            });

            this.agents.market.on('marketDataUpdate', (data) => {
                // Update analysis agent with new market data
                if (this.agents.analysis.updateMarketData) {
                    this.agents.analysis.updateMarketData(data);
                }
            });
        }

        // News Agent -> Analysis Agent
        if (this.agents.news && this.agents.analysis) {
            this.agents.news.on('marketNews', (news) => {
                try {
                    if (this.agents.analysis.handleNewsUpdate) {
                        console.log('📰 Processing news update for analysis');
                        this.agents.analysis.handleNewsUpdate(news);
                    }
                } catch (error) {
                    console.error('❌ Error in news update handler:', error);
                }
            });
        }

        // Analysis Agent -> Risk Manager -> Trading Agent
        if (this.agents.analysis && this.agents.risk) {
            this.agents.analysis.on('tradingSignal', (signal) => {
                try {
                    console.log('📊 Received trading signal, validating risk...');
                    this.agents.risk.handleEvent('validateSignal', signal);
                } catch (error) {
                    console.error('❌ Error in trading signal handler:', error);
                }
            });
        }

        if (this.agents.risk && this.agents.trading) {
            this.agents.risk.on('signalApproved', (signal) => {
                try {
                    console.log('✅ Signal approved, executing trade...');
                    this.agents.trading.handleEvent('executeSignal', signal);
                } catch (error) {
                    console.error('❌ Error in signal approval handler:', error);
                }
            });
        }

        // Trading Agent -> All (notifications)
        if (this.agents.trading) {
            this.agents.trading.on('orderExecuted', (order) => {
                console.log('💰 Order executed:', order);
                this.emit('orderExecuted', order);

                // Send Telegram notification
                if (this.agents.analysis && this.agents.analysis.sendTelegramMessage) {
                    const message = `💰 <b>Order Executed</b>\n\n` +
                        `📊 <b>Symbol:</b> ${order.symbol}\n` +
                        `🎯 <b>Action:</b> ${order.side}\n` +
                        `💎 <b>Price:</b> $${order.price}\n` +
                        `📈 <b>Quantity:</b> ${order.quantity}\n` +
                        `⏰ <b>Time:</b> ${new Date().toLocaleString()}`;

                    this.agents.analysis.sendTelegramMessage(message);
                }
            });

            this.agents.trading.on('tradeError', (error) => {
                console.error('❌ Trade execution error:', error);
                if (this.agents.analysis && this.agents.analysis.sendTelegramMessage) {
                    this.agents.analysis.sendTelegramMessage(
                        `❌ <b>Trade Error</b>\n\n${error.error}`
                    );
                }
            });
        }
    }

    async startAllAgents() {
        const startOrder = ['market', 'news', 'risk', 'trading', 'analysis'];

        for (const agentName of startOrder) {
            const agent = this.agents[agentName];
            try {
                if (agentName === 'analysis') {
                    // For your existing AnalysisAgent singleton
                    if (agent && agent.start) {
                        await agent.start();
                    }
                } else if (agent && agent.start) {
                    await agent.start(this.config);
                }
                console.log(`✅ ${agentName} agent started`);
            } catch (error) {
                console.error(`❌ Failed to start ${agentName} agent:`, error);
                // Don't throw error, continue with other agents
            }
        }
        this.isRunning = true;
    }

    convertSymbolToCoinId(symbol) {
        const mapping = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum'
        };
        return mapping[symbol] || symbol.toLowerCase().replace('usdt', '');
    }

    async stop() {
        console.log('🛑 Stopping all agents...');

        for (const [name, agent] of Object.entries(this.agents)) {
            try {
                if (agent && agent.stop) {
                    await agent.stop();
                }
                console.log(`✅ ${name} agent stopped`);
            } catch (error) {
                console.error(`❌ Error stopping ${name} agent:`, error);
            }
        }

        this.isRunning = false;
        return {
            success: true,
            message: 'System stopped successfully'
        };
    }

    getSystemStatus() {
        const status = {
            isRunning: this.isRunning,
            agents: {},
            totalAlerts: 0,
            activeSignals: 0,
            timestamp: Date.now()
        };

        for (const [name, agent] of Object.entries(this.agents)) {
            if (agent && agent.getStatus) {
                status.agents[name] = agent.getStatus();
            } else {
                status.agents[name] = 'unknown';
            }
        }

        // Get additional metrics from analysis agent
        if (this.agents.analysis && this.agents.analysis.getStatus) {
            const analysisStatus = this.agents.analysis.getStatus();
            status.totalAlerts = analysisStatus.cronJobs || 0;
        }

        return status;
    }

    // Manual trigger for testing
    async triggerAnalysis(coinId = 'bitcoin') {
        // THÊM RATE LIMITING
        const now = Date.now();
        const lastTime = this.lastAnalysisTime.get(coinId) || 0;
        const minInterval = 30000; // 30 giây

        if ((now - lastTime) < minInterval) {
            console.log(`⏭️ Skipping ${coinId} - analyzed ${Math.round((now - lastTime)/1000)}s ago`);
            return {
                success: false,
                error: `Please wait ${Math.round((minInterval - (now - lastTime))/1000)}s before next analysis`
            };
        }

        this.lastAnalysisTime.set(coinId, now);

        if (this.agents.analysis) {
            return await this.agents.analysis.analyzeAndAlert(coinId, true);
        }
        return {
            success: false,
            error: 'Analysis agent not available'
        };
    }

    async getMarketData(symbol) {
        if (this.agents.market && this.agents.market.priceCache) {
            return this.agents.market.priceCache.get(symbol) || null;
        }
        return null;
    }

    // Force news collection
    async collectNews() {
        try {
            if (this.agents.news && this.agents.news.collectCryptoNews) {
                await this.agents.news.collectCryptoNews();
                return {
                    success: true,
                    message: 'News collection triggered'
                };
            }
            return {
                success: false,
                error: 'News agent not available'
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
}

export default AgentOrchestrator;
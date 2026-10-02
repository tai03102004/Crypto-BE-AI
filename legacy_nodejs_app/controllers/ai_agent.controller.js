import AgentOrchestrator from "../core/AgentOrchestrator.js";

const orchestrator = new AgentOrchestrator();

export const status = async (req, res) => {
    try {
        const status = orchestrator.getSystemStatus();
        res.json({
            success: true,
            data: status
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const start = async (req, res) => {
    try {
        const result = await orchestrator.initialize();
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const stop = async (req, res) => {
    try {
        const result = await orchestrator.stop();
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const analyzeCoin = async (req, res) => {
    try {
        const {
            coin
        } = req.params;
        const result = await orchestrator.triggerAnalysis(coin);
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const getMarketData = async (req, res) => {
    try {
        const {
            symbol
        } = req.params;
        const data = await orchestrator.getMarketData(symbol);
        res.json({
            success: true,
            data: data
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const collectNews = async (req, res) => {
    try {
        const result = await orchestrator.collectNews();
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const getTradingStatus = async (req, res) => {
    try {
        if (!orchestrator.agents.trading) {
            return res.status(400).json({
                success: false,
                error: 'Trading agent not initialized'
            });
        }

        const status = orchestrator.agents.trading.getStatus();
        res.json({
            success: true,
            data: status
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const getPositions = async (req, res) => {
    try {
        const positions = Array.from(orchestrator.agents.trading.activePositions.values());
        res.json({
            success: true,
            data: {
                positions: positions,
                count: positions.length
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const getTradingHistory = async (req, res) => {
    try {
        const history = orchestrator.agents.trading.orderHistory.slice(-10);
        res.json({
            success: true,
            data: history
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const checkBinanceAccount = async (req, res) => {
    try {
        if (!orchestrator.agents) {
            return res.status(400).json({
                success: false,
                error: 'Orchestrator not initialized'
            });
        }

        if (!orchestrator.agents.trading) {
            return res.status(400).json({
                success: false,
                error: 'Trading agent not initialized'
            });
        }

        if (!orchestrator.agents.trading.binanceLive) {
            return res.status(400).json({
                success: false,
                error: 'Binance service not available'
            });
        }
        console.log("orchestrator agents trading:", orchestrator.agents.trading);

        // Test connection and get account info
        const testResult = await orchestrator.agents.trading.binanceLive.testConnection();
        const accountInfo = await orchestrator.agents.trading.binanceLive.getDetailedAccountInfo();
        const balance = await orchestrator.agents.trading.binanceLive.getAccountBalance();

        res.json({
            success: true,
            data: {
                connectionTest: testResult,
                accountInfo: accountInfo,
                balance: balance,
                isTestnet: process.env.BINANCE_TESTNET === 'true'
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};

export const getBinanceHistory = async (req, res) => {
    try {
        const {
            symbol = 'BTCUSDT', limit = 10
        } = req.query;

        const history = await orchestrator.agents.trading.binanceLive.getTradingHistory(symbol, parseInt(limit));

        res.json({
            success: true,
            data: history
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
};
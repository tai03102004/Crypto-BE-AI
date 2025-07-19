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
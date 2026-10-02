// routes/aiChat.routes.js
import express from 'express';
import {
    status,
    start,
    stop,
    analyzeCoin,
    getMarketData,
    collectNews,
    getTradingStatus,
    getPositions,
    getTradingHistory,
    checkBinanceAccount,
    getBinanceHistory
} from '../controllers/ai_agent.controller.js';

const router = express.Router();
// System control routes
router.get('/status', status);
router.post('/start', start);
router.post('/stop', stop);

// Trading routes:
router.get('/trading/status', getTradingStatus);
router.get('/trading/positions', getPositions);
router.get('/trading/history', getTradingHistory);
router.get('/binance/account', checkBinanceAccount);
router.get('/binance/history', getBinanceHistory);

// Analysis routes
router.post('/analyze/:coin', analyzeCoin);
router.get('/market/:symbol', getMarketData);
router.post('/news/collect', collectNews);
export default router;
import express from 'express';
import {
    prices
} from '../controllers/crypto/prices.controller.js';
import {
    historyByCoinId
} from '../controllers/crypto/history.controller.js';

const router = express.Router();

router.get("/prices", prices);
router.get("/history/:coinId", historyByCoinId);

export default router;
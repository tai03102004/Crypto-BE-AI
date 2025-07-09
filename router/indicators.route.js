import express from 'express';
import {
    indicators
} from '../controllers/indicators.controller.js';

const router = express.Router();

router.post("/indicators", indicators);

export default router;
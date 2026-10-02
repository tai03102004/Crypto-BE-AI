import express from 'express';
import {
    manualAnalysis
} from '../controllers/manual-analysis.controller.js';

const router = express.Router();

router.post("/", manualAnalysis);

export default router;
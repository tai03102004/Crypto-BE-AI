import express from 'express';
import {
    getRecentAlerts
} from '../controllers/alerts.controller.js';

const router = express.Router();

// Route GET /api/alerts
router.get("/", getRecentAlerts);

export default router;
// routes/aiChat.routes.js
import express from 'express';

const router = express.Router();
import {
    analysis
} from '../controllers/analysis.controller.js';

// Tạo cuộc trò chuyện mới
router.get('/', analysis);


export default router;
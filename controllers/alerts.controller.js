import {
    getAlerts
} from '../data/alerts.js';

import AIAnalysisService from '../services/AIAgent.service.js';

export const getRecentAlerts = async (req, res) => {
    try {
        const config = {
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
        AIAnalysisService.init(config);
        await AIAnalysisService.start();
        const alerts = await getAlerts();

        res.json(alerts.slice(-20));
    } catch (error) {
        console.error("Error fetching alerts:", error);
        res.status(500).json({
            error: "Internal server error"
        });
    }
};
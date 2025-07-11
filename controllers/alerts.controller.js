import {
    getAlerts
} from '../data/alerts.js';
import AIAnalysisService from '../services/AIAgent.service.js';


export const getRecentAlerts = async (req, res) => {
    try {
        const config = {
            telegramToken: '8134723930:AAEZWYUfKmArVSJ2GoLtOfVAhRMHTL12gFo',
            chatId: '5648969247',
            aiApiKey: 'io-v2-eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJvd25lciI6Ijc1NjNiM2I4LWU3OTEtNGFjMi04YTY1LTg0ZjU3ODkyNDM5NSIsImV4cCI6NDkwNTIwMjQ4Nn0.hYGWdOQVRdbhUYF_IQD1Qd-HNOg7i9NRmhj1PMkDHtS-hK5C0JMqVBF8O31URDswDEVdQIdM2p3is-TXpwxjRw',
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
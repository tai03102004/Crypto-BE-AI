import {
    getAnalysisResults
} from '../data/analysisResults.js';
import {
    performAnalysis
} from '../middlewares/performAnalysis.middlewares.js';
import AIAnalysisService from '../services/AIAgent.service.js';

export const analysis = async (req, res) => {
    await performAnalysis();

    const config = {
        telegramToken: '8134723930:AAEZWYUfKmArVSJ2GoLtOfVAhRMHTL12gFo',
        chatId: 'jashon_chang',
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

    var analysisResults = getAnalysisResults();
    res.json(analysisResults);
}
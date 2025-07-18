import {
    getCryptoData,
    setCryptoData
} from '../data/cryptoData.js';
import {
    getAlerts,
    setAlerts
} from '../data/alerts.js';
import coinGeckoService from '../services/CoinGecko.service.js';
import AlertSystem from '../services/AlertSystem.service.js';
import AIAnalysisService from '../services/AIAnalysis.service.js';
import technicalService from '../services/TechnicalAnalysis.service.js';
import {
    setAnalysisResults
} from '../data/analysisResults.js';

import {
    AiAnalysis
} from '../model/ai_analysis.model.js';

import {
    WebSocketServer
} from 'ws';
import pLimit from 'p-limit';

const limit = pLimit(1); // Limit concurrency to 1 to avoid rate limiting issues

// WebSocket server for real-time updates
const wss = new WebSocketServer({
    port: 8080
});

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Main analysis function
export const performAnalysis = async (req, res) => {
    // try {
    console.log('Starting crypto analysis...');

    // Get current crypto prices (coin Gecko API)
    const priceData = await coinGeckoService.getCryptoPrices();
    if (!priceData) return;

    const previousData = {
        ...getCryptoData()
    };
    setCryptoData(priceData);

    // Get historical data for all coins
    const coins = Object.keys(priceData);
    const historicalData = {};
    for (const coin of coins) {
        console.log(`Fetching historical data for ${coin}...`);
        historicalData[coin] = await coinGeckoService.getHistoricalData(coin, 30);
        await sleep(2000); // Add a 2-second delay between requests
    }

    // Get technical indicators for each coin
    const analysisPromises = coins.map((coinId) => limit(async () => {
        const symbol = coinId.toLowerCase();

        let indicators = {};
        try {
            indicators = await technicalService.calculateAllIndicators(symbol);
        } catch (error) {
            console.error(`Error calculating indicators for ${coinId}:`, error.message);
        }

        // Check for alerts
        const coinAlerts = AlertSystem.checkAlerts(coinId, priceData[coinId], previousData[coinId], indicators);
        const currentAlerts = getAlerts();
        setAlerts([...currentAlerts, ...coinAlerts]);

        return {
            coin: coinId,
            price: priceData[coinId],
            indicators
        };
    }));

    const analysisData = await Promise.all(analysisPromises);

    // AI Analysis
    let aiAnalysis = '';
    if (process.env.IOINTELLIGENCE_API_KEY) {
        aiAnalysis = await AIAnalysisService.analyzeMarketData(priceData, analysisData, historicalData);
    }

    const getNextConversationId = async () => {
        const latestMessage = await AiAnalysis.findOne().sort({
            conversationId: -1
        });
        const latestId = latestMessage ? parseInt(latestMessage.conversationId, 10) : 0;
        return latestId + 1;
    };

    const conversationId = await getNextConversationId();

    await AiAnalysis.create({
        conversationId: `crypto_analysis + ${conversationId}`,
        content: `Crypto analysis completed. AI Analysis: ${aiAnalysis.analysis}`,
        alert: `Crypto analysis completed. AI alert: ${getAlerts().slice(-10).map(alert => alert.message).join(', ')}`,
        imagesUrl: [],

        role: "assistant",
    });

    const result = {
        timestamp: new Date(),
        data: analysisData,
        aiAnalysis,
        alerts: getAlerts().slice(-10),
    };

    // console.log('Analysis result:', result);

    setAnalysisResults(result);

    // Broadcast to WebSocket clients
    broadcast({
        type: 'ANALYSIS_UPDATE',
        data: result
    });
    coinGeckoService.clearCache();
    // } catch (error) {
    //     console.error('Error in analysis:', error.message);
    // }
};

// WebSocket connection handling
wss.on('connection', (ws) => {
    console.log('New WebSocket client connected');

    // Send current data to new client
    ws.send(JSON.stringify({
        type: 'INITIAL_DATA',
        data: setAnalysisResults // Ensure this variable is defined globally
    }));

    ws.on('close', () => {
        console.log('WebSocket client disconnected');
    });
});

// Broadcast to all connected clients
function broadcast(data) {
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(data));
        }
    });
}
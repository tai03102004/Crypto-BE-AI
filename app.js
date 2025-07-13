// server.js - Main Express Server


import express from 'express';
import cors from 'cors';
import cron from 'node-cron';
import dotenv from 'dotenv';
dotenv.config();
import cookieParser from 'cookie-parser';
import session from 'express-session';
import flash from 'connect-flash';
import bodyParser from 'body-parser';
import methodOverride from 'method-override';
import route from './router/index.route.js';

import AIAnalysisService from './services/AIAgent.service.js';

// Load environment variables
import {
    connect
} from './config/database.js';
import {
    performAnalysis
} from './middlewares/performAnalysis.middlewares.js';


const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Kết nối với database
connect();

// để web đẹp hơn
app.use(express.static(`${process.cwd()}/public`));

// Flash
app.use(cookieParser("LHNASDASDAD"));
app.use(session({
    secret: process.env.SESSION_SECRET || "your_default_secret", // nên để trong .env
    resave: false,
    saveUninitialized: false,
    cookie: {
        maxAge: 60000
    }
}));

app.use(flash());

// bodyParser: để có thể lấy data trong req.body (key:value) từ phía client nhập vào
app.use(bodyParser.urlencoded({
    extended: false
}));

// method-override:  use patch, delete,..
app.use(methodOverride('_method'));

// route
route(app);

// Schedule analysis every 1 hour
cron.schedule('0 * * * *', async () => {
    console.log('Running scheduled analysis every hour...');
    // performAnalysis();

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

});


// Initial analysis on startup
setTimeout(() => {
    performAnalysis();
}, 5000);


app.listen(PORT, () => {
    console.log(`Crypto Co-Pilot Backend running on port ${PORT}`);
    console.log(`WebSocket server running on port 8080`);
    console.log('Scheduled analysis every 5 minutes');
});

export default app;
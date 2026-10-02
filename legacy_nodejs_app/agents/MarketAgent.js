import EventEmitter from 'events';
import WebSocket from 'ws';
import CoinGeckoService from '../services/CoinGecko.service.js';

class MarketAgent extends EventEmitter {
    constructor() {
        super();
        this.connections = new Map();
        this.isRunning = false;
        this.priceCache = new Map();
        this.config = null;
    }

    async start(config) {
        this.config = config;
        this.isRunning = true;

        await this.setupWebSocketConnections();
        this.setupPeriodicCollection();

        console.log('🌐 Market Agent started');
    }

    async setupWebSocketConnections() {
        const symbols = this.config.symbols || ['BTCUSDT', 'ETHUSDT'];
        symbols.forEach(symbol => {
            const ws = new WebSocket(`wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@ticker`);

            ws.on('open', () => {
                console.log(`🔗 Connected to ${symbol} stream`);
            });

            ws.on('message', (data) => {
                const ticker = JSON.parse(data);
                this.handlePriceUpdate(symbol, ticker);
            });

            ws.on('error', (error) => {
                console.error(`❌ WebSocket error for ${symbol}:`, error);
            });

            this.connections.set(symbol, ws);
        });
    }

    handlePriceUpdate(symbol, ticker) {
        const priceData = {
            symbol: symbol,
            price: parseFloat(ticker.c),
            change24h: parseFloat(ticker.p),
            volume: parseFloat(ticker.v),
            timestamp: Date.now()
        }

        this.priceCache.set(symbol, priceData);

        this.emit('priceUpdate', priceData);

        if (Math.abs(priceData.change24h) > 5) {
            this.emit('significantPriceMove', priceData);
        }
    }

    setupPeriodicCollection() {
        this.marketDataInterval = setInterval(async () => {
            await this.collectDetailedMarketData();
        }, 5 * 60 * 1000);
    }

    async collectDetailedMarketData() {
        try {
            const symbols = this.config.symbols || ['bitcoin', 'ethereum'];
            const marketData = await CoinGeckoService.getCryptoPrices(symbols);

            for (const [symbol, data] of Object.entries(marketData)) {
                this.emit('marketDataUpdate', {
                    symbol,
                    data,
                    timestamp: Date.now()
                });
            }
        } catch (error) {
            console.error('❌ Error collecting market data:', error);
        }
    }

    getStatus() {
        return {
            isRunning: this.isRunning,
            activeConnections: this.connections.size,
            cachedPrices: this.priceCache.size,
            lastUpdated: Date.now(),
        }
    }

    stop() {
        this.connections.forEach(ws => ws.close());
        this.connections.clear();

        if (this.marketDataInterval) {
            clearInterval(this.marketDataInterval);
            this.marketDataInterval = null;
        }
        this.isRunning = false;
        console.log('🌐 Market Agent stopped');
    }
}

export default MarketAgent;
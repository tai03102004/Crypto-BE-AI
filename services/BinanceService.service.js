import ccxt from 'ccxt';

class BinanceLiveTrading {
    constructor() {
        this.exchange = null;
        this.isLive = false;
    }

    async initialize() {
        this.exchange = new ccxt.binance({
            apiKey: process.env.BINANCE_API_KEY,
            secret: process.env.BINANCE_SECRET_KEY,
            sandbox: process.env.BINANCE_TESTNET === 'true',
            enableRateLimit: true,
        });

        try {
            await this.exchange.loadMarkets();
            const balance = await this.exchange.fetchBalance();
            console.log('✅ Binance connection established');
            console.log('💰 Account balance:', balance.USDT?.free || 0, 'USDT');
            this.isLive = true;
            return true;
        } catch (error) {
            console.error('❌ Binance connection failed:', error.message);
            return false;
        }
    }

    async createMarketOrder(symbol, side, amount, price = null) {
        try {
            if (!this.isLive) {
                throw new Error('Binance not connected');
            }

            const order = await this.exchange.createOrder(
                symbol, // 'BTC/USDT'
                'market', // 'market' or 'limit'
                side, // 'buy' or 'sell'
                amount, // amount in base currency
                price // price (null for market orders)
            );

            console.log('✅ Live order created:', order);
            return {
                success: true,
                orderId: order.id,
                symbol: order.symbol,
                side: order.side,
                amount: order.amount,
                price: order.price || order.average,
                status: order.status,
                timestamp: order.timestamp
            };
        } catch (error) {
            console.error('❌ Live order failed:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    async getAccountBalance() {
        try {
            const balance = await this.exchange.fetchBalance();
            return {
                USDT: balance.USDT?.free || 0,
                BTC: balance.BTC?.free || 0,
                ETH: balance.ETH?.free || 0,
                total: balance.USDT?.total || 0
            };
        } catch (error) {
            console.error('❌ Balance fetch failed:', error);
            return null;
        }
    }

    async getOrderStatus(orderId, symbol) {
        try {
            const order = await this.exchange.fetchOrder(orderId, symbol);
            return order;
        } catch (error) {
            console.error('❌ Order status fetch failed:', error);
            return null;
        }
    }
}

export default new BinanceLiveTrading();
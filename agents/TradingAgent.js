import BinanceLiveTrading from '../services/BinanceLiveTrading.js';

class TradingAgent extends EventEmitter {
    constructor() {
        super();
        this.activePositions = new Map();
        this.orderHistory = [];
        this.balance = {};
        this.tradingMode = 'paper'; // 'paper' or 'live'
        this.binanceLive = BinanceLiveTrading;
    }

    async start(config) {
        this.config = config;
        this.tradingMode = config.tradingMode || 'paper';

        if (this.tradingMode === 'live') {
            const connected = await this.binanceLive.initialize();
            if (!connected) {
                console.warn('⚠️ Binance connection failed, switching to paper mode');
                this.tradingMode = 'paper';
            } else {
                this.balance = await this.binanceLive.getAccountBalance();
                console.log(`💰 Live Trading Agent started with balance:`, this.balance);
            }
        } else {
            console.log(`💰 Trading Agent started in ${this.tradingMode} mode`);
        }
    }

    async executeSignal(signal) {
        try {
            console.log(`🎯 Executing ${this.tradingMode} signal:`, signal);

            // Convert coin to trading symbol
            const symbol = this.convertCoinToSymbol(signal.coin);
            const side = signal.action.toLowerCase(); // 'buy' or 'sell'
            const amount = this.calculatePositionSize(signal);

            if (this.tradingMode === 'live') {
                return await this.executeLiveOrder(symbol, side, amount, signal);
            } else {
                return await this.executePaperTrade(symbol, side, amount, signal);
            }
        } catch (error) {
            console.error('❌ Trade execution error:', error);
            this.emit('tradeError', {
                signal,
                error: error.message
            });
        }
    }

    async executeLiveOrder(symbol, side, amount, signal) {
        try {
            const result = await this.binanceLive.createMarketOrder(
                symbol, // 'BTC/USDT'
                side, // 'buy' or 'sell'
                amount // calculated amount
            );

            if (result.success) {
                const order = {
                    id: result.orderId,
                    symbol: symbol,
                    side: side.toUpperCase(),
                    type: 'MARKET',
                    quantity: amount,
                    price: result.price,
                    status: 'FILLED',
                    timestamp: Date.now(),
                    mode: 'LIVE',
                    signal: signal
                };

                this.orderHistory.push(order);

                // Track position
                if (side === 'buy') {
                    this.activePositions.set(symbol, {
                        ...order,
                        stopLoss: signal.stopLoss,
                        takeProfit: signal.takeProfit,
                        entryPrice: result.price
                    });
                } else {
                    this.activePositions.delete(symbol);
                }

                // Update balance
                this.balance = await this.binanceLive.getAccountBalance();

                this.emit('orderExecuted', order);
                return order;
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('❌ Live order execution failed:', error);
            throw error;
        }
    }

    convertCoinToSymbol(coin) {
        const mapping = {
            'bitcoin': 'BTC/USDT',
            'ethereum': 'ETH/USDT'
        };
        return mapping[coin] || `${coin.toUpperCase()}/USDT`;
    }

    calculatePositionSize(signal) {
        const riskPercentage = 0.02; // 2% risk per trade
        const accountValue = this.balance?.USDT || 1000; // Use actual USDT balance
        const riskAmount = accountValue * riskPercentage;

        if (signal.stopLoss && signal.entryPoint) {
            const riskPerUnit = Math.abs(signal.entryPoint - signal.stopLoss);
            const quantity = riskAmount / riskPerUnit;
            return Math.max(0.001, quantity); // Minimum order size
        }

        // Fallback: use 1% of account value
        const fallbackAmount = accountValue * 0.01;
        return fallbackAmount / signal.entryPoint;
    }
}
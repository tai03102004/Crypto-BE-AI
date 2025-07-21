import BinanceLiveTrading from '../services/BinanceService.service.js';
import {
    EventEmitter
} from 'events';

class TradingAgent extends EventEmitter {
    constructor() {
        super();
        this.portfolio = new Map(); // Live positions
        this.orderHistory = [];
        this.balance = {};
        this.tradingMode = 'live';
        this.binanceLive = BinanceLiveTrading;
        this.isRunning = false;

        // ✨ Trading stats for P&L tracking
        this.tradingStats = {
            totalTrades: 0,
            winTrades: 0,
            lossTrades: 0,
            totalPnL: 0,
            dailyPnL: 0
        };

        this.priceMonitor = null;
    }

    async start(config) {
        this.config = config;
        this.tradingMode = config?.tradingMode || 'live';
        this.isRunning = true;

        console.log(`🚀 Starting TradingAgent in ${this.tradingMode} mode...`);

        if (this.tradingMode === 'live' && this.binanceLive) {
            const testResult = await this.binanceLive.testConnection();
            if (!testResult.success) {
                console.warn('⚠️ Binance connection failed, switching to paper mode');
                this.tradingMode = 'live';
            } else {
                const connected = await this.binanceLive.initialize();
                if (connected) {
                    this.balance = await this.binanceLive.getAccountBalance();
                    console.log(`💰 Live Trading connected`);
                } else {
                    this.tradingMode = 'live';
                }
            }
        }

        // ✨ Start monitoring for live mode
        if (this.tradingMode === 'live') {
            this.startPnLMonitoring();
        }

        console.log(`✅ TradingAgent started in ${this.tradingMode} mode`);
    }

    // ✨ Main execution method
    async executeSignal(signal) {
        // try {

        if (this.tradingMode === 'live' && this.binanceLive.exchange) {
            console.log('💰 Updating balance before trade...');
            this.balance = await this.binanceLive.getAccountBalance();
            console.log('✅ Updated balance:', this.balance);
        }

        if (!this.validateSignal(signal)) {
            return {
                success: false,
                error: 'Signal validation failed'
            };
        }

        const symbol = this.convertCoinToSymbol(signal.coin);
        const side = signal.action.toLowerCase();
        const amount = this.calculatePositionSize(signal);
        console.log("💰 Calculated trade amount:", amount);
        console.log(`🔍 Trading ${side.toUpperCase()} ${symbol} with amount: $${amount}`);

        if (!amount || amount <= 0) {
            console.error('❌ Invalid amount:', amount);
            // ✨ FORCE MINIMUM TRADE IF BALANCE IS GOOD
            if (this.balance?.USDT > 100) {
                const forceAmount = 50; // Force $50 trade
                console.log(`🔧 Forcing minimum trade: $${forceAmount}`);
                return await this.executeLiveOrder(symbol, side, forceAmount, signal);
            }
            return {
                success: false,
                error: 'Invalid trade amount'
            };
        }


        if (this.tradingMode === 'live') {
            return await this.executeLiveOrder(symbol, side, amount, signal);
        } else {
            return await this.executePaperTrade(symbol, side, amount, signal);
        }
        // } catch (error) {
        //     console.error('❌ Trade execution error:', error);
        //     return {
        //         success: false,
        //         error: error.message
        //     };
        // }
    }

    validateSignal(signal) {
        if (!signal.coin || !signal.action || !signal.confidence) return false;
        if (signal.confidence < 0.75) return false;
        if (this.balance.USDT < 10) return false;
        if (this.portfolio.size >= 3) return false;
        return true;
    }

    // ✨ LIVE BINANCE TRADING
    async executeLiveOrder(symbol, side, amount, signal) {
        // try {
        if (!symbol || !side || !amount || amount <= 0) {
            throw new Error(`Invalid parameters: symbol=${symbol}, side=${side}, amount=${amount}`);
        }

        if (!this.binanceLive.exchange) {
            throw new Error('Binance exchange not initialized');
        }
        console.log(`🚀 LIVE TRADE: ${side.toUpperCase()} ${symbol} - $${amount}`);

        const result = await this.binanceLive.createMarketOrder(symbol, side, amount);
        console.log('>>>>> DEBUG LIVE ORDER RESULT <<<<<');
        console.log('Result:', result);
        if (!result) {
            throw new Error('No result from Binance order');
        }

        if (result.success) {
            const order = {
                id: result.orderId,
                symbol: symbol,
                side: side.toUpperCase(),
                amount: amount,
                timestamp: Date.now(),
                mode: 'LIVE',
            };

            this.orderHistory.push(order);
            this.tradingStats.totalTrades++;

            if (side === 'buy') {
                // ✨ Open position
                const position = {
                    symbol: symbol,
                    side: 'LONG',
                    entryPrice: signal.entryPoint || result.price,
                    quantity: amount,
                    entryTime: new Date(),
                    stopLoss: signal.stopLoss || (result.price * 0.97),
                    takeProfit: signal.takeProfit || (result.price * 1.05),
                    unrealizedPnL: {
                        absolute: 0,
                        percentage: 0
                    }
                };

                this.portfolio.set(symbol, position);

                const buyMessage = `🟢 <b>BUY EXECUTED</b>\n\n` +
                    `🪙 ${symbol}\n` +
                    `💰 $${(result.price || 0).toFixed(2)}\n` +
                    `📊 ${amount.toFixed(6)}\n` +
                    `🛑 Stop: $${position.stopLoss.toFixed(2)}\n` +
                    `🎯 Target: $${position.takeProfit.toFixed(2)}`;

                this.emit('sendTelegramMessage', buyMessage);

                return {
                    success: true,
                    order
                };
            } else {
                // ✨ Close position and calculate P&L
                const position = this.portfolio.get(symbol);
                console.log("💰 Closing position2:", position);
                if (position) {
                    const pnl = this.calculatePnL(position, result.amount);
                    this.updateTradingStats(pnl);
                    this.portfolio.delete(symbol);

                    await this.sendPnLNotification(symbol, position, result.amount, pnl);
                    console.log(`✅ LIVE SELL executed: ${symbol} @ $${result.price} | P&L: $${pnl.absolute.toFixed(2)}`);
                }
            }

            this.emit('orderExecuted', order);
            return {
                success: true,
                order
            };
        } else {
            throw new Error(result.error);
        }
        // } catch (error) {
        //     console.error('❌ Live order failed:', error);
        //     return {
        //         success: false,
        //         error: error.message
        //     };
        // }
    }

    // ✨ Paper trading (for testing)
    async executePaperTrade(symbol, side, amount, signal) {
        try {
            const currentPrice = signal.entryPoint || 50000;
            const quantity = amount / currentPrice;

            const order = {
                id: `paper_${Date.now()}`,
                symbol: symbol,
                side: side.toUpperCase(),
                quantity: quantity,
                price: currentPrice,
                timestamp: Date.now(),
                mode: 'PAPER',
                signal: signal
            };

            this.orderHistory.push(order);

            if (side === 'buy') {
                this.balance.USDT -= amount;
                this.portfolio.set(symbol, {
                    symbol: symbol,
                    entryPrice: currentPrice,
                    quantity: quantity,
                    entryTime: new Date(),
                    stopLoss: signal.stopLoss,
                    takeProfit: signal.takeProfit
                });
            } else {
                const position = this.portfolio.get(symbol);
                console.log("💰 Closing position:", position);
                if (position) {
                    const pnl = this.calculatePnL(position, currentPrice);
                    this.updateTradingStats(pnl);
                    this.balance.USDT += amount;
                    this.portfolio.delete(symbol);
                    await this.sendPnLNotification(symbol, position, currentPrice, pnl);
                }
            }

            console.log(`✅ Paper trade: ${side.toUpperCase()} ${symbol} @ $${currentPrice}`);
            this.emit('orderExecuted', order);
            return {
                success: true,
                order
            };

        } catch (error) {
            console.error('❌ Paper trade failed:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    // ✨ P&L calculation
    calculatePnL(position, exitPrice) {
        const pnl = (exitPrice - position.entryPrice) * position.quantity;
        const pnlPercent = ((exitPrice - position.entryPrice) / position.entryPrice) * 100;

        return {
            absolute: pnl,
            percentage: pnlPercent,
            isProfit: pnl > 0
        };
    }

    updateTradingStats(pnl) {
        this.tradingStats.totalPnL += pnl.absolute;
        this.tradingStats.dailyPnL += pnl.absolute;

        if (pnl.isProfit) {
            this.tradingStats.winTrades++;
        } else {
            this.tradingStats.lossTrades++;
        }
    }

    // ✨ Real-time monitoring for live trading
    startPnLMonitoring() {
        this.priceMonitor = setInterval(async () => {
            if (this.portfolio.size > 0) {
                await this.updatePortfolioPrices();
                await this.checkStopLossAndTakeProfit();
            }
        }, 30000);
    }

    async updatePortfolioPrices() {
        try {
            for (const [symbol, position] of this.portfolio) {
                const ticker = await this.binanceLive.exchange.fetchTicker(symbol);
                position.currentPrice = ticker.last;
                position.unrealizedPnL = this.calculatePnL(position, ticker.last);
                this.portfolio.set(symbol, position);
            }
        } catch (error) {
            console.error('❌ Price update failed:', error.message);
        }
    }

    // Add to TradingAgent class:

    async checkStopLossAndTakeProfit() {
        for (const [symbol, position] of this.portfolio) {
            const currentPrice = position.currentPrice;

            // ✨ Smart Stop Loss (Market conditions)
            if (position.stopLoss && currentPrice <= position.stopLoss) {
                console.log(`🛑 STOP LOSS TRIGGERED: ${symbol} @ $${currentPrice}`);
                await this.executeLiveOrder(symbol, 'sell', position.quantity, {
                    type: 'stop_loss',
                    reason: `Stop loss hit at $${currentPrice}`
                });
            }

            // ✨ Smart Take Profit  
            if (position.takeProfit && currentPrice >= position.takeProfit) {
                console.log(`🎯 TAKE PROFIT TRIGGERED: ${symbol} @ $${currentPrice}`);
                await this.executeLiveOrder(symbol, 'sell', position.quantity, {
                    type: 'take_profit',
                    reason: `Take profit hit at $${currentPrice}`
                });
            }

            // ✨ Emergency Exit (Market crash detection)
            if (position.unrealizedPnL && position.unrealizedPnL.percentage < -10) {
                console.log(`🚨 EMERGENCY EXIT: ${symbol} - Loss > 10%`);
                await this.executeLiveOrder(symbol, 'sell', position.quantity, {
                    type: 'emergency_exit',
                    reason: `Emergency exit - Loss: ${position.unrealizedPnL.percentage.toFixed(2)}%`
                });
            }

            // ✨ Trailing Stop (Lock in profits)
            if (position.unrealizedPnL && position.unrealizedPnL.percentage > 5) {
                const trailingStop = currentPrice * 0.95; // 5% trailing stop
                if (trailingStop > position.stopLoss) {
                    position.stopLoss = trailingStop;
                    console.log(`📈 TRAILING STOP updated: ${symbol} @ $${trailingStop.toFixed(2)}`);
                }
            }
        }
    }

    // ✨ Enhanced P&L notification with more details
    async sendPnLNotification(symbol, position, exitPrice, pnl) {
        const emoji = pnl.isProfit ? '🟢' : '🔴';
        const status = pnl.isProfit ? 'PROFIT' : 'LOSS';

        // Determine exit reason
        let exitReason = '🔄 Manual';
        if (position.signal?.type === 'stop_loss') exitReason = '🛑 Stop Loss';
        if (position.signal?.type === 'take_profit') exitReason = '🎯 Take Profit';
        if (position.signal?.type === 'emergency_exit') exitReason = '🚨 Emergency';

        const message = `${emoji} <b>${status} - ${symbol}</b>\n\n` +
            `📈 <b>Entry:</b> $${position.entryPrice.toFixed(2)}\n` +
            `📉 <b>Exit:</b> $${exitPrice.toFixed(2)}\n` +
            `💰 <b>P&L:</b> $${pnl.absolute.toFixed(2)} (${pnl.percentage.toFixed(2)}%)\n` +
            `📊 <b>Quantity:</b> ${position.quantity.toFixed(6)}\n` +
            `⏰ <b>Duration:</b> ${this.getPositionDuration(position.entryTime)}\n` +
            `🏷️ <b>Exit Type:</b> ${exitReason}\n\n` +
            `📈 <b>Total P&L:</b> $${this.tradingStats.totalPnL.toFixed(2)}\n` +
            `🎯 <b>Win Rate:</b> ${this.getWinRate()}%\n` +
            `📊 <b>Total Trades:</b> ${this.tradingStats.totalTrades}`;

        this.emit('sendTelegramMessage', message);
    }

    getPositionDuration(entryTime) {
        const duration = Date.now() - entryTime.getTime();
        const hours = Math.floor(duration / (1000 * 60 * 60));
        const minutes = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60));
        return `${hours}h ${minutes}m`;
    }

    getWinRate() {
        const totalClosedTrades = this.tradingStats.winTrades + this.tradingStats.lossTrades;
        if (totalClosedTrades === 0) return 0;
        return ((this.tradingStats.winTrades / totalClosedTrades) * 100).toFixed(1);
    }

    getPortfolioStatus() {
        const positions = Array.from(this.portfolio.values());
        let totalUnrealizedPnL = 0;

        positions.forEach(pos => {
            if (pos.unrealizedPnL) {
                totalUnrealizedPnL += pos.unrealizedPnL.absolute;
            }
        });

        return {
            openPositions: positions.length,
            totalUnrealizedPnL: totalUnrealizedPnL,
            totalRealizedPnL: this.tradingStats.totalPnL,
            winRate: this.getWinRate(),
            totalTrades: this.tradingStats.totalTrades,
            positions: positions
        };
    }

    convertCoinToSymbol(coin) {
        const mapping = {
            'bitcoin': 'BTCUSDT',
            'ethereum': 'ETHUSDT'
        };
        return mapping[coin] || `${coin.toUpperCase()}USDT`;
    }

    calculatePositionSize(signal) {
        const riskPercentage = 0.02;
        const accountValue = this.balance?.USDT.free || 0;
        const maxTradeValue = accountValue * 0.01;
        console.log(`💰 Account USDT: ${accountValue}`);
        console.log(`📊 Max trade value: ${maxTradeValue}`);
        if (signal.stopLoss && signal.entryPoint) {
            const riskPerUnit = Math.abs(signal.entryPoint - signal.stopLoss);
            const riskAmount = accountValue * riskPercentage;
            const quantity = riskAmount / riskPerUnit;
            return Math.min(quantity * signal.entryPoint, maxTradeValue);
        }

        return accountValue * 0.01;
    }

    getStatus() {
        return {
            isRunning: this.isRunning,
            tradingMode: this.tradingMode,
            balance: this.balance,
            activePositions: this.portfolio.size,
            totalTrades: this.orderHistory.length
        };
    }

    async stop() {
        this.isRunning = false;
        if (this.priceMonitor) {
            clearInterval(this.priceMonitor);
        }
        console.log('🛑 Trading Agent stopped');
    }
}

export default TradingAgent;
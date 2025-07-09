import {
    getAlerts,
    setAlerts
} from '../data/alerts.js';

// Alert system
class AlertSystem {
    constructor() {
        this.thresholds = {
            priceChange: 5, // 5% change
            rsiOverbought: 70,
            rsiOversold: 30,
            volumeSpike: 50, // 50% volume increase

            // New trading thresholds
            stopLossHit: 0.5, // 0.5% buffer before stop loss
            takeProfitApproach: 2, // 2% before take profit
            entryOpportunity: 1, // 1% near entry point
            riskRewardMin: 1.5 // Minimum risk/reward ratio
        };

        this.activeSignals = new Map();
    }

    // Set trading signals from AI analysis
    setTradingSignals(signals) {
        signals.forEach(signal => {
            if (signal.action === 'BUY' || signal.action === 'SELL') {
                this.activeSignals.set(signal.coin, {
                    ...signal,
                    status: 'ACTIVE',
                    createdAt: new Date()
                });
            }
        });
    }

    // Check alerts for both general market and trading signals
    checkAlerts(coinId, currentData, previousData, indicators) {
        const alerts = [];

        // Original market alerts
        alerts.push(...this.checkMarketAlerts(coinId, currentData, previousData, indicators));

        // New trading signal alerts
        alerts.push(...this.checkTradingSignals(coinId, currentData));

        return alerts;
    }

    checkMarketAlerts(coinId, currentData, previousData, indicators) {
        const alerts = [];

        // Price change alert
        if (previousData && currentData.usd && previousData.usd) {
            const priceChange = Math.abs(((currentData.usd - previousData.usd) / previousData.usd) * 100);
            if (priceChange >= this.thresholds.priceChange) {
                alerts.push({
                    type: 'PRICE_CHANGE',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} thay đổi ${priceChange.toFixed(2)}% trong thời gian ngắn`,
                    severity: priceChange >= 10 ? 'HIGH' : 'MEDIUM',
                    timestamp: new Date(),
                    currentPrice: currentData.usd
                });
            }
        }

        // RSI alerts
        if (indicators.rsi && indicators.rsi.value) {
            if (indicators.rsi.value >= this.thresholds.rsiOverbought) {
                alerts.push({
                    type: 'RSI_OVERBOUGHT',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} RSI = ${indicators.rsi.value} - Vùng quá mua, có thể giảm`,
                    severity: 'MEDIUM',
                    timestamp: new Date(),
                    currentPrice: currentData.usd,
                    recommendation: 'Cân nhắc SELL hoặc giảm position'
                });
            } else if (indicators.rsi.value <= this.thresholds.rsiOversold) {
                alerts.push({
                    type: 'RSI_OVERSOLD',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} RSI = ${indicators.rsi.value} - Vùng quá bán, có thể tăng`,
                    severity: 'MEDIUM',
                    timestamp: new Date(),
                    currentPrice: currentData.usd,
                    recommendation: 'Cân nhắc BUY hoặc tăng position'
                });
            }
        }

        return alerts;
    }

    checkTradingSignals(coinId, currentData) {
        const alerts = [];
        const signal = this.activeSignals.get(coinId);

        if (!signal || signal.status !== 'ACTIVE') {
            return alerts;
        }

        const currentPrice = currentData.usd;

        // Entry point alert
        if (signal.entryPoint) {
            const entryDiff = Math.abs((currentPrice - signal.entryPoint) / signal.entryPoint * 100);
            if (entryDiff <= this.thresholds.entryOpportunity) {
                alerts.push({
                    type: 'ENTRY_OPPORTUNITY',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} đang gần Entry Point: $${signal.entryPoint} (hiện tại: $${currentPrice})`,
                    severity: 'HIGH',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.entryPoint,
                    action: signal.action,
                    recommendation: `Cân nhắc ${signal.action} tại giá hiện tại`
                });
            }
        }

        // Stop loss alert
        if (signal.stopLoss) {
            const stopLossDiff = signal.action === 'BUY' ?
                (signal.stopLoss - currentPrice) / currentPrice * 100 :
                (currentPrice - signal.stopLoss) / currentPrice * 100;

            if (stopLossDiff <= this.thresholds.stopLossHit && stopLossDiff >= -2) {
                alerts.push({
                    type: 'STOP_LOSS_ALERT',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} đang gần Stop Loss: $${signal.stopLoss} (hiện tại: $${currentPrice})`,
                    severity: 'CRITICAL',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.stopLoss,
                    action: 'CLOSE_POSITION',
                    recommendation: 'Cân nhắc cắt lỗ để bảo vệ vốn'
                });
            }
        }

        // Take profit alert
        if (signal.takeProfit) {
            const takeProfitDiff = signal.action === 'BUY' ?
                (signal.takeProfit - currentPrice) / currentPrice * 100 :
                (currentPrice - signal.takeProfit) / currentPrice * 100;

            if (takeProfitDiff <= this.thresholds.takeProfitApproach && takeProfitDiff >= 0) {
                alerts.push({
                    type: 'TAKE_PROFIT_ALERT',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} đang gần Take Profit: $${signal.takeProfit} (hiện tại: $${currentPrice})`,
                    severity: 'HIGH',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.takeProfit,
                    action: 'TAKE_PROFIT',
                    recommendation: 'Cân nhắc chốt lời một phần hoặc toàn bộ'
                });
            }
        }

        // Signal expiry alert (optional - if signal is too old)
        const signalAge = (new Date() - signal.createdAt) / (1000 * 60 * 60); // hours
        if (signalAge > 24) { // Signal older than 24 hours
            alerts.push({
                type: 'SIGNAL_EXPIRY',
                coin: coinId,
                message: `${coinId.toUpperCase()} - Tín hiệu giao dịch đã cũ (${signalAge.toFixed(1)}h), cần phân tích mới`,
                severity: 'LOW',
                timestamp: new Date(),
                currentPrice: currentPrice,
                recommendation: 'Cần phân tích lại thị trường'
            });
        }

        return alerts;
    }

    // Get all active trading signals
    getActiveSignals() {
        return Array.from(this.activeSignals.values());
    }

    // Update signal status
    updateSignalStatus(coinId, status) {
        const signal = this.activeSignals.get(coinId);
        if (signal) {
            signal.status = status;
            signal.updatedAt = new Date();
        }
    }

    // Remove expired or completed signals
    cleanupSignals() {
        const now = new Date();
        for (const [coinId, signal] of this.activeSignals.entries()) {
            const ageInHours = (now - signal.createdAt) / (1000 * 60 * 60);
            if (ageInHours > 72 || signal.status === 'COMPLETED') { // 3 days
                this.activeSignals.delete(coinId);
            }
        }
    }
}

export default new AlertSystem();
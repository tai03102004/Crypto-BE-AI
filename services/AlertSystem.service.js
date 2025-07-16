// Alert system
class AlertSystem {
    constructor() {
        this.thresholds = {
            priceChange: 5, // 5% change
            rsiOverbought: 70,
            rsiOversold: 30,
            volumeSpike: 50, // 50% volume increase

            // Multi-indicator thresholds
            strongSignalConfirmation: 2, // Need 2+ indicators to confirm
            criticalRSI: 80, // More extreme RSI levels
            criticalRSILow: 20,

            // New trading thresholds
            stopLossHit: 0.5,
            takeProfitApproach: 2,
            entryOpportunity: 1,
            riskRewardMin: 1.5
        };

        this.activeSignals = new Map();

        this.alertHistory = [];
    }

    // Set trading signals from AI analysis
    setTradingSignals(signals) {
        signals.forEach(signal => {
            if (signal.action === 'BUY' || signal.action === 'SELL') {
                const signalData = {
                    ...signal,
                    status: 'ACTIVE',
                    createdAt: new Date(),
                    id: `${signal.coin}_${Date.now()}`
                };
                this.activeSignals.set(signal.coin, signalData);
                console.log(`Signal set for ${signal.coin}:`, signalData);
            }
        });
    }

    // Check alerts with multiple indicators
    checkAlerts(coinId, currentData, previousData, techData) {
        const alerts = [];

        // Market alerts with multiple confirmations
        alerts.push(...this.checkMarketAlerts(coinId, currentData, previousData, techData));

        // Trading signal alerts
        alerts.push(...this.checkTradingSignals(coinId, currentData));

        return alerts;
    }

    checkMarketAlerts(coinId, currentData, previousData, techData) {
        const alerts = [];

        // Price change alert
        if (previousData && currentData.usd && previousData.usd && previousData.usd !== currentData.usd) {
            const priceChange = Math.abs(((currentData.usd - previousData.usd) / previousData.usd) * 100);
            if (priceChange >= this.thresholds.priceChange) {
                alerts.push({
                    type: 'PRICE_CHANGE',
                    coin: coinId,
                    message: `${coinId.toUpperCase()} change ${priceChange.toFixed(2)}% in a short time`,
                    severity: priceChange >= 10 ? 'HIGH' : 'MEDIUM',
                    timestamp: new Date(),
                    currentPrice: currentData.usd
                });
            }
        }

        // IMPROVED: Multi-indicator signal analysis
        const signals = this.analyzeMultipleIndicators(coinId, currentData, techData);
        alerts.push(...signals);

        return alerts;
    }

    // NEW: Analyze multiple indicators together
    analyzeMultipleIndicators(coinId, currentData, techData) {
        const alerts = [];
        const confirmations = [];

        if (!techData) return alerts;

        // RSI Analysis
        let rsiSignal = null;
        if (techData.rsi && typeof techData.rsi === 'number') {
            if (techData.rsi >= this.thresholds.criticalRSI) {
                rsiSignal = 'CRITICAL_OVERBOUGHT';
                confirmations.push({
                    indicator: 'RSI',
                    signal: 'SELL',
                    strength: 'CRITICAL',
                    value: techData.rsi
                });
            } else if (techData.rsi >= this.thresholds.rsiOverbought) {
                rsiSignal = 'OVERBOUGHT';
                confirmations.push({
                    indicator: 'RSI',
                    signal: 'SELL',
                    strength: 'MEDIUM',
                    value: techData.rsi
                });
            } else if (techData.rsi <= this.thresholds.criticalRSILow) {
                rsiSignal = 'CRITICAL_OVERSOLD';
                confirmations.push({
                    indicator: 'RSI',
                    signal: 'BUY',
                    strength: 'CRITICAL',
                    value: techData.rsi
                });
            } else if (techData.rsi <= this.thresholds.rsiOversold) {
                rsiSignal = 'OVERSOLD';
                confirmations.push({
                    indicator: 'RSI',
                    signal: 'BUY',
                    strength: 'MEDIUM',
                    value: techData.rsi
                });
            }
        }

        // MACD Analysis
        if (techData.macd && techData.macd_signal) {
            const macdDiff = techData.macd - techData.macd_signal;
            if (macdDiff > 0 && techData.macd_trend === 'BULLISH') {
                confirmations.push({
                    indicator: 'MACD',
                    signal: 'BUY',
                    strength: 'MEDIUM',
                    value: macdDiff.toFixed(2)
                });
            } else if (macdDiff < 0 && techData.macd_trend === 'BEARISH') {
                confirmations.push({
                    indicator: 'MACD',
                    signal: 'SELL',
                    strength: 'MEDIUM',
                    value: macdDiff.toFixed(2)
                });
            }
        }

        // EMA/SMA Analysis
        if (techData.ema_signal === 'STRONG_BULLISH' || techData.sma_signal === 'STRONG_BULLISH') {
            confirmations.push({
                indicator: 'MA',
                signal: 'BUY',
                strength: 'HIGH',
                value: 'Strong trend'
            });
        } else if (techData.ema_signal === 'STRONG_BEARISH' || techData.sma_signal === 'STRONG_BEARISH') {
            confirmations.push({
                indicator: 'MA',
                signal: 'SELL',
                strength: 'HIGH',
                value: 'Strong downtrend'
            });
        }

        // Bollinger Bands Analysis
        if (techData.bollinger && techData.bollinger.signal) {
            if (techData.bollinger.signal === 'BULLISH') {
                confirmations.push({
                    indicator: 'BOLLINGER',
                    signal: 'BUY',
                    strength: 'MEDIUM',
                    value: 'Above middle band'
                });
            } else if (techData.bollinger.signal === 'BEARISH') {
                confirmations.push({
                    indicator: 'BOLLINGER',
                    signal: 'SELL',
                    strength: 'MEDIUM',
                    value: 'Below middle band'
                });
            }
        }

        // Volume Analysis
        if (techData.volume_signal === 'HIGH' || techData.volume_signal === 'VERY_HIGH') {
            confirmations.push({
                indicator: 'VOLUME',
                signal: 'CONFIRMATION',
                strength: 'HIGH',
                value: 'High volume'
            });
        }

        // Create alerts based on confirmations
        const buyConfirmations = confirmations.filter(c => c.signal === 'BUY');
        const sellConfirmations = confirmations.filter(c => c.signal === 'SELL');
        const volumeConfirmation = confirmations.find(c => c.signal === 'CONFIRMATION');

        // Strong BUY signal (multiple confirmations)
        if (buyConfirmations.length >= this.thresholds.strongSignalConfirmation) {
            const criticalCount = buyConfirmations.filter(c => c.strength === 'CRITICAL').length;
            alerts.push({
                type: criticalCount > 0 ? 'STRONG_BUY_SIGNAL' : 'BUY_SIGNAL',
                coin: coinId,
                message: `${coinId.toUpperCase()} - Strong BUY signal from ${buyConfirmations.length} indicators: ${buyConfirmations.map(c => c.indicator).join(', ')}`,
                severity: criticalCount > 0 ? 'CRITICAL' : 'HIGH',
                timestamp: new Date(),
                currentPrice: currentData.usd,
                confirmations: buyConfirmations,
                hasVolumeConfirmation: !!volumeConfirmation,
                recommendation: 'Consider BUY position'
            });
        }

        // Strong SELL signal (multiple confirmations)
        if (sellConfirmations.length >= this.thresholds.strongSignalConfirmation) {
            const criticalCount = sellConfirmations.filter(c => c.strength === 'CRITICAL').length;
            alerts.push({
                type: criticalCount > 0 ? 'STRONG_SELL_SIGNAL' : 'SELL_SIGNAL',
                coin: coinId,
                message: `${coinId.toUpperCase()} - Strong SELL signal from ${sellConfirmations.length} indicators: ${sellConfirmations.map(c => c.indicator).join(', ')}`,
                severity: criticalCount > 0 ? 'CRITICAL' : 'HIGH',
                timestamp: new Date(),
                currentPrice: currentData.usd,
                confirmations: sellConfirmations,
                hasVolumeConfirmation: !!volumeConfirmation,
                recommendation: 'Consider SELL position'
            });
        }

        // Conflicting signals warning
        if (buyConfirmations.length > 0 && sellConfirmations.length > 0) {
            alerts.push({
                type: 'CONFLICTING_SIGNALS',
                coin: coinId,
                message: `${coinId.toUpperCase()} - Conflicting signals: ${buyConfirmations.length} BUY vs ${sellConfirmations.length} SELL indicators`,
                severity: 'MEDIUM',
                timestamp: new Date(),
                currentPrice: currentData.usd,
                recommendation: 'Wait for clearer signals or use smaller position size'
            });
        }

        return alerts;
    }

    checkTradingSignals(coinId, currentData) {
        const alerts = [];
        const signal = this.activeSignals.get(coinId);

        console.log(`Checking trading signals for ${coinId.toUpperCase()}:`, signal);

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
                    message: `${coinId.toUpperCase()} is nearing Entry Point: $${signal.entryPoint} (current: $${currentPrice})`,
                    severity: 'HIGH',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.entryPoint,
                    action: signal.action,
                    recommendation: `Consider ${signal.action} at current price`
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
                    message: `${coinId.toUpperCase()} is nearing Stop Loss: $${signal.stopLoss} (current: $${currentPrice})`,
                    severity: 'CRITICAL',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.stopLoss,
                    action: 'CLOSE_POSITION',
                    recommendation: 'Consider cutting losses to protect capital'
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
                    message: `${coinId.toUpperCase()} is nearing Take Profit: $${signal.takeProfit} (current: $${currentPrice})`,
                    severity: 'HIGH',
                    timestamp: new Date(),
                    currentPrice: currentPrice,
                    targetPrice: signal.takeProfit,
                    action: 'TAKE_PROFIT',
                    recommendation: 'Consider taking partial or full profits'
                });
            }
        }

        // Signal expiry alert
        const signalAge = (new Date() - signal.createdAt) / (1000 * 60 * 60);
        if (signalAge > 24) {
            alerts.push({
                type: 'SIGNAL_EXPIRY',
                coin: coinId,
                message: `${coinId.toUpperCase()} - Trading signal is old (${signalAge.toFixed(1)}h), need new analysis`,
                severity: 'LOW',
                timestamp: new Date(),
                currentPrice: currentPrice,
                recommendation: 'Need to re-analyze the market'
            });
        }

        return alerts;
    }

    // Get all active trading signals
    getActiveSignals() {
        console.log(`Active signals count: ${this.activeSignals}`);
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
            if (ageInHours > 72 || signal.status === 'COMPLETED') {
                this.activeSignals.delete(coinId);
            }
        }
    }
}

export default new AlertSystem();
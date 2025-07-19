import EventEmitter from 'events';

class RiskManager extends EventEmitter {
    constructor() {
        super();
        this.riskLimits = {
            maxPositionSize: 0.1, // 10% of portfolio
            maxDailyLoss: 0.05, // 5% daily loss limit
            minConfidence: 0.7, // Minimum signal confidence
            maxOpenPositions: 3 // Maximum open positions
        };
        this.dailyPnL = 0;
        this.openPositions = 0;
    }

    handleEvent(eventName, data) {
        switch (eventName) {
            case 'validateSignal':
                this.validateSignal(data);
                break;
        }
    }

    async validateSignal(signal) {
        const riskChecks = [
            this.checkConfidenceLevel(signal),
            this.checkPositionLimits(signal),
            this.checkDailyLoss(),
            this.checkMarketConditions(signal)
        ];

        const approved = riskChecks.every(check => check);

        if (approved) {
            this.emit('signalApproved', {
                ...signal,
                riskApproved: true,
                approvedAt: Date.now()
            });
        } else {
            this.emit('signalRejected', {
                signal,
                reason: 'Risk management rejection',
                failedChecks: riskChecks
            });
        }
    }

    checkConfidenceLevel(signal) {
        return signal.confidence >= this.riskLimits.minConfidence;
    }

    checkPositionLimits(signal) {
        return this.openPositions < this.riskLimits.maxOpenPositions;
    }

    checkDailyLoss() {
        return this.dailyPnL > -this.riskLimits.maxDailyLoss;
    }

    checkMarketConditions(signal) {
        // Add market volatility checks, etc.
        return true;
    }

    getStatus() {
        return {
            dailyPnL: this.dailyPnL,
            openPositions: this.openPositions,
            riskLimits: this.riskLimits
        };
    }
}

export default RiskManager;
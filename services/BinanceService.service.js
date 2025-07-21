import ccxt from 'ccxt';

class BinanceLiveTrading {
    constructor() {
        this.exchange = null;
        this.isLive = false;
        this.accountInfo = null;
        this.isInitialized = false;
        this.timeOffset = 0;
    }

    async initialize() {
        if (!process.env.BINANCE_API_KEY || !process.env.BINANCE_SECRET_KEY) {
            console.error('❌ Missing Binance API credentials');
            console.log('💡 Please set BINANCE_API_KEY and BINANCE_SECRET_KEY in .env file');
            return false;
        }
        console.log(`🔑 API Key: ${process.env.BINANCE_API_KEY.substring(0, 8)}...`);
        console.log(`🔐 Secret: ${process.env.BINANCE_SECRET_KEY ? 'SET' : 'NOT SET'}`);
        console.log(`🧪 Testnet: ${process.env.BINANCE_TESTNET}`);
        this.exchange = new ccxt.binance({
            apiKey: process.env.BINANCE_API_KEY,
            secret: process.env.BINANCE_SECRET_KEY,
            sandbox: process.env.BINANCE_TESTNET === 'true',
            enableRateLimit: true,
            options: {
                defaultType: 'spot', // Use 'spot' for spot trading
                timeDifference: this.timeOffset,
                adjustForTimeDifference: true,
                recvWindow: 60000,
            }
        });

        try {
            console.log('⏳ Loading markets...');
            await this.exchange.loadMarkets();
            try {
                const serverTime = await this.exchange.fetchTime();
                const localTime = Date.now();
                this.timeOffset = serverTime - localTime;
                this.exchange.options.timeDifference = this.timeOffset;
                console.log('⏰ Time synchronized with Binance server');
            } catch (timeError) {
                console.warn('⚠️ Could not sync time, continuing without time offset');
                this.timeOffset = 0;
            }
            const balance = await this.exchange.fetchBalance();
            await this.getDetailedAccountInfo();
            console.log('✅ Binance connection established');
            console.log('💰 Account balance:', balance.USDT?.free || 0, 'USDT');
            this.isLive = true;
            this.isInitialized = true;
            return true;
        } catch (error) {
            console.error('❌ Binance connection failed:', error.message);
            return false;
        }
    }

    async getDetailedAccountInfo() {
        try {
            // Get account information
            const accountInfo = await this.exchange.fetchBalance();

            // Get account status and permissions
            const accountData = await this.exchange.privateGetAccount();

            this.accountInfo = {
                accountType: accountData.accountType,
                canTrade: accountData.canTrade,
                canWithdraw: accountData.canWithdraw,
                canDeposit: accountData.canDeposit,
                updateTime: new Date(accountData.updateTime),
                permissions: accountData.permissions,
                balances: accountData.balances.filter(b => parseFloat(b.free) > 0 || parseFloat(b.locked) > 0)
            };

            console.log('\n🔍 ==================== BINANCE ACCOUNT INFO ====================');
            console.log('👤 Account Type:', this.accountInfo.accountType);
            console.log('📊 Trading Enabled:', this.accountInfo.canTrade);
            console.log('💸 Withdraw Enabled:', this.accountInfo.canWithdraw);
            console.log('💰 Deposit Enabled:', this.accountInfo.canDeposit);
            console.log('🔑 Permissions:', this.accountInfo.permissions);
            console.log('⏰ Last Update:', this.accountInfo.updateTime.toLocaleString());
            console.log('🌐 Testnet Mode:', process.env.BINANCE_TESTNET === 'true' ? 'YES' : 'NO');

            console.log('\n💰 ==================== ACCOUNT BALANCES ====================');
            this.accountInfo.balances
                .filter(balance => ['ETH', 'BTC'].includes(balance.asset))
                .forEach(balance => {
                    const free = parseFloat(balance.free);
                    const locked = parseFloat(balance.locked);
                    const total = free + locked;

                    if (total > 0) {
                        console.log(`${balance.asset.padEnd(8)} | Free: ${free.toFixed(8)} | Locked: ${locked.toFixed(8)} | Total: ${total.toFixed(8)}`);
                    }
                });

            console.log('===============================================================\n');

            return this.accountInfo;

        } catch (error) {
            console.error('❌ Failed to get account info:', error.message);
            return null;
        }
    }

    async createMarketOrder(symbol, side, amountUSD) {
        // try {
        if (!this.isLive) {
            throw new Error('Binance not connected');
        }

        if (!amountUSD || isNaN(amountUSD) || amountUSD <= 0) {
            throw new Error(`Invalid amountUSD: ${amountUSD}`);
        }

        console.log('>>>>> DEBUG ORDER PARAMS <<<<<');
        console.log('Symbol:', symbol);
        console.log('Side:', side);
        console.log('Amount (USD):', amountUSD, typeof amountUSD);

        // Fetch ticker price
        const ticker = await this.exchange.fetchTicker(symbol);
        const price = ticker.last;

        console.log('Fetched price for', symbol, '=>', price);

        // Tính toán amount theo đơn vị "base" (ví dụ BTC nếu BTC/USDT)
        const amountBase = amountUSD / price;

        console.log('Calculated base amount:', amountBase);

        // Check tối thiểu Binance yêu cầu (tùy cặp coin, thường >10 USDT)
        const market = await this.exchange.loadMarkets();
        const minNotional = market[symbol]?.limits?.cost?.min || 10;

        console.log('Minimum notional for', symbol, '=', minNotional);

        if (amountUSD < minNotional) {
            throw new Error(`Order notional ($${amountUSD}) is below minimum ($${minNotional})`);
        }

        // Gửi lệnh order
        const order = await this.exchange.createOrder(
            symbol,
            'market',
            side,
            this.exchange.amountToPrecision(symbol, amountBase)
        );

        console.log('✅ Live order created:', order);

        return {
            success: true,
            orderId: order.id,
            symbol: order.symbol,
            side: order.side,
            amount: order.amount,
            status: order.status,
            timestamp: order.timestamp
        };
        // } catch (error) {
        //     console.error('❌ Live order failed:', error.message);
        //     console.error('📄 Full error:', error);
        //     return {
        //         success: false,
        //         error: error.message
        // };
    }



    async getAccountBalance() {
        try {
            const balance = await this.exchange.fetchBalance();

            // Log current balance info
            console.log('\n💰 ==================== CURRENT BALANCE ====================');
            console.log('USDT Total:', balance.USDT?.total || 0);
            console.log('BTC Free:', balance.BTC?.free || 0);
            console.log('ETH Free:', balance.ETH?.free || 0);
            console.log('===========================================================\n');

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

    async testConnection() {
        try {
            console.log('\n🧪 ==================== CONNECTION TEST ====================');
            if (!this.exchange) {
                console.log('❌ Exchange not initialized, attempting to initialize...');
                const initialized = await this.initialize();
                if (!initialized) {
                    return {
                        success: false,
                        error: 'Failed to initialize exchange'
                    };
                }
            }
            // Test 1: Basic connectivity
            console.log('⏳ Testing basic connectivity...');
            await this.exchange.loadMarkets();
            console.log('✅ Market data loaded successfully');

            // Test 2: Account access
            console.log('⏳ Testing account access...');
            const balance = await this.exchange.fetchBalance();
            console.log('✅ Account balance retrieved successfully');

            // Test 3: Account permissions
            console.log('⏳ Testing account permissions...');
            const accountData = await this.exchange.privateGetAccount();
            console.log('✅ Account data retrieved successfully');

            console.log('\n📋 Connection Test Results:');
            console.log(`   API Key: ${process.env.BINANCE_API_KEY ? process.env.BINANCE_API_KEY.substring(0, 8) + '...' : 'NOT SET'}`);
            console.log(`   Secret Key: ${process.env.BINANCE_SECRET_KEY ? 'SET (hidden)' : 'NOT SET'}`);
            console.log(`   Testnet: ${process.env.BINANCE_TESTNET}`);
            console.log(`   Trading Enabled: ${accountData.canTrade}`);
            console.log(`   Account Type: ${accountData.accountType}`);
            console.log('===========================================================\n');

            return {
                success: true,
                accountType: accountData.accountType,
                canTrade: accountData.canTrade,
                balanceCount: Object.keys(balance).length
            };

        } catch (error) {
            console.error('❌ Connection test failed:', error.message);
            return {
                success: false,
                error: error.message
            };
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
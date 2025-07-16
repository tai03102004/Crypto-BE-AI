import axios from 'axios';

/**
 * Service to interact with CoinGecko API for cryptocurrency data.
 * Provides methods to fetch current prices and historical data for cryptocurrencies.
 */

class CoinGeckoService {
    constructor() {
        this.baseURL = 'https://api.coingecko.com/api/v3';
        this.apiKey = process.env.COINGECKO_API_KEY || null;
        this.cachedData = new Map();
        this.lastFetch = new Map();

        this.rateLimitConfig = {
            freeCallsPerMinute: 5,
            timeWindow: 60000,
            callsInCurrentWindow: 0,
            windowStart: Date.now()
        };

        this.retryConfig = {
            maxRetries: 3,
            baseDelay: 1000,
            maxDelay: 10000,
            backoffMultiplier: 2
        };

        this.requestQueue = [];
        this.isProcessingQueue = false;

        this.axiosInstance = axios.create({
            timeout: 30000,
            headers: {
                'accept': 'application/json',
                'User-Agent': 'CoinGecko-Service/1.0'
            }
        });

        this.setupInterceptors();
    }

    setupInterceptors() {
        this.axiosInstance.interceptors.request.use(
            (config) => {
                if (this.apiKey) {
                    config.headers['x-cg-pro-api-key'] = this.apiKey;
                }
                return config;
            },
            (error) => Promise.reject(error)
        );

        this.axiosInstance.interceptors.response.use(
            (response) => response,
            (error) => {
                if (error.response?.status === 429) {
                    console.warn('Rate limit exceeded, will retry with exponential backoff');
                }
                return Promise.reject(error);
            }
        );
    }

    checkRateLimit() {
        const now = Date.now();
        const maxCalls = this.rateLimitConfig.freeCallsPerMinute;

        if (now - this.rateLimitConfig.windowStart > this.rateLimitConfig.timeWindow) {
            this.rateLimitConfig.callsInCurrentWindow = 0;
            this.rateLimitConfig.windowStart = now;
        }

        return this.rateLimitConfig.callsInCurrentWindow < maxCalls;
    }

    incrementRateLimit() {
        this.rateLimitConfig.callsInCurrentWindow++;
    }

    getDelayUntilNextSlot() {
        const timeRemaining = this.rateLimitConfig.timeWindow - (Date.now() - this.rateLimitConfig.windowStart);
        return Math.max(0, timeRemaining);
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    getBackoffDelay(attempt) {
        const delay = this.retryConfig.baseDelay * Math.pow(this.retryConfig.backoffMultiplier, attempt);
        return Math.min(delay, this.retryConfig.maxDelay);
    }

    async processQueue() {
        if (this.isProcessingQueue || this.requestQueue.length === 0) {
            return;
        }

        this.isProcessingQueue = true;

        while (this.requestQueue.length > 0) {
            if (!this.checkRateLimit()) {
                const delay = this.getDelayUntilNextSlot();
                console.log(`Rate limit reached, waiting ${delay}ms before next request`);
                await this.sleep(delay);
                continue;
            }

            const {
                request,
                resolve,
                reject
            } = this.requestQueue.shift();

            try {
                this.incrementRateLimit();
                const result = await this.makeRequestWithRetry(request);
                resolve(result);
            } catch (error) {
                reject(error);
            }

            await this.sleep(100);
        }

        this.isProcessingQueue = false;
    }

    queueRequest(request) {
        return new Promise((resolve, reject) => {
            this.requestQueue.push({
                request,
                resolve,
                reject
            });
            this.processQueue();
        });
    }

    async makeRequestWithRetry(requestConfig) {
        let lastError;

        for (let attempt = 0; attempt <= this.retryConfig.maxRetries; attempt++) {
            try {
                const response = await this.axiosInstance(requestConfig);
                return response;
            } catch (error) {
                lastError = error;

                // Don't retry on client errors (4xx) except 429
                if (error.response?.status >= 400 && error.response?.status < 500 && error.response?.status !== 429) {
                    throw error;
                }

                // Don't retry on last attempt
                if (attempt === this.retryConfig.maxRetries) {
                    break;
                }

                const delay = this.getBackoffDelay(attempt);
                console.log(`Request failed (attempt ${attempt + 1}/${this.retryConfig.maxRetries + 1}), retrying in ${delay}ms...`);
                await this.sleep(delay);
            }
        }

        throw lastError;
    }

    getCacheKey(method, params) {
        return `${method}_${JSON.stringify(params)}`;
    }

    isCacheValid(key, cacheTime = 60000) {
        const lastFetch = this.lastFetch.get(key);
        return lastFetch && (Date.now() - lastFetch) < cacheTime;
    }


    async getCryptoPrices(coins = ['bitcoin', 'ethereum'], useCache = true) {
        const cacheKey = this.getCacheKey('prices', coins);

        if (useCache && this.isCacheValid(cacheKey)) {
            console.log('Returning cached crypto prices');
            return this.cachedData.get(cacheKey);
        }

        // try {
        const response = await this.queueRequest({
            method: 'GET',
            url: `${this.baseURL}/simple/price`,
            params: {
                ids: coins.join(','),
                vs_currencies: 'usd',
                include_24hr_change: true,
                include_24hr_vol: true,
                include_market_cap: true
            }
        });

        this.cachedData.set(cacheKey, response.data);
        this.lastFetch.set(cacheKey, Date.now());
        return response.data;
        // } catch (error) {
        //     console.error('Error fetching crypto prices:', error.message);

        //     // Return cached data if available
        //     if (this.cachedData.has(cacheKey)) {
        //         console.log('Returning stale cached data due to error');
        //         return this.cachedData.get(cacheKey);
        //     }

        //     throw error;
        // }
    }

    async getHistoricalData(coinId, days = 30, useCache = true) {
        const cacheKey = this.getCacheKey('historical', {
            coinId,
            days
        });

        if (useCache && this.isCacheValid(cacheKey, 300000)) {
            console.log(`Returning cached historical data for ${coinId}`);
            return this.cachedData.get(cacheKey);
        }

        const params = {
            vs_currency: 'usd',
            days: days
        };

        if (days > 90) {
            params.interval = 'daily';
        }

        // try {
        const response = await this.queueRequest({
            method: 'GET',
            url: `${this.baseURL}/coins/${coinId}/market_chart`,
            params
        });

        const data = {
            prices: response.data.prices,
            market_caps: response.data.market_caps,
            total_volumes: response.data.total_volumes
        };

        this.cachedData.set(cacheKey, data);
        this.lastFetch.set(cacheKey, Date.now());
        return data;
        // } catch (error) {
        //     console.error(`Error fetching historical data for ${coinId}:`, error.message);
        //                 if (this.cachedData.has(cacheKey)) {
        //         console.log('Returning stale cached data due to error');
        //         return this.cachedData.get(cacheKey);
        //     }

        //     throw error;
        // }
    }

    async getHistoricalDataForCoins(coinIds = [], days = 30, useCache = true) {
        const historicalData = {};
        const errors = {};

        // Process coins in batches to avoid overwhelming the API
        const batchSize = 2;
        for (let i = 0; i < coinIds.length; i += batchSize) {
            const batch = coinIds.slice(i, i + batchSize);
            const batchPromises = batch.map(async (coinId) => {
                try {
                    const data = await this.getHistoricalData(coinId, days, useCache);
                    historicalData[coinId] = data;
                } catch (error) {
                    console.error(`Failed to fetch data for ${coinId}:`, error.message);
                    errors[coinId] = error.message;
                }
            });

            await Promise.all(batchPromises);

            // Wait between batches if not the last batch
            if (i + batchSize < coinIds.length) {
                await this.sleep(2000);
            }
        }
        if (Object.keys(errors).length > 0) {
            console.warn('Some coins failed to fetch:', errors);
        }

        return {
            data: historicalData,
            errors
        };
    }

    async getAllInfoCoin(coins = ['bitcoin', 'ethereum'], useCache = true) {
        const cacheKey = this.getCacheKey('markets', coins);

        if (useCache && this.isCacheValid(cacheKey)) {
            console.log('Returning cached market data');
            return this.cachedData.get(cacheKey);
        }

        // try {
        const response = await this.queueRequest({
            method: 'GET',
            url: `${this.baseURL}/coins/markets`,
            params: {
                ids: coins.join(','),
                vs_currency: 'usd',
                order: 'market_cap_desc',
                per_page: 100,
                page: 1,
                sparkline: false,
                price_change_percentage: '1h,24h,7d'
            }
        });

        this.cachedData.set(cacheKey, response.data);
        this.lastFetch.set(cacheKey, Date.now());
        return response.data;
        // } catch (error) {
        //     console.error('Error fetching market data:', error.message);

        //     // Return cached data if available
        //     if (this.cachedData.has(cacheKey)) {
        //         console.log('Returning stale cached data due to error');
        //         return this.cachedData.get(cacheKey);
        //     }

        //     throw error;
        // }
    }

    clearCache() {
        this.cachedData.clear();
        this.lastFetch.clear();
        console.log('Cache cleared');
    }

    getRateLimitStatus() {
        const now = Date.now();
        const timeRemaining = this.rateLimitConfig.timeWindow - (now - this.rateLimitConfig.windowStart);
        const maxCalls = this.rateLimitConfig.freeCallsPerMinute;

        return {
            callsRemaining: maxCalls - this.rateLimitConfig.callsInCurrentWindow,
            totalCalls: maxCalls,
            timeUntilReset: Math.max(0, timeRemaining),
            queueLength: this.requestQueue.length,
            hasApiKey: !!this.apiKey
        };
    }
}

export default new CoinGeckoService();
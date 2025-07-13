import axios from 'axios';

/**
 * Service to interact with CoinGecko API for cryptocurrency data.
 * Provides methods to fetch current prices and historical data for cryptocurrencies.
 */

class CoinGeckoService {
    constructor() {
        this.baseURL = 'https://api.coingecko.com/api/v3';
        this.apiKey = process.env.COINGECKO_API_KEY || null;
        this.cachedData = null;   // ✅ Đúng
        this.lastFetch = 0;
    }

    async getCryptoPrices(coins = ['bitcoin', 'ethereum']) {
        const now = Date.now();
        if (this.cachedData && now - this.lastFetch < 60000) {
            return this.cachedData;
        }
        try {
            const response = await axios.get(`${this.baseURL}/simple/price`, {
                params: {
                    ids: coins.join(','),
                    vs_currencies: 'usd',
                    include_24hr_change: true,
                    include_24hr_vol: true,
                    include_market_cap: true
                },
                headers: {
                    accept: 'application/json',
                    ...(this.apiKey && {
                        'x-cg-pro-api-key': this.apiKey
                    })

                }
            });
            this.cachedData = response.data;
            this.lastFetch = now;
            return response.data;
        } catch (error) {
            console.error('Error fetching crypto prices:', error.message);
            return this.cachedData || null;
        }
    }

    async getHistoricalData(coinId, days = 30) {
        console.log("CoinId", coinId);
        try {
            const response = await axios.get(`${this.baseURL}/coins/${coinId}/market_chart`, {
                params: {
                    vs_currency: 'usd',
                    days: days,
                    interval: 'daily'
                },
                headers: {
                    accept: 'application/json',
                    ...(this.apiKey && {
                        'x-cg-pro-api-key': this.apiKey
                    })

                }

            });
            return {
                prices: response.data.prices,
                market_caps: response.data.market_caps,
                total_volumes: response.data.total_volumes
            };
        } catch (error) {
            console.error('Error fetching historical data:', error.message);
            return null;
        }
    }

    async getHistoricalDataForCoins(coinIds, days = 30) {
        console.log("coinIds", coinIds);
        const historicalData = {};

        for (const coinId of coinIds) {
            const data = await this.getHistoricalData(coinId, days);
            if (data) {
                historicalData[coinId] = data;
            }
            // Rate limiting
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

        return historicalData;
    }

    async getAllInfoCoin(coins = ['bitcoin', 'ethereum']) {
        try {
            const response = await axios.get(`${this.baseURL}/coins/markets`, {
                params: {
                    ids: coins.join(','),
                    vs_currency: 'usd',
                    include_24hr_change: true,
                    include_24hr_vol: true,
                    include_market_cap: true
                },
                headers: {
                    accept: 'application/json',
                    ...(this.apiKey && {
                        'x-cg-pro-api-key': this.apiKey
                    })

                }
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching crypto prices:', error.message);
            return null;
        }
    }
}

export default new CoinGeckoService();

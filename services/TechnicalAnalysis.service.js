import {
    fileURLToPath
} from 'url';

import {
    spawn
} from 'child_process';

import path from 'path';

import coinGeckoService from './CoinGecko.service.js';



const __filename = fileURLToPath(
    import.meta.url);
const __dirname = path.dirname(__filename)
class TechnicalAnalysisService {
    constructor() {
        this.pythonScriptPath = path.join(__dirname, '../python/technical_indicators.py');
        this.priceCache = new Map();
    }

    /**
     *  RSI: chỉ báo động lực, > 70: quá mua (có thể giảm), < 30: quá bán (có thể tăng)
     * @param {*} symbol 
     * @param {*} exchange 
     * @param {*} interval 
     */

    async runPythonScript(prices, indicator, volumes = null, highs = null, lows = null) {
        return new Promise((resolve, reject) => {
            const args = [
                this.pythonScriptPath,
                JSON.stringify(prices),
                indicator
            ];

            if (volumes) {
                args.push(JSON.stringify(volumes));
            }

            if (highs) {
                args.push(JSON.stringify(highs));
            }

            if (lows) {
                args.push(JSON.stringify(lows));
            }

            const pythonProcess = spawn('python', args);

            let dataString = '';
            let errorString = '';

            pythonProcess.stdout.on('data', (data) => {
                dataString += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                errorString += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code === 0) {
                    try {
                        const result = JSON.parse(dataString);
                        resolve(result);
                    } catch (error) {
                        reject(new Error(`Error parse JSON: ${error.message}`));
                    }
                } else {
                    reject(new Error(`Python script failed: ${errorString}`));
                }
            });

            pythonProcess.on('error', (error) => {
                reject(new Error(`Error run Python: ${error.message}`));
            });
        });
    }

    async getPriceData(symbol) {
        // try {
        if (this.priceCache.has(symbol)) {
            const cachedData = this.priceCache.get(symbol);
            if (Date.now() - cachedData.timestamp < 3600000) {
                return cachedData.data;
            } else {
                console.log(`🔄 Cập nhật cache cho ${symbol}`)
                this.priceCache.delete(symbol);
            }
        }

        const infoCoin = await coinGeckoService.getAllInfoCoin([symbol]);
        const priceCoin = await coinGeckoService.getHistoricalDataForCoins([symbol], 100);
        const prices = priceCoin.data[symbol].prices.map(([_, price]) => price);
        const totalVolume = priceCoin.data[symbol].prices.map(([_, total_volumes]) => total_volumes);

        const dataCoin = {};

        for (let i = 0; i < infoCoin.length; i++) {
            const coin = infoCoin[i];
            dataCoin[symbol] = {
                current_price: coin.current_price,
                volumes: totalVolume,
                highs: coin.high_24h,
                lows: coin.low_24h,
                prices: prices
            }
        }

        this.priceCache.set(symbol, {
            data: dataCoin,
            timestamp: Date.now()
        });

        return dataCoin;

        // } catch (error) {
        //     throw new Error(`Lỗi lấy dữ liệu giá: ${error.message}`);
        // }
    }

    /**
     * Calculating single technical indicator
     * @param {string} symbol - Coin symbol
     * @param {string} indicator - Technical indicator name
     * @returns {Promise<Object>} - Calculation result
     * */
    async calculateSingleIndicator(symbol, indicator) {
        try {
            const priceData = await this.getPriceData(symbol);

            const result = await this.runPythonScript(
                priceData.prices,
                indicator,
                priceData.volumes,
                priceData.highs,
                priceData.lows
            );

            return result;
        } catch (error) {
            throw new Error(`Lỗi tính ${indicator}: ${error.message}`);
        }
    }

    /**
     * Calculate all technical indicators
     * @param {string} symbol - Coin symbol
     * @returns {Promise<Object>} - Calculation result
     * */
    async calculateAllIndicators(symbol) {
        // try {
        const priceData = await this.getPriceData(symbol);

        const result = await this.runPythonScript(
            priceData[symbol].prices,
            'all',
            priceData[symbol].volumes,
            priceData[symbol].highs,
            priceData[symbol].lows
        );

        return result;
        // } catch (error) {
        //     throw new Error(`Error calculating all indicators: ${error.message}`);
        // }
    }

    async getSingleIndicator(symbol, indicator) {
        try {
            const result = await this.calculateSingleIndicator(symbol, indicator);
            return result;
        } catch (error) {
            console.error(`Eror getSingleIndicator ${indicator} with ${symbol}:`, error);
            throw error;
        }
    }


    async getTechnicalIndicators(symbol) {
        try {
            const allIndicators = await this.calculateAllIndicators(symbol);
            if (allIndicators.error) {
                throw new Error(allIndicators.error);
            }

            const formattedResult = {
                // RSI
                rsi: allIndicators.rsi?.value || 50,
                rsi_signal: allIndicators.rsi?.signal || 'NEUTRAL',
                rsi_message: allIndicators.rsi?.message || '',

                // MACD
                macd: allIndicators.macd?.macd || 0,
                macd_signal: allIndicators.macd?.signal || 0,
                macd_histogram: allIndicators.macd?.histogram || 0,
                macd_trend: allIndicators.macd?.trend || 'NEUTRAL',
                macd_message: allIndicators.macd?.message || '',

                // EMA
                ema: allIndicators.ema?.ema_value || 45000,
                ema_signal: allIndicators.ema?.signal || 'NEUTRAL',
                ema_message: allIndicators.ema?.message || '',

                // SMA
                sma: allIndicators.sma?.sma_value || 45000,
                sma_signal: allIndicators.sma?.signal || 'NEUTRAL',
                sma_message: allIndicators.sma?.message || '',

                // Volume
                volume: allIndicators.volume?.current_volume || 1000000000,
                volume_signal: allIndicators.volume?.signal || 'NEUTRAL',
                volume_message: allIndicators.volume?.message || '',

                // Bollinger Bands
                bollinger: {
                    upper: allIndicators.bollinger?.upper_band || 50000,
                    lower: allIndicators.bollinger?.lower_band || 40000,
                    middle: allIndicators.bollinger?.middle_band || 45000,
                    signal: allIndicators.bollinger?.signal || 'NEUTRAL',
                    message: allIndicators.bollinger?.message || ''
                },

                // Stochastic
                stochastic: {
                    k: allIndicators.stochastic?.k_percent || 50,
                    d: allIndicators.stochastic?.d_percent || 50,
                    signal: allIndicators.stochastic?.signal || 'NEUTRAL',
                    message: allIndicators.stochastic?.message || ''
                },

                // Tổng hợp
                summary: allIndicators.summary || {
                    overall_signal: 'NEUTRAL',
                    recommendation: 'Quan sát thêm',
                    confidence: 0
                },

                // Metadata
                timestamp: Date.now(),
                symbol: symbol
            };

            return formattedResult;

        } catch (error) {
            console.error(`Error getTechnicalIndicators with ${symbol}:`, error);

            // Fallback Data if error occurs
            return {
                rsi: Math.floor(Math.random() * 100),
                macd: (Math.random() - 0.5) * 10,
                ema: Math.floor(Math.random() * 50000),
                volume: Math.floor(Math.random() * 1000000000),
                bollinger: {
                    upper: Math.floor(Math.random() * 60000),
                    lower: Math.floor(Math.random() * 40000)
                },
                sma: Math.floor(Math.random() * 45000),
                stochastic: {
                    k: Math.floor(Math.random() * 100),
                    d: Math.floor(Math.random() * 100)
                },
                error: error.message
            };
        }
    }

}

export default new TechnicalAnalysisService();
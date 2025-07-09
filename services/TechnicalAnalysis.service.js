import axios from 'axios';

// TAAPI.io service for technical indicators
class TechnicalAnalysisService {
    constructor() {
        this.apiKey = process.env.TAAPI_API_KEY;
        this.baseURL = 'https://api.taapi.io';
    }

    /**
     *  RSI: chỉ báo động lực, > 70: quá mua (có thể giảm), < 30: quá bán (có thể tăng)
     * @param {*} symbol 
     * @param {*} exchange 
     * @param {*} interval 
     */
    async getRSI(symbol, exchange = 'binance', interval = '1h') {
        try {
            const response = await axios.get(`${this.baseURL}/rsi`, {
                params: {
                    secret: process.env.TAAPI_API_KEY,
                    exchange: exchange,
                    symbol: symbol,
                    interval: interval
                }
            });
            console.log('RSI response:', response.data);
            return response.data;
        } catch (error) {
            console.error('Error fetching RSI:', error.message);
            return null;
        }
    }
    /**
     * MACD: chỉ báo xu hướng
     * Tín hiệu mua/bán khi các đường cắt nhau
     */
    async getMACD(symbol, exchange = 'binance', interval = '1h') {
        try {
            const response = await axios.get(`${this.baseURL}/macd`, {
                params: {
                    secret: process.env.TAAPI_API_KEY,
                    exchange: exchange,
                    symbol: symbol,
                    interval: interval
                }
            });
            console.log('MACD response:', response.data);
            return response.data;
        } catch (error) {
            console.error('Error fetching MACD:', error.message);
            return null;
        }
    }
}

export default new TechnicalAnalysisService();
import axios from 'axios';
import cron from 'node-cron';
import {
    Telegraf
} from 'telegraf';
/**
 * AI Agent Service Class
 */
class AIAnalysisService {
    constructor() {
        this.config = null;
        this.bot = null;
        this.aiAgent = null;
        this.cronJobs = [];
        this.isRunning = false;
        this.previousPrices = {};
        this.defaultConfig = {
            alertThresholds: {
                priceChange: 5,
                volume: 20,
                rsiOverbought: 70,
                rsiOversold: 30
            },
            checkInterval: '*/30 * * * *',
            quickCheckInterval: '*/5 * * * *',
            supportedCoins: ['bitcoin', 'ethereum'],
            aiInstructions: 'Bạn là chuyên gia phân tích cryptocurrency. Hãy phân tích dữ liệu thị trường và đưa ra nhận định chính xác, ngắn gọn bằng tiếng Việt.'
        };
    }

    /**
     * Khởi tạo service với cấu hình
     * @param {Object} config - Cấu hình service
     */
    init(config) {
        this.config = {
            ...this.defaultConfig,
            ...config
        };

        // Khởi tạo AI Agent
        this.aiAgent = {
            name: this.config.aiName || "Crypto Analysis Agent",
            instructions: this.config.aiInstructions,
            model: this.config.aiModel || "meta-llama/Llama-3.3-70B-Instruct",
            apiKey: this.config.aiApiKey,
            baseUrl: this.config.aiBaseUrl || "https://api.intelligence.io.solutions/api/v1",
            headers: {
                'Authorization': `Bearer ${this.config.aiApiKey}`,
                'Content-Type': 'application/json'
            }
        };

        // Khởi tạo Telegram Bot
        this.bot = new Telegraf(this.config.telegramToken);

        console.log('✅ AIAnalysisService initialized');
        return this;
    }

    /**
     * Phân tích dữ liệu bằng AI
     * @param {string} data - Dữ liệu cần phân tích
     * @returns {Promise<string>} - Kết quả phân tích
     */
    async analyzeWithAI(data) {
        try {
            const payload = {
                model: this.aiAgent.model,
                messages: [{
                        role: 'system',
                        content: this.aiAgent.instructions
                    },
                    {
                        role: 'user',
                        content: data
                    }
                ],
                max_tokens: 500,
                temperature: 0.7
            };

            const response = await axios.post(
                `${this.aiAgent.baseUrl}/chat/completions`,
                payload, {
                    headers: this.aiAgent.headers,
                    timeout: 30000
                }
            );

            return response.data.choices[0].message.content;
        } catch (error) {
            console.error('❌ AI Analysis Error:', error.message);
            return 'Lỗi khi phân tích dữ liệu AI';
        }
    }

    /**
     * Lấy dữ liệu cryptocurrency
     * @param {string} symbol - Symbol của coin
     * @returns {Promise<Object>} - Dữ liệu coin
     */
    async getCryptoData(symbol) {
        try {
            const response = await axios.get('https://api.coingecko.com/api/v3/simple/price', {
                params: {
                    ids: symbol,
                    vs_currencies: 'usd',
                    include_24hr_change: true,
                    include_market_cap: true,
                    include_24hr_vol: true
                },
                timeout: 10000
            });

            return response.data[symbol];
        } catch (error) {
            console.error(`❌ Error fetching ${symbol}:`, error.message);
            throw new Error(`Không thể lấy dữ liệu ${symbol}`);
        }
    }

    /**
     * Tính toán chỉ số kỹ thuật
     * @param {string} symbol - Symbol của coin
     * @returns {Promise<Object>} - Chỉ số kỹ thuật
     */
    async getTechnicalIndicators(symbol) {
        // Mock data - trong thực tế sẽ gọi API thật
        return {
            rsi: Math.floor(Math.random() * 100),
            macd: (Math.random() - 0.5) * 10,
            ema: Math.floor(Math.random() * 50000),
            volume: Math.floor(Math.random() * 1000000000),
            bollinger: {
                upper: Math.floor(Math.random() * 60000),
                lower: Math.floor(Math.random() * 40000)
            },
            sma: Math.floor(Math.random() * 45000)
        };
    }

    /**
     * Kiểm tra điều kiện cảnh báo
     * @param {string} symbol - Symbol
     * @param {number} currentPrice - Giá hiện tại
     * @param {number} priceChange24h - Thay đổi 24h
     * @param {Object} techData - Dữ liệu kỹ thuật
     * @returns {boolean} - Có nên cảnh báo không
     */
    shouldSendAlert(symbol, currentPrice, priceChange24h, techData) {
        const {
            alertThresholds
        } = this.config;

        return [
            Math.abs(priceChange24h) > alertThresholds.priceChange,
            techData.rsi > alertThresholds.rsiOverbought,
            techData.rsi < alertThresholds.rsiOversold,
            Math.abs(techData.macd) > 5
        ].some(condition => condition);
    }

    /**
     * Format tin nhắn cảnh báo
     * @param {string} symbol - Symbol
     * @param {Object} priceData - Dữ liệu giá
     * @param {Object} techData - Dữ liệu kỹ thuật
     * @param {string} aiAnalysis - Phân tích AI
     * @returns {string} - Tin nhắn format
     */
    formatAlertMessage(symbol, priceData, techData, aiAnalysis) {
        const emoji = priceData.usd_24h_change > 0 ? '🟢' : '🔴';
        const trend = priceData.usd_24h_change > 0 ? 'TĂNG' : 'GIẢM';
        const coinName = symbol.charAt(0).toUpperCase() + symbol.slice(1);

        return `
${emoji} <b>CẢNH BÁO ${coinName.toUpperCase()}</b>

💰 <b>Giá:</b> $${priceData.usd.toFixed(2)}
📊 <b>24h:</b> ${priceData.usd_24h_change.toFixed(2)}% (${trend})
📈 <b>Volume:</b> $${(priceData.usd_24h_vol / 1000000).toFixed(2)}M
💎 <b>Cap:</b> $${(priceData.usd_market_cap / 1000000000).toFixed(2)}B

📋 <b>Chỉ số kỹ thuật:</b>
• RSI: ${techData.rsi} ${techData.rsi > 70 ? '🔴' : techData.rsi < 30 ? '🟢' : '🟡'}
• MACD: ${techData.macd.toFixed(2)}
• EMA: $${techData.ema.toFixed(2)}
• SMA: $${techData.sma.toFixed(2)}

🤖 <b>Phân tích AI:</b>
${aiAnalysis}

⏰ <i>${new Date().toLocaleString('vi-VN')}</i>
        `.trim();
    }

    /**
     * Gửi tin nhắn Telegram
     * @param {string} message - Tin nhắn
     * @param {string} chatId - Chat ID (optional)
     */
    async sendTelegramMessage(message, chatId = null) {
        try {
            await this.bot.telegram.sendMessage(
                chatId || this.config.chatId,
                message, {
                    parse_mode: 'HTML',
                    disable_web_page_preview: true
                }
            );
            console.log('✅ Message sent successfully');
        } catch (error) {
            console.error('❌ Telegram send error:', error.message);
            throw new Error('Lỗi gửi tin nhắn Telegram');
        }
    }

    /**
     * Phân tích và gửi cảnh báo
     * @param {string} symbol - Symbol coin
     * @param {boolean} forceAlert - Bắt buộc gửi cảnh báo
     */
    async analyzeAndAlert(symbol, forceAlert = false) {
        try {
            console.log(`🔍 Analyzing ${symbol}...`);

            const [priceData, techData] = await Promise.all([
                this.getCryptoData(symbol),
                this.getTechnicalIndicators(symbol)
            ]);

            const currentPrice = priceData.usd;
            const priceChange24h = priceData.usd_24h_change || 0;

            // Kiểm tra điều kiện cảnh báo
            const shouldAlert = forceAlert || this.shouldSendAlert(symbol, currentPrice, priceChange24h, techData);

            if (shouldAlert) {
                // Chuẩn bị dữ liệu cho AI
                const analysisData = `
                Phân tích ${symbol.toUpperCase()}:
                - Giá: $${currentPrice.toFixed(2)}
                - Thay đổi 24h: ${priceChange24h.toFixed(2)}%
                - Volume: $${(priceData.usd_24h_vol / 1000000).toFixed(2)}M
                - RSI: ${techData.rsi}
                - MACD: ${techData.macd.toFixed(2)}
                - EMA: ${techData.ema}
                - SMA: ${techData.sma}
                
                Hãy phân tích và đưa ra nhận định ngắn gọn.
                `;

                const aiAnalysis = await this.analyzeWithAI(analysisData);
                const alertMessage = this.formatAlertMessage(symbol, priceData, techData, aiAnalysis);

                await this.sendTelegramMessage(alertMessage);
                this.previousPrices[symbol] = currentPrice;

                console.log(`✅ Alert sent for ${symbol}`);
                return {
                    success: true,
                    message: 'Cảnh báo đã được gửi'
                };
            } else {
                console.log(`ℹ️ No alert needed for ${symbol}`);
                return {
                    success: false,
                    message: 'Không cần cảnh báo'
                };
            }

        } catch (error) {
            console.error(`❌ Error analyzing ${symbol}:`, error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Lấy trạng thái thị trường
     * @returns {Promise<Object>} - Trạng thái thị trường
     */
    async getMarketStatus() {
        try {
            const results = await Promise.all(
                this.config.supportedCoins.map(coin => this.getCryptoData(coin))
            );

            const marketData = {};
            results.forEach((data, index) => {
                const coin = this.config.supportedCoins[index];
                marketData[coin] = {
                    price: data.usd,
                    change24h: data.usd_24h_change,
                    volume: data.usd_24h_vol,
                    marketCap: data.usd_market_cap
                };
            });

            return {
                success: true,
                data: marketData
            };
        } catch (error) {
            console.error('❌ Error getting market status:', error.message);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Thiết lập Telegram commands
     */
    setupTelegramCommands() {
        this.bot.command('start', (ctx) => {
            ctx.reply('🚀 Crypto Alert Bot đã sẵn sàng!\n\n/help - Xem hướng dẫn');
        });

        this.bot.command('status', async (ctx) => {
            const result = await this.getMarketStatus();
            if (result.success) {
                let message = '📊 <b>Trạng thái thị trường:</b>\n\n';
                Object.entries(result.data).forEach(([coin, data]) => {
                    const emoji = coin === 'bitcoin' ? '🟡' : '🔵';
                    const name = coin === 'bitcoin' ? 'Bitcoin' : 'Ethereum';
                    message += `${emoji} <b>${name}:</b> $${data.price.toFixed(2)} (${data.change24h.toFixed(2)}%)\n`;
                });
                ctx.reply(message, {
                    parse_mode: 'HTML'
                });
            } else {
                ctx.reply('❌ Lỗi khi lấy dữ liệu thị trường');
            }
        });

        this.bot.command('analyze', async (ctx) => {
            const args = ctx.message.text.split(' ');
            const symbol = args[1] || 'bitcoin';

            if (!this.config.supportedCoins.includes(symbol)) {
                ctx.reply(`❌ Không hỗ trợ "${symbol}". Hỗ trợ: ${this.config.supportedCoins.join(', ')}`);
                return;
            }

            ctx.reply(`🔍 Đang phân tích ${symbol}...`);
            const result = await this.analyzeAndAlert(symbol, true);

            if (!result.success && result.error) {
                ctx.reply(`❌ Lỗi: ${result.error}`);
            }
        });

        this.bot.command('help', (ctx) => {
            const help = `
🤖 <b>Crypto Alert Bot</b>

<b>Lệnh:</b>
/start - Khởi động
/status - Trạng thái thị trường  
/analyze [coin] - Phân tích coin
/help - Hướng dẫn

<b>Hỗ trợ:</b> ${this.config.supportedCoins.join(', ')}
            `;
            ctx.reply(help, {
                parse_mode: 'HTML'
            });
        });
    }

    /**
     * Thiết lập scheduler
     */
    setupScheduler() {
        // Lịch chính
        const mainJob = cron.schedule(this.config.checkInterval, async () => {
            console.log('🔄 Scheduled analysis...');
            for (const coin of this.config.supportedCoins) {
                await this.analyzeAndAlert(coin);
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
        });

        // Lịch kiểm tra nhanh
        const quickJob = cron.schedule(this.config.quickCheckInterval, async () => {
            console.log('⚡ Quick check...');
            // Logic kiểm tra nhanh
        });

        this.cronJobs = [mainJob, quickJob];
    }

    /**
     * Khởi động service
     */
    async start() {
        try {
            if (this.isRunning) {
                console.log('⚠️ Service đã đang chạy');
                return {
                    success: false,
                    message: 'Service đã chạy'
                };
            }

            if (!this.config) {
                throw new Error('Chưa khởi tạo cấu hình. Gọi init() trước');
            }

            this.setupTelegramCommands();
            this.setupScheduler();

            await this.bot.launch();
            this.isRunning = true;

            console.log('🚀 AIAnalysisService started');

            await this.sendTelegramMessage('🤖 Crypto Alert Bot đã khởi động!');

            return {
                success: true,
                message: 'Service đã khởi động'
            };
        } catch (error) {
            console.error('❌ Error starting service:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Dừng service
     */
    async stop() {
        try {
            if (!this.isRunning) {
                console.log('⚠️ Service chưa chạy');
                return {
                    success: false,
                    message: 'Service chưa chạy'
                };
            }

            this.cronJobs.forEach(job => job.destroy());
            this.cronJobs = [];

            this.bot.stop();
            this.isRunning = false;

            console.log('🛑 AIAnalysisService stopped');
            return {
                success: true,
                message: 'Service đã dừng'
            };
        } catch (error) {
            console.error('❌ Error stopping service:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Kiểm tra trạng thái service
     */
    getStatus() {
        return {
            isRunning: this.isRunning,
            config: this.config ? 'Đã cấu hình' : 'Chưa cấu hình',
            supportedCoins: this.config?.supportedCoins || [],
            cronJobs: this.cronJobs.length
        };
    }
}

// Export singleton instance
export default new AIAnalysisService();
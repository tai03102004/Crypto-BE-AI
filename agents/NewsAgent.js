import EventEmitter from "events";
import {
    spawn
} from "child_process";
import path from "path";

const __filename = fileURLToPath(
    import.meta.url);
const __dirname = path.dirname(__filename)
import {
    fileURLToPath
} from 'url';
class NewsAgent extends EventEmitter {
    constructor() {
        super();
        this.newCache = new Map();
        this.isRunning = false;
    }

    async start(config) {
        this.config = config;
        this.startNewsCollection();
        console.log("📰 News Agent started");
    }

    startNewsCollection() {
        // Collect news every 30 minutes
        this.newInterval = setInterval(async () => {
            await this.collectCryptoNews();
        }, 30 * 60 * 1000); // 30 minutes

        this.collectCryptoNews();
    }

    async collectCryptoNews() {
        try {
            console.log('📰 Collecting crypto news...');
            const newsData = await this.runCrewAIScript();

            if (newsData && newsData.length > 0) {
                this.emit('marketNews', {
                    news: newsData,
                    timestamp: Date.now(),
                    sentiment: this.analyzeSentiment(newsData)
                });
            } else {
                console.warn('No news data collected.');
            }
        } catch (err) {
            console.error("Error collecting crypto news:", err);
        }
    }

    async runCrewAIScript() {
        return new Promise((resolve, reject) => {
            const scriptPath = path.join(__dirname, '../python/crew_analysis.py');
            const pythonProcess = spawn('python', [scriptPath]);

            let output = '';
            let errorOutput = '';
            pythonProcess.stdout.on('data', (data) => {
                output += data.toString();
            });

            pythonProcess.stderr.on('data', (data) => {
                errorOutput += data.toString();
            });

            pythonProcess.on('close', (code) => {
                if (code === 0) {
                    try {
                        const newsData = JSON.parse(output);
                        resolve(newsData);
                    } catch (error) {
                        resolve(output);
                    }
                } else {
                    reject(new Error(`Python script failed: ${errorOutput}`));
                }
            });
        });
    }

    analyzeSentiment(newsText) {
        const bullishWords = ['bull', 'rise', 'increase', 'positive', 'growth', 'pump'];
        const bearishWords = ['bear', 'fall', 'decrease', 'negative', 'crash', 'dump'];

        const text = newsText.toLowerCase();
        let bullishScore = 0;
        let bearishScore = 0;

        bullishWords.forEach(word => {
            bullishScore += (text.match(new RegExp(word, 'g')) || []).length;
        });

        bearishWords.forEach(word => {
            bearishScore += (text.match(new RegExp(word, 'g')) || []).length;
        });

        if (bullishScore > bearishScore) return 'BULLISH';
        if (bearishScore > bullishScore) return 'BEARISH';
        return 'NEUTRAL';
    }

    getStatus() {
        return {
            isRunning: this.isRunning,
            cacheSize: this.newCache.size,
            lastUpdate: this.lastNewsUpdate
        }
    }

    stop() {
        if (this.newsInterval) {
            clearInterval(this.newsInterval);
            this.newsInterval = null;
            console.log("📰 News Agent stopped");
        }
        this.isRunning = false;
    }
}

export default NewsAgent;
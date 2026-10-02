import coinGeckoService from '../../services/CoinGecko.service.js';

export const historyByCoinId = async (req, res) => {
    try {
        const {
            coinId
        } = req.params;
        if (!coinId) {
            return res.status(400).json({
                error: "Missing coinId parameter"
            });
        }

        const {
            days = 30
        } = req.query;

        const data = await coinGeckoService.getHistoricalData(coinId, days);
        res.json(data);
    } catch (error) {
        res.status(500).json({
            error: error.message
        });
    }
};
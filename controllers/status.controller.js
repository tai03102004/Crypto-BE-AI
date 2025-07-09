export const status = async (req, res) => {
    res.json({
        status: 'running',
        timestamp: new Date(),
        services: {
            coinGecko: true,
            taapi: !!process.env.TAAPI_API_KEY,
            openai: !!process.env.OPENAI_API_KEY
        }
    });
};
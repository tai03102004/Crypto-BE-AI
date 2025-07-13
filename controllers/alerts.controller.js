import {
    getAlerts
} from '../data/alerts.js';

export const getRecentAlerts = async (req, res) => {
    try {
        const alerts = await getAlerts();
        res.json(alerts.slice(-20));
    } catch (error) {
        console.error("Error fetching alerts:", error);
        res.status(500).json({
            error: "Internal server error"
        });
    }
};
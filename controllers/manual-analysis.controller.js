import {
    performAnalysis
} from '../middlewares/performAnalysis.middlewares.js';

export const manualAnalysis = async (req, res) => {
    try {
        await performAnalysis();
        res.json({
            success: true,
            message: 'Analysis completed'
        });
    } catch (error) {
        res.status(500).json({
            error: error.message
        });
    }
};
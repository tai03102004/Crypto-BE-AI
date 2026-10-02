import {
    getAnalysisResults
} from '../data/analysisResults.js';
import {
    performAnalysis
} from '../middlewares/performAnalysis.middlewares.js';

export const analysis = async (req, res) => {
    await performAnalysis();
    var analysisResults = getAnalysisResults();
    res.json(analysisResults);
}
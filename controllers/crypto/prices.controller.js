import {
    getCryptoData
} from '../../data/cryptoData.js';

export const prices = async (req, res) => {
    const cryptoData = getCryptoData();
    res.json(cryptoData);
};
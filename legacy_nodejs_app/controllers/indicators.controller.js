import {
    spawn
} from 'child_process';

export const indicators = async (req, res) => {
    // try {
    const {
        prices,
        indicator
    } = req.body;

    const pythonProcess = spawn('python3', ['python/technical_indicators.py', JSON.stringify(prices), indicator]);

    let result = '';
    pythonProcess.stdout.on('data', (data) => {
        result += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error('Python script error:', data.toString());
    });

    pythonProcess.on('close', (code) => {
        if (code === 0) {
            try {
                const parsedResult = JSON.parse(result);
                res.json(parsedResult);
            } catch (e) {
                res.status(500).json({
                    error: 'Invalid Python output'
                });
            }
        } else {
            res.status(500).json({
                error: 'Python script failed'
            });
        }
    });
    // } catch (error) {
    //     res.status(500).json({
    //         error: error.message
    //     });
    // }
};
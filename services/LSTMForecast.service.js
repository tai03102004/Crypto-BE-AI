import {
  spawn
} from "child_process";


export async function predictLSTM() {
  // Bitcoin forecast
  const btc = await new Promise((resolve, reject) => {
    const process = spawn("python", ["python/predict_lstm.py"]);
    let output = "";
    process.stdout.on("data", (data) => {
      output += data.toString();
      console.log("Python Output:", output);
    });
    process.on("close", () => {
      resolve(JSON.parse(output));
    });
  });

  // Ethereum forecast
  const eth = await new Promise((resolve, reject) => {
    const process = spawn("python", ["python/predict_lstm_eth.py"]);
    let output = "";
    process.stdout.on("data", (data) => {
      output += data.toString();
      console.log("Ethereum Python Output:", output);
    });
    process.on("close", () => {
      resolve(JSON.parse(output));
    });
  });

  return {
    btc,
    eth
  };
}
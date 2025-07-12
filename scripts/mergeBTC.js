import CoinGeckoService from "../services/CoinGecko.service.js";
import fs from "fs";

// Hàm đọc CSV cũ
function loadOldData(filePath) {
  if (!fs.existsSync(filePath)) return [];

  const text = fs.readFileSync(filePath, "utf-8");
  const lines = text.trim().split("\n");

  // Bỏ dòng header
  const data = lines.slice(1).map(line => {
    const parts = line.split(",");
    return {
      date: parts[0].trim(),
      close: parseFloat(parts[1])
    };
  });

  return data;
}

// Hàm gọi CoinGecko
async function fetchNewData() {
  const data = await CoinGeckoService.getHistoricalData("bitcoin", 365);

  return data.prices.map(([timestamp, price]) => ({
    date: new Date(timestamp).toISOString().split("T")[0],
    close: parseFloat(price)
  }));
}

// Hàm merge dữ liệu
function mergeData(oldData, newData) {
  const map = new Map();

  // Thêm dữ liệu cũ
  for (const row of oldData) {
    map.set(row.date, row.close);
  }

  // Thêm dữ liệu mới (ghi đè nếu trùng ngày)
  for (const row of newData) {
    map.set(row.date, row.close);
  }

  // Chuyển lại thành mảng và sort theo ngày
  const merged = Array.from(map.entries())
    .map(([date, close]) => ({ date, close }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  return merged;
}

(async () => {
  const filePath = "python/data/BTC.csv";

  console.log("🔹 Đang đọc dữ liệu cũ...");
  const oldData = loadOldData(filePath);

  console.log("🔹 Đang tải dữ liệu mới từ CoinGecko...");
  const newData = await fetchNewData();

  console.log(`🔹 Dữ liệu cũ: ${oldData.length} dòng`);
  console.log(`🔹 Dữ liệu mới: ${newData.length} dòng`);

  const merged = mergeData(oldData, newData);
  console.log(`✅ Đã merge tổng cộng ${merged.length} dòng.`);

  // Tạo nội dung CSV
  const lines = ["date,close"];
  for (const row of merged) {
    lines.push(`${row.date},${row.close.toFixed(2)}`);
  }

  fs.writeFileSync(filePath, lines.join("\n"), "utf-8");
  console.log(`✅ File đã ghi: ${filePath}`);
})();

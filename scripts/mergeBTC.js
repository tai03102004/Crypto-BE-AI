import CoinGeckoService from "../services/CoinGecko.service.js";
import fs from "fs";

// Hàm đọc dữ liệu cũ (giữ lại date và close)
function loadOldData(filePath) {
  if (!fs.existsSync(filePath)) return [];

  const text = fs.readFileSync(filePath, "utf-8");
  const lines = text.trim().split("\n");

  if (lines.length <= 1) return [];

  // Dòng header
  const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
  const dateIdx = headers.indexOf("date");
  const closeIdx = headers.indexOf("close");


  if (dateIdx === -1 || closeIdx === -1) {
    throw new Error("File CSV không có cột 'date' hoặc 'close'");
  }

  // Parse dữ liệu
  const data = lines.slice(1).map(line => {
    const parts = line.split(",");
    return {
      date: parts[dateIdx].trim(),
      close: parseFloat(parts[closeIdx])
    };
  });

  return data;
}

// Hàm gọi CoinGecko
async function fetchNewData() {
  const data = await CoinGeckoService.getHistoricalData("bitcoin", 365); // 1 năm gần nhất
  return data.prices.map(([timestamp, price]) => ({
    date: new Date(timestamp).toISOString().split("T")[0],
    close: parseFloat(price)
  }));
}

// Merge dữ liệu
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

  // Chuyển thành mảng & sort
  const merged = Array.from(map.entries())
    .map(([date, close]) => ({
      date,
      close
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  return merged;
}

// Main
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

  // Tạo CSV: chỉ 2 cột date,close
  const lines = ["date,close"];
  for (const row of merged) {
    lines.push(`${row.date},${row.close.toFixed(2)}`);
  }

  fs.writeFileSync(filePath, lines.join("\n"), "utf-8");

  console.log(`✅ File đã ghi: ${filePath}`);
  console.log(`📅 Earliest date: ${merged[0].date}`);
  console.log(`📅 Latest date: ${merged[merged.length -1].date}`);
})();
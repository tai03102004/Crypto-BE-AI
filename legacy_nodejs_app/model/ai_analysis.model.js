// CryptoAI/model/chat.model.js
import mongoose from "mongoose";

export const Role = {
    assistant: "assistant",
};

const aiAnalysisSchema = new mongoose.Schema({
    conversationId: String, // Phòng chat
    content: String, // Nội dung tin nhắn
    imagesUrl: Array, // Hình ảnh up lên
    role: {
        type: String,
        enum: Object.values(Role), // "assistant"
        required: true,
    },
    alert: String,
    deleted: {
        type: Boolean,
        default: false,
    },
    deletedAt: Date,
}, {
    timestamps: true, // createdAt và updatedAt
});

// Nếu đã tồn tại model rồi thì dùng lại (tránh lỗi khi hot reload)
export const AiAnalysis =
    mongoose.models.AiAnalysis || mongoose.model("AiAnalysis", aiAnalysisSchema, "AiAnalysis");
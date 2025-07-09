// CryptoAI/model/chat.model.js
import mongoose from "mongoose";

export const Role = {
  user: "user",
  assistant: "assistant",
};

const aiMessageSchema = new mongoose.Schema({
  conversationId: String, // Phòng chat
  content: String, // Nội dung tin nhắn
  imagesUrl: Array, // Hình ảnh up lên
  role: {
    type: String,
    enum: Object.values(Role), // Chắc chắn là "user" hoặc "assistant"
    required: true,
  },
  deleted: {
    type: Boolean,
    default: false,
  },
  deletedAt: Date,
}, {
  timestamps: true, // createdAt và updatedAt
});

// Nếu đã tồn tại model rồi thì dùng lại (tránh lỗi khi hot reload)
export const AiMessage =
  mongoose.models.AiMessage || mongoose.model("AiMessage", aiMessageSchema, "AiMessages");
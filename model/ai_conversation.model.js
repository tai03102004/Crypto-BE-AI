import mongoose from "mongoose";

const ConversationSchema = new mongoose.Schema({
    user_id: String, // user_id người chat
    title: String,
    description: String, // Mô tả cuộc trò chuyện
    model: String, // Model AI sử dụng
    deleted: {
      // Trạng thái
      type: Boolean,
      default: false,
    },
    createAt: Date, // Tạo khi nào
    updatedAt: Date, // Cập nhật khi nào
    deletedAt: Date, // Nhắn khi nào
  },

  {
    timestamps: true
  }
);

export const Conversation =
  mongoose.models.Conversation || mongoose.model("Conversation", ConversationSchema, "Conversations");
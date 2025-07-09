// routes/aiChat.routes.js
import express from 'express';
import AIChatController from '../controllers/ai_chat.controller.js';

const router = express.Router();

// Tạo cuộc trò chuyện mới
router.post('/conversations', AIChatController.createConversation);

// Lấy danh sách cuộc trò chuyện của user
router.get('/conversations/:user_id', AIChatController.getConversations);

// Lấy tin nhắn trong cuộc trò chuyện
router.get('/conversations/:conversationId/messages', AIChatController.getMessages);

// Gửi tin nhắn và nhận phản hồi AI
router.post('/conversations/:conversationId/messages', AIChatController.sendMessage.bind(AIChatController));

// Xóa tin nhắn
router.delete('/messages/:messageId', AIChatController.deleteMessage);

// Xóa cuộc trò chuyện
router.delete('/conversations/:conversationId', AIChatController.deleteConversation);

export default router;
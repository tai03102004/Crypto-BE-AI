// controllers/aiChat.controller.js
import {
    AiMessage,
    Role
} from '../model/ai_message.model.js';
import {
    Conversation
} from '../model/ai_conversation.model.js';
import AIAnalysisService from '../services/AIAnalysis.service.js';
import axios from 'axios';

class AIChatController {
    user_id = "tai"
    // Tạo cuộc trò chuyện mới
    async createConversation(req, res) {
        try {
            const {
                user_id,
                title,
                description
            } = req.body;

            const conversation = new Conversation({
                user_id,
                title: title || 'Cuộc trò chuyện mới',
                description: description || '',
                model: 'meta-llama/Llama-3.3-70B-Instruct',
                createAt: new Date(),
                updatedAt: new Date()
            });

            await conversation.save();

            res.status(201).json({
                success: true,
                message: 'Tạo cuộc trò chuyện thành công',
                data: conversation
            });
        } catch (error) {
            console.error('Error creating conversation:', error);
            res.status(500).json({
                success: false,
                message: 'Lỗi khi tạo cuộc trò chuyện',
                error: error.message
            });
        }
    }

    // Lấy danh sách cuộc trò chuyện
    async getConversations(req, res) {
        try {
            const {
                user_id
            } = req.params;

            const conversations = await Conversation.find({
                user_id,
                deleted: false
            }).sort({
                updatedAt: -1
            });

            res.json({
                success: true,
                data: conversations
            });
        } catch (error) {
            console.error('Error getting conversations:', error);
            res.status(500).json({
                success: false,
                message: 'Lỗi khi lấy danh sách cuộc trò chuyện'
            });
        }
    }

    // Lấy tin nhắn trong cuộc trò chuyện
    async getMessages(req, res) {
        try {
            const {
                conversationId
            } = req.params;
            const {
                page = 1, limit = 20
            } = req.query;

            const messages = await AiMessage.find({
                    conversationId,
                    deleted: false
                })
                .sort({
                    createdAt: -1
                })
                .limit(limit * 1)
                .skip((page - 1) * limit);

            res.json({
                success: true,
                data: messages.reverse() // Đảo ngược để hiển thị theo thứ tự thời gian
            });
        } catch (error) {
            console.error('Error getting messages:', error);
            res.status(500).json({
                success: false,
                message: 'Lỗi khi lấy tin nhắn'
            });
        }
    }

    // Gửi tin nhắn và nhận phản hồi từ AI
    async sendMessage(req, res) {
        // try {
        const {
            conversationId,
            content,
            imagesUrl = []
        } = req.body;

        if (!conversationId || !content) {
            return res.status(400).json({
                success: false,
                message: 'Thiếu thông tin conversationId hoặc content'
            });
        }

        // Kiểm tra conversation có tồn tại
        const conversation = await Conversation.findById(conversationId);
        if (!conversation) {
            return res.status(404).json({
                success: false,
                message: 'Không tìm thấy cuộc trò chuyện'
            });
        }

        // Lưu tin nhắn của user
        const userMessage = new AiMessage({
            conversationId,
            content,
            imagesUrl,
            role: Role.user
        });
        await userMessage.save();

        // Lấy lịch sử tin nhắn để có context
        const messageHistory = await AiMessage.find({
            conversationId,
            deleted: false
        }).sort({
            createdAt: 1
        }).limit(10); // Lấy 10 tin nhắn gần nhất

        // Chuẩn bị messages cho API
        const messages = [{
                role: 'system',
                content: `Bạn là một trợ lý AI thông minh và hữu ích. Hãy trả lời câu hỏi một cách chi tiết và chính xác.
                    Nếu câu hỏi liên quan đến cryptocurrency, hãy cung cấp thông tin kỹ thuật và phân tích chuyên sâu.
                    Trả lời bằng tiếng Việt một cách tự nhiên và thân thiện.`
            },
            ...messageHistory.map(msg => ({
                role: msg.role,
                content: msg.content
            }))
        ];

        // Gọi API AI
        console.log(this.callAIAPI);
        const aiResponse = await this.callAIAPI(messages);

        // Lưu phản hồi của AI
        const aiMessage = new AiMessage({
            conversationId,
            content: aiResponse,
            imagesUrl: [],
            role: Role.assistant
        });
        await aiMessage.save();

        // Cập nhật thời gian cuộc trò chuyện
        conversation.updatedAt = new Date();
        await conversation.save();

        res.json({
            success: true,
            message: 'Gửi tin nhắn thành công',
            data: {
                userMessage,
                aiMessage
            }
        });

        // } catch (error) {
        //     console.error('Error sending message:', error);
        //     res.status(500).json({
        //         success: false,
        //         message: 'Lỗi khi gửi tin nhắn',
        //         error: error.message
        //     });
        // }
    }

    // Gọi API AI
    async callAIAPI(messages) {
        try {
            const apiKey = process.env.IOINTELLIGENCE_API_KEY;
            if (!apiKey) {
                throw new Error('API key không được cấu hình');
            }

            const response = await axios.post(
                'https://api.intelligence.io.solutions/api/v1/chat/completions', {
                    model: "meta-llama/Llama-3.3-70B-Instruct",
                    messages: messages,
                    stream: false,
                    max_completion_tokens: 1000,
                    temperature: 0.7
                }, {
                    headers: {
                        'Authorization': `Bearer ${apiKey}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            return response.data.choices[0].message.content;
        } catch (error) {
            console.error('Error calling AI API:', error);
            return 'Xin lỗi, hiện tại không thể trả lời câu hỏi của bạn. Vui lòng thử lại sau.';
        }
    }

    // Xóa tin nhắn
    async deleteMessage(req, res) {
        try {
            const {
                messageId
            } = req.params;

            const message = await AiMessage.findById(messageId);
            if (!message) {
                return res.status(404).json({
                    success: false,
                    message: 'Không tìm thấy tin nhắn'
                });
            }

            message.deleted = true;
            message.deletedAt = new Date();
            await message.save();

            res.json({
                success: true,
                message: 'Xóa tin nhắn thành công'
            });
        } catch (error) {
            console.error('Error deleting message:', error);
            res.status(500).json({
                success: false,
                message: 'Lỗi khi xóa tin nhắn'
            });
        }
    }

    // Xóa cuộc trò chuyện
    async deleteConversation(req, res) {
        try {
            const {
                conversationId
            } = req.params;

            const conversation = await Conversation.findById(conversationId);
            if (!conversation) {
                return res.status(404).json({
                    success: false,
                    message: 'Không tìm thấy cuộc trò chuyện'
                });
            }

            conversation.deleted = true;
            conversation.deletedAt = new Date();
            await conversation.save();

            // Xóa tất cả tin nhắn trong cuộc trò chuyện
            await AiMessage.updateMany({
                conversationId
            }, {
                deleted: true,
                deletedAt: new Date()
            });

            res.json({
                success: true,
                message: 'Xóa cuộc trò chuyện thành công'
            });
        } catch (error) {
            console.error('Error deleting conversation:', error);
            res.status(500).json({
                success: false,
                message: 'Lỗi khi xóa cuộc trò chuyện'
            });
        }
    }

}

export default new AIChatController();
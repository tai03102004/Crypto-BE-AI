FROM node:18-alpine  # Thay vì node:18-slim

# Chỉ install cần thiết
RUN apk add --no-cache python3 py3-pip

# Xóa cache sau install
RUN npm install && npm cache clean --force
RUN pip3 install -r requirements.txt && rm -rf ~/.cache/pip

# Multi-stage build
FROM node:18-alpine AS deps
COPY package*.json ./
RUN npm ci --only=production

FROM node:18-alpine AS runner
COPY --from=deps /app/node_modules ./node_modules

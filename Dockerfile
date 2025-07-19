# Use Alpine instead of slim for smaller size
FROM node:18-alpine

# Install Python
RUN apk add --no-cache python3 py3-pip

# Copy package files
COPY package*.json ./
RUN npm install && npm cache clean --force

# Copy requirements and install Python packages
COPY requirements.txt ./
RUN pip3 install -r requirements.txt && rm -rf ~/.cache/pip

# Copy source code
COPY . .

EXPOSE 3000
CMD ["npm", "start"]

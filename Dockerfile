# Base image: Python (vì TensorFlow dễ cài hơn)
FROM python:3.9

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Create app directory
WORKDIR /app

# Copy code
COPY . .

# Install Python dependencies
RUN pip install -r requirements.txt

# Install Node.js dependencies
RUN npm install

# Expose port (nếu Node.js chạy cổng 3000)
EXPOSE 3000

# Start Node.js server
CMD ["npm", "start"]

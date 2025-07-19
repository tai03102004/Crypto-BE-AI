FROM node:18-alpine

RUN apk add --no-cache python3 py3-pip

COPY package*.json ./
RUN npm install

COPY requirements.txt ./
RUN pip3 install -r requirements.txt --break-system-packages

COPY . .

EXPOSE 3000
CMD ["npm", "start"]

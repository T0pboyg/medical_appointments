FROM node:22-slim
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/*.jsx frontend/*.css frontend/*.js frontend/index.html ./
CMD ["npm", "run", "dev"]

# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code and build
COPY . .
RUN npm run build

# Production server stage (using non-root unprivileged nginx)
FROM nginxinc/nginx-unprivileged:alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 8080 (unprivileged port)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

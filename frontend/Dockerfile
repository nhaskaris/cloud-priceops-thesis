# Stage 1: Build Vite app
FROM node:22-alpine AS build
WORKDIR /app

# Copy dependency manifests first for better caching
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy rest of the app
COPY . .

COPY .env .env

# Build the app (Vite outputs to /app/dist)
RUN npm run build

# Stage 2: Serve the built app
FROM node:22-alpine AS production
WORKDIR /app

# Install lightweight static server
RUN npm install -g serve --no-audit --silent

# Copy built files from the build stage
COPY --from=build /app/dist ./dist

EXPOSE 3000

# Serve the Vite build output on port 3000
CMD ["serve", "-s", "dist", "-l", "3000"]

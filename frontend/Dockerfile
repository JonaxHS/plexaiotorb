FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the React app
RUN npm run build

# Use a lightweight Nginx server to serve the static files
FROM nginx:alpine

# Copy the build output from the builder stage
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80 (we'll map it to 5173 or 80 in docker-compose)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

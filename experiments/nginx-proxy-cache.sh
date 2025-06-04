#!/bin/bash
# Script to run Nginx as a reverse proxy with caching in Docker

# Create directories for Nginx configuration and cache
mkdir -p ./nginx/conf.d
mkdir -p ./nginx/cache

# Create Nginx configuration file
cat > ./nginx/conf.d/default.conf << 'EOF'
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m max_size=1g inactive=60m;
proxy_cache_key "$scheme$request_method$host$request_uri";
proxy_cache_valid 200 302 10m;
proxy_cache_valid 404 1m;

server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://backend_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Enable caching
        proxy_cache my_cache;
        proxy_cache_bypass $http_pragma $http_authorization;
        add_header X-Cache-Status $upstream_cache_status;
        
        # Cache control
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_lock on;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
    }

    # Cache status endpoint
    location /cache-status {
        access_log off;
        stub_status on;
    }
}

# Define the upstream server (replace with your actual backend)
upstream backend_server {
    server your-backend-service:8080;
    keepalive 32;
}
EOF

# Create Docker Compose file
cat > ./nginx/docker-compose.yml << 'EOF'
version: '3'

services:
  nginx-proxy:
    image: nginx:alpine
    container_name: nginx-proxy-cache
    ports:
      - "8080:80"
    volumes:
      - ./conf.d:/etc/nginx/conf.d
      - ./cache:/var/cache/nginx
    environment:
      - NGINX_HOST=localhost
      - NGINX_PORT=80
    restart: unless-stopped
    networks:
      - proxy-network

networks:
  proxy-network:
    driver: bridge
EOF

# Run the Docker container
echo "Starting Nginx reverse proxy with cache..."
cd ./nginx
docker-compose up -d

echo "Nginx proxy is running on http://localhost:8080"
echo "To check cache status: http://localhost:8080/cache-status"
echo "To stop the proxy: docker-compose down"

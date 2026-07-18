# StructPilot Docker 部署教程

> 容器化部署 - 一次构建，到处运行

---

## 方案优势

✅ **环境一致性**：开发环境 = 生产环境  
✅ **快速部署**：一条命令启动  
✅ **易于迁移**：打包镜像随处运行  
✅ **资源隔离**：互不干扰  
✅ **版本管理**：支持回滚

---

## 第一步：创建 Dockerfile

在项目根目录创建 `Dockerfile`：

```dockerfile
# 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建运行目录
RUN mkdir -p runtime/memory runtime/cache runtime/uploads

# 暴露端口
EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# 启动命令
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## 第二步：创建 .dockerignore

排除不必要的文件：

```
.env
.git
.gitignore
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.Python
runtime/
*.log
.DS_Store
Thumbs.db
.pytest_cache
```

---

## 第三步：构建镜像

```bash
# 构建镜像
docker build -t structpilot:latest .

# 查看镜像
docker images | grep structpilot
```

---

## 第四步：运行容器

### 方式 A：简单运行（测试）

```bash
docker run -d \
  --name structpilot \
  -p 8501:8501 \
  structpilot:latest
```

访问：`http://localhost:8501`

### 方式 B：完整配置（生产）

```bash
docker run -d \
  --name structpilot \
  -p 8501:8501 \
  -v $(pwd)/runtime:/app/runtime \
  -v $(pwd)/.env:/app/.env \
  --restart unless-stopped \
  --memory="2g" \
  --cpus="2" \
  structpilot:latest
```

参数说明：
- `-d`：后台运行
- `--name`：容器名称
- `-p`：端口映射
- `-v`：挂载卷（持久化数据）
- `--restart`：自动重启策略
- `--memory`：内存限制
- `--cpus`：CPU 限制

---

## 第五步：使用 Docker Compose（推荐）

### 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  structpilot:
    build: .
    container_name: structpilot
    ports:
      - "8501:8501"
    volumes:
      - ./runtime:/app/runtime
      - ./.env:/app/.env:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - structpilot-network

  # 可选：Nginx 反向代理
  nginx:
    image: nginx:alpine
    container_name: structpilot-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - structpilot
    restart: unless-stopped
    networks:
      - structpilot-network

networks:
  structpilot-network:
    driver: bridge
```

### 创建 nginx.conf（如使用 Nginx）

```nginx
server {
    listen 80;
    server_name structpilot.yourdomain.com;

    location / {
        proxy_pass http://structpilot:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    client_max_body_size 200M;
}
```

### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

---

## 常用管理命令

### 容器管理

```bash
# 查看运行的容器
docker ps

# 查看所有容器（包括停止的）
docker ps -a

# 停止容器
docker stop structpilot

# 启动容器
docker start structpilot

# 重启容器
docker restart structpilot

# 删除容器
docker rm structpilot

# 进入容器
docker exec -it structpilot bash
```

### 日志管理

```bash
# 查看实时日志
docker logs -f structpilot

# 查看最近 100 行
docker logs --tail 100 structpilot

# 带时间戳
docker logs -f --timestamps structpilot
```

### 镜像管理

```bash
# 查看镜像
docker images

# 删除镜像
docker rmi structpilot:latest

# 清理未使用的镜像
docker image prune -a

# 导出镜像
docker save -o structpilot.tar structpilot:latest

# 导入镜像
docker load -i structpilot.tar
```

---

## 数据持久化

### 方法 1：绑定挂载（推荐）

```bash
docker run -d \
  -v $(pwd)/runtime:/app/runtime \
  -v $(pwd)/.env:/app/.env \
  structpilot:latest
```

### 方法 2：命名卷

```bash
# 创建卷
docker volume create structpilot-data

# 使用卷
docker run -d \
  -v structpilot-data:/app/runtime \
  structpilot:latest

# 查看卷
docker volume ls

# 删除卷
docker volume rm structpilot-data
```

---

## 环境变量管理

### 方式 1：.env 文件（推荐）

```bash
docker run -d \
  --env-file .env \
  structpilot:latest
```

### 方式 2：命令行传递

```bash
docker run -d \
  -e STRUCTPILOT_LLM_API_KEY=your_key \
  -e STRUCTPILOT_LLM_MODEL=Qwen/Qwen3-VL-32B-Instruct \
  structpilot:latest
```

### 方式 3：Docker Secrets（生产环境）

```bash
# 创建 secret
echo "your_api_key" | docker secret create llm_api_key -

# 在 docker-compose.yml 中使用
secrets:
  llm_api_key:
    external: true
```

---

## 多容器编排示例

完整的 `docker-compose.yml`（带数据库和缓存）：

```yaml
version: '3.8'

services:
  structpilot:
    build: .
    container_name: structpilot
    ports:
      - "8501:8501"
    volumes:
      - app-data:/app/runtime
      - ./.env:/app/.env:ro
    restart: unless-stopped
    depends_on:
      - redis
    networks:
      - app-network

  redis:
    image: redis:alpine
    container_name: structpilot-redis
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    container_name: structpilot-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - structpilot
    restart: unless-stopped
    networks:
      - app-network

volumes:
  app-data:
  redis-data:

networks:
  app-network:
    driver: bridge
```

---

## 生产环境部署

### 1. 在服务器上安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo apt install docker-compose -y

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. 上传项目文件

```bash
# 在本地打包
tar -czf structpilot-docker.tar.gz \
  Dockerfile \
  docker-compose.yml \
  requirements.txt \
  main.py \
  graph/ \
  agents/ \
  knowledge_base/ \
  config/ \
  ui/ \
  utils/ \
  validator/ \
  assets/ \
  .streamlit/

# 上传到服务器
scp structpilot-docker.tar.gz root@服务器IP:/opt/

# 在服务器上解压
ssh root@服务器IP
cd /opt
tar -xzf structpilot-docker.tar.gz
cd structpilot
```

### 3. 配置并启动

```bash
# 创建 .env 文件
cp .env.example .env
nano .env

# 创建必要目录
mkdir -p runtime ssl

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务（不停机）
docker-compose up -d --no-deps --build structpilot

# 或完全重启
docker-compose down
docker-compose up -d
```

---

## 监控与日志

### 查看资源使用

```bash
# 查看容器资源使用
docker stats

# 查看特定容器
docker stats structpilot
```

### 日志轮转配置

在 `docker-compose.yml` 中添加：

```yaml
services:
  structpilot:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 故障排查

### 容器无法启动

```bash
# 查看容器状态
docker ps -a

# 查看启动日志
docker logs structpilot

# 检查配置
docker inspect structpilot
```

### 网络问题

```bash
# 查看网络
docker network ls

# 检查网络连接
docker network inspect structpilot-network

# 测试容器间通信
docker exec structpilot ping nginx
```

### 数据丢失

```bash
# 查看挂载卷
docker volume inspect structpilot-data

# 备份卷
docker run --rm \
  -v structpilot-data:/source \
  -v $(pwd):/backup \
  alpine tar -czf /backup/backup.tar.gz -C /source .
```

---

## 安全加固

### 1. 使用非 root 用户

修改 `Dockerfile`：

```dockerfile
# 创建非特权用户
RUN useradd -m -u 1000 structpilot

# 切换用户
USER structpilot
```

### 2. 限制资源

在 `docker-compose.yml` 中：

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '1'
      memory: 1G
```

### 3. 只读文件系统

```yaml
read_only: true
tmpfs:
  - /tmp
  - /app/runtime
```

---

## 常见问题

### Q1: 容器启动后立即退出

**排查**：
```bash
docker logs structpilot
docker inspect structpilot
```

### Q2: 无法访问应用

**检查**：
- 端口映射是否正确
- 防火墙是否开放端口
- 容器是否正常运行

### Q3: 数据持久化失败

**原因**：卷挂载配置错误

**解决**：
```bash
# 检查卷
docker volume inspect structpilot-data

# 重新创建
docker-compose down -v
docker-compose up -d
```

---

**Docker 部署版本**：v1.0  
**最后更新**：2026-07-18  
**适用软件版本**：StructPilot v6.0

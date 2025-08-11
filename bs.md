# UniHome租房系统部署指南

## 🚀 三种部署方案对比

| 方案 | 难度 | 成本 | 性能 | 推荐度 |
|------|------|------|------|--------|
| **方案1: 免费云平台** | ⭐ | 免费 | ⭐⭐ | 🔥🔥🔥 |
| **方案2: 内网穿透** | ⭐⭐ | 免费 | ⭐⭐⭐ | 🔥🔥 |
| **方案3: VPS部署** | ⭐⭐⭐ | $5-15/月 | ⭐⭐⭐⭐⭐ | 🔥 |

---

# 🎯 方案1: 免费云平台部署 (推荐新手)

## 特点
- ✅ **完全免费** - 无需任何费用
- ✅ **零配置** - 几分钟完成部署
- ✅ **自动HTTPS** - 平台自动提供SSL证书
- ✅ **全球CDN** - 加拿大访问速度快
- ❌ **有使用限制** - 免费额度有限

## 1.1 Render.com 部署 (最推荐)

### 准备工作
1. **注册GitHub账户**: https://github.com
2. **上传代码到GitHub**:
```bash
# 在项目目录执行
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/unihome.git
git push -u origin main
```

### 修改代码适配云平台
创建 `requirements.txt` (如果没有):
```txt
Flask==2.0.1
Flask-SQLAlchemy==2.5.1
Werkzeug==2.0.1
Jinja2==3.0.1
python-dotenv==0.19.0
gunicorn==20.1.0
```

修改 `app.py` 最后几行:
```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### Render部署步骤
1. **访问Render**: https://render.com
2. **注册账户** (可用GitHub登录)
3. **创建新服务**:
   - 点击 "New" → "Web Service"
   - 连接GitHub仓库
   - 选择您的unihome项目
4. **配置服务**:
   - Name: `unihome-rental`
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
5. **点击Deploy** - 等待3-5分钟完成部署

### 获取访问地址
部署完成后，您会得到类似这样的地址:
```
https://unihome-rental.onrender.com
```

## 1.2 Railway.app 部署 (备选)

### 部署步骤
1. **访问Railway**: https://railway.app
2. **GitHub登录**
3. **New Project** → **Deploy from GitHub repo**
4. **选择您的仓库**
5. **自动部署** - Railway会自动识别Flask应用

### 配置环境变量 (可选)
在Railway控制台设置:
```
SECRET_KEY=your-secret-key-here
```

## 1.3 Vercel部署 (适合静态化)

如果您想要更好的性能，可以考虑将应用静态化:

创建 `vercel.json`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app.py"
    }
  ]
}
```

---

# 🏠 方案2: 内网穿透 (本地运行)

## 特点
- ✅ **完全免费** - 使用免费内网穿透服务
- ✅ **本地运行** - 代码在您的电脑上运行
- ✅ **实时调试** - 修改代码立即生效
- ❌ **需要保持开机** - 电脑关机网站就无法访问
- ❌ **网络依赖** - 依赖您的网络稳定性

## 2.1 使用ngrok (推荐)

### 安装ngrok
1. **注册账户**: https://ngrok.com
2. **下载ngrok**:
   - Windows: 下载exe文件
   - 解压到任意目录
3. **获取认证token**:
   - 登录ngrok控制台
   - 复制Your Authtoken

### 配置和启动
```bash
# 1. 认证ngrok
ngrok authtoken YOUR_AUTH_TOKEN

# 2. 启动您的Flask应用
python app.py

# 3. 新开命令行窗口，启动ngrok
ngrok http 5000
```

### 获取公网地址
ngrok会显示类似这样的地址:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

加拿大用户就可以通过 `https://abc123.ngrok.io` 访问您的网站！

## 2.2 使用花生壳 (国内用户友好)

### 安装步骤
1. **下载花生壳客户端**: https://hsk.oray.com
2. **注册账户并登录**
3. **添加映射**:
   - 内网地址: `127.0.0.1:5000`
   - 选择免费域名
4. **启动服务**

## 2.3 使用frp (开源方案)

### 客户端配置
创建 `frpc.ini`:
```ini
[common]
server_addr = frp服务器地址
server_port = 7000

[web]
type = http
local_ip = 127.0.0.1
local_port = 5000
custom_domains = your-domain.com
```

---

# 🔧 方案3: VPS部署 (专业方案)

## 简化版VPS部署

如果您还是想要VPS部署，这里是最简化的步骤:

### 一键部署脚本
创建 `deploy.sh`:
```bash
#!/bin/bash
# UniHome一键部署脚本

echo "开始部署UniHome..."

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip nginx

# 安装Python依赖
pip3 install -r requirements.txt
pip3 install gunicorn

# 启动应用
gunicorn -w 2 -b 0.0.0.0:5000 app:app &

# 配置Nginx
sudo tee /etc/nginx/sites-available/default > /dev/null <<EOF
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

# 重启Nginx
sudo systemctl restart nginx

echo "部署完成！访问 http://您的服务器IP 即可"
```

### 使用方法
```bash
chmod +x deploy.sh
./deploy.sh
```

---

# 🎯 推荐方案选择

## 新手用户 → 方案1: Render.com
- **优点**: 最简单，完全免费，自动HTTPS
- **适合**: 学习、演示、小流量使用
- **操作时间**: 10分钟

## 开发调试 → 方案2: ngrok
- **优点**: 本地运行，实时调试，免费
- **适合**: 开发测试、临时展示
- **操作时间**: 5分钟

## 商业运营 → 方案3: VPS
- **优点**: 完全控制，高性能，无限制
- **适合**: 正式运营、高流量
- **操作时间**: 2-4小时

---

# 🚀 快速开始 (推荐新手)

## 最简单的5分钟部署

1. **上传代码到GitHub**
2. **访问 https://render.com**
3. **GitHub登录 → New Web Service**
4. **选择仓库 → Deploy**
5. **等待部署完成**

就这么简单！您的网站就可以全球访问了！

需要详细步骤的话，请告诉我您选择哪个方案，我可以提供更具体的操作指导。

---

# 📋 详细操作步骤

## 方案1详细步骤: Render.com免费部署

### 第1步: 准备GitHub仓库

1. **访问GitHub**: https://github.com
2. **注册/登录账户**
3. **创建新仓库**:
   - 点击右上角 "+" → "New repository"
   - Repository name: `unihome-rental`
   - 设为Public
   - 点击 "Create repository"

### 第2步: 上传项目代码

**方法A: 使用GitHub网页上传**
1. 在新建的仓库页面点击 "uploading an existing file"
2. 将您的所有项目文件拖拽到页面上
3. 填写提交信息: "Initial commit"
4. 点击 "Commit changes"

**方法B: 使用Git命令** (如果您熟悉Git)
```bash
# 在项目目录执行
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/unihome-rental.git
git push -u origin main
```

### 第3步: 修改代码适配云平台

在项目根目录创建/修改以下文件:

**requirements.txt** (必须):
```txt
Flask==2.0.1
Flask-SQLAlchemy==2.5.1
Werkzeug==2.0.1
Jinja2==3.0.1
python-dotenv==0.19.0
gunicorn==20.1.0
```

**修改app.py最后几行**:
```python
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

### 第4步: 部署到Render

1. **访问Render**: https://render.com
2. **注册账户**:
   - 点击 "Get Started for Free"
   - 选择 "GitHub" 登录
   - 授权Render访问您的GitHub
3. **创建Web Service**:
   - 点击 "New +" → "Web Service"
   - 选择 "Connect a repository"
   - 找到并选择 `unihome-rental` 仓库
   - 点击 "Connect"
4. **配置部署设置**:
   - **Name**: `unihome-rental`
   - **Environment**: `Python 3`
   - **Region**: `Oregon (US West)` (对加拿大用户较快)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
   - **Plan**: 选择 "Free" (免费)
5. **点击 "Create Web Service"**

### 第5步: 等待部署完成

- 部署过程需要3-5分钟
- 您可以在页面上看到实时日志
- 部署成功后会显示绿色的 "Live" 状态

### 第6步: 获取访问地址

部署完成后，您会得到一个地址，类似:
```
https://unihome-rental.onrender.com
```

🎉 **恭喜！您的网站现在可以全球访问了！**

### 第7步: 测试功能

1. **访问首页**: 打开您的网站地址
2. **测试管理后台**: 访问 `您的网站地址/admin/login`
   - 用户名: admin
   - 密码: admin123
3. **测试房源展示**: 检查房源列表和详情页

---

## 方案2详细步骤: ngrok内网穿透

### 第1步: 安装ngrok

1. **访问ngrok官网**: https://ngrok.com
2. **注册免费账户**
3. **下载ngrok**:
   - Windows: 下载 `ngrok.exe`
   - 解压到任意文件夹 (如 `C:\ngrok\`)

### 第2步: 配置ngrok

1. **获取认证token**:
   - 登录ngrok控制台
   - 在Dashboard页面找到 "Your Authtoken"
   - 复制token
2. **认证ngrok**:
```bash
# 在ngrok目录执行
ngrok authtoken YOUR_AUTH_TOKEN_HERE
```

### 第3步: 启动应用

1. **启动Flask应用**:
```bash
# 在项目目录执行
python app.py
```
确保看到类似输出:
```
* Running on http://127.0.0.1:5000
```

2. **新开命令行窗口，启动ngrok**:
```bash
# 在ngrok目录执行
ngrok http 5000
```

### 第4步: 获取公网地址

ngrok启动后会显示:
```
Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        United States (us)
Forwarding                    https://abc123.ngrok.io -> http://localhost:5000
Forwarding                    http://abc123.ngrok.io -> http://localhost:5000
```

🎉 **您的网站地址**: `https://abc123.ngrok.io`

### 第5步: 分享给用户

- 将 `https://abc123.ngrok.io` 地址分享给加拿大用户
- 只要您的电脑开机且运行着Flask应用，用户就能访问
- 每次重启ngrok，地址会变化 (免费版限制)

---

## 🔧 常见问题解决

### Render部署问题

**问题1: 部署失败，显示"Build failed"**
```
解决方案:
1. 检查requirements.txt文件是否存在
2. 确保app.py中有正确的端口配置
3. 查看Build日志，找到具体错误信息
```

**问题2: 网站显示"Application Error"**
```
解决方案:
1. 检查app.py中的数据库路径
2. 确保所有依赖都在requirements.txt中
3. 查看Runtime日志
```

**问题3: 静态文件无法加载**
```
解决方案:
1. 确保static文件夹已上传到GitHub
2. 检查HTML中的静态文件路径
```

### ngrok使用问题

**问题1: ngrok显示"command not found"**
```
解决方案:
1. 确保ngrok.exe在当前目录
2. 或将ngrok添加到系统PATH环境变量
```

**问题2: 访问网站显示"Tunnel not found"**
```
解决方案:
1. 确保Flask应用正在运行
2. 检查端口号是否正确 (默认5000)
3. 重启ngrok
```

**问题3: 网站访问很慢**
```
解决方案:
1. 免费版ngrok服务器在美国，延迟较高
2. 考虑升级到付费版选择更近的服务器
3. 或使用其他内网穿透工具
```

---

## 💡 优化建议

### 提升网站性能

1. **启用Gzip压缩** (Render自动启用)
2. **优化图片大小**:
```bash
# 压缩图片 (可选)
pip install Pillow
```

3. **添加缓存头**:
```python
# 在app.py中添加
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
```

### 自定义域名 (可选)

**Render.com自定义域名**:
1. 在Render控制台点击您的服务
2. 进入 "Settings" → "Custom Domains"
3. 添加您的域名
4. 按提示配置DNS记录

**ngrok自定义域名** (付费功能):
```bash
ngrok http 5000 -hostname=your-domain.com
```

---

## 📊 方案对比总结

| 特性 | Render.com | ngrok | VPS |
|------|------------|-------|-----|
| **成本** | 免费 | 免费 | $5-15/月 |
| **设置时间** | 10分钟 | 5分钟 | 2-4小时 |
| **技术难度** | ⭐ | ⭐ | ⭐⭐⭐ |
| **稳定性** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **访问速度** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **自定义域名** | ✅ (付费) | ✅ (付费) | ✅ (免费) |
| **SSL证书** | ✅ 自动 | ✅ 自动 | 需配置 |
| **适用场景** | 演示、学习 | 开发、测试 | 商业运营 |

## 🎯 最终推荐

**新手首选**: Render.com - 最简单，完全免费，适合学习和演示
**开发测试**: ngrok - 本地运行，方便调试
**商业运营**: VPS - 完全控制，高性能

选择适合您需求的方案，按照上面的详细步骤操作即可！

---

# 🔗 有用链接

- **Render.com**: https://render.com
- **ngrok**: https://ngrok.com
- **GitHub**: https://github.com
- **免费域名**: https://www.freenom.com
- **VPS推荐**: https://www.vultr.com

需要更详细的帮助或遇到问题，随时告诉我！

---

# 🏆 高级方案: VPS部署 (可选)

如果您需要更高的性能和完全的控制权，可以选择VPS部署。这里提供简化版的VPS部署步骤：

## VPS一键部署脚本

创建 `deploy.sh` 文件：
```bash
#!/bin/bash
echo "🚀 开始部署UniHome到VPS..."

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip nginx git

# 克隆项目 (替换为您的仓库地址)
git clone https://github.com/yourusername/unihome-rental.git
cd unihome-rental

# 安装Python依赖
pip3 install -r requirements.txt
pip3 install gunicorn

# 启动应用 (后台运行)
nohup gunicorn -w 2 -b 127.0.0.1:5000 app:app > app.log 2>&1 &

# 配置Nginx
sudo tee /etc/nginx/sites-available/default > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /static {
        alias $(pwd)/static;
        expires 30d;
    }
}
EOF

# 重启Nginx
sudo systemctl restart nginx

echo "✅ 部署完成！"
echo "🌐 访问地址: http://您的服务器IP"
echo "🔧 管理后台: http://您的服务器IP/admin/login"
```

## 使用方法

1. **购买VPS** (推荐香港节点):
   - Vultr: https://www.vultr.com
   - DigitalOcean: https://www.digitalocean.com
   - 最低配置: 1核1GB内存即可

2. **连接服务器**:
```bash
ssh root@your_server_ip
```

3. **运行部署脚本**:
```bash
wget https://raw.githubusercontent.com/yourusername/unihome-rental/main/deploy.sh
chmod +x deploy.sh
./deploy.sh
```

4. **访问网站**: `http://您的服务器IP`

## 免费域名配置

如果您想要自定义域名：

1. **注册免费域名**: https://www.freenom.com
2. **配置DNS记录**:
   - 类型: A
   - 名称: @
   - 值: 您的服务器IP
3. **修改Nginx配置**中的 `server_name` 为您的域名

---

# 📞 总结和建议

## 🎯 方案选择指南

**完全新手** → **Render.com**
- ✅ 10分钟完成部署
- ✅ 完全免费
- ✅ 自动HTTPS
- ✅ 全球CDN加速

**开发调试** → **ngrok**
- ✅ 5分钟开始使用
- ✅ 本地运行，方便修改
- ✅ 实时调试

**商业运营** → **VPS**
- ✅ 完全控制
- ✅ 高性能
- ✅ 无使用限制
- ❌ 需要一定技术基础

## 🚀 推荐操作流程

1. **先用Render.com** - 快速上线，让加拿大用户能够访问
2. **测试功能** - 确保所有功能正常工作
3. **收集反馈** - 了解用户需求和问题
4. **考虑升级** - 如果流量大了再考虑VPS

## 💰 成本对比

| 方案 | 月成本 | 年成本 | 适用阶段 |
|------|--------|--------|----------|
| Render.com | $0 | $0 | 启动阶段 |
| ngrok | $0 | $0 | 开发测试 |
| VPS | $60-180 | $60-180 | 成熟运营 |

## 🎉 部署完成后

无论选择哪种方案，部署完成后您都将拥有：

✅ **全球可访问的租房网站**
✅ **完整的管理后台系统**
✅ **HTTPS安全加密**
✅ **移动端适配**
✅ **房源展示和搜索功能**

**加拿大用户现在就可以通过浏览器访问您的租房平台了！**

---

## 🆘 需要帮助？

如果在部署过程中遇到任何问题：

1. **检查错误日志** - 大部分问题都能从日志中找到原因
2. **重新部署** - 有时候重新部署就能解决问题
3. **询问我** - 随时告诉我具体的错误信息，我来帮您解决



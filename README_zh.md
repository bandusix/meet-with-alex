# Meet With ALEX - Interview Scheduler 🚀

[🇬🇧 English Documentation](./README.md)

这是一个极客风格（Geek Style）的自动化面试预约系统。候选人可以通过该页面选择时间，系统将通过飞书 API 自动生成专属视频会议链接，并写入面试官（ALEX）的飞书日历。

**🌐 在线演示 (Live Demos):**
- [Vercel 部署地址](https://meet-with-alex.vercel.app/)
- [Railway 部署地址](https://meet-with-alex-production.up.railway.app)

## 核心特性
- 💻 **Geek / Hacker UI**：基于 GitHub Dark Mode 配色与 Fira Code 等宽字体，模拟终端命令行交互体验。
- 📅 **自动化日历同步**：对接飞书开放平台，自动在日历中创建包含专属视频会议链接的日程。
- ☁️ **云端原生支持**：开箱即用，已适配 Vercel（Serverless 函数）和 Railway 环境配置。

---

## 准备工作（飞书权限配置）
在部署前，你需要确保在飞书开放平台（[open.feishu.cn](https://open.feishu.cn/)）创建了“企业自建应用”，并拥有以下信息：
1. **App ID** (`FEISHU_APP_ID`)
2. **App Secret** (`FEISHU_APP_SECRET`)
3. **User ID** (`FEISHU_USER_ID`) - 你本人的飞书 open_id

**⚠️ 必须开通并发布的飞书权限：**
- 获取与更新视频会议信息 (`vc:meeting`)
- 预约视频会议 (`vc:reserve`)
- 获取与更新用户日历及日程 (`calendar:calendar`)
- 创建日历日程 (`calendar:calendar.event:create`)
- 获取用户 user ID (`contact:user.employee_id:readonly`)

*(注：权限勾选后，请务必点击“版本管理与发布”创建一个新版本，审核通过后权限才会生效)*

---

## 部署指南 ☁️

本项目支持一键部署到主流的云托管平台，推荐使用 **Vercel** 或 **Railway**。

### 选项 A: 部署到 Vercel (推荐)
本项目根目录下已经包含了 `vercel.json`，可以直接被 Vercel 识别为 Python Serverless 项目。

1. 登录 [Vercel](https://vercel.com/)。
2. 点击右上角 **"Add New"** -> **"Project"**。
3. 在 Import Git Repository 列表中，找到并导入（Import）你的 `meet-with-alex` 仓库。
4. 展开 **Environment Variables** (环境变量) 区域，依次添加以下三个变量：
   - Name: `FEISHU_APP_ID` | Value: *你的飞书 App ID*
   - Name: `FEISHU_APP_SECRET` | Value: *你的飞书 App Secret*
   - Name: `FEISHU_USER_ID` | Value: *你的飞书 Open ID*
5. 点击 **Deploy**。
6. 等待约 1-2 分钟，部署完成后，Vercel 会分配一个类似 `meet-with-alex.vercel.app` 的域名，即可访问使用！

### 选项 B: 部署到 Railway
本项目根目录下包含了 `railway.toml`，Railway 会使用 Nixpacks 自动构建并启动 FastAPI。

1. 登录 [Railway](https://railway.app/)。
2. 点击 **"New Project"**，选择 **"Deploy from GitHub repo"**。
3. 选择你的 `meet-with-alex` 仓库。
4. 点击卡片进入项目设置，切换到 **Variables** 面板。
5. 点击 **"New Variable"**，添加与上述 Vercel 相同的三个飞书环境变量（`FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_USER_ID`）。
6. 切换到 **Settings** 面板，在 **Networking** 区域点击 **"Generate Domain"**。
7. 等待构建完成，点击生成的公开域名即可访问！

---

## 本地开发与测试
如果你想在本地运行修改此项目：

1. 克隆仓库：
   ```bash
   git clone https://github.com/bandusix/meet-with-alex.git
   cd meet-with-alex
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 复制 `.env.example` 为 `.env` 并填入你的飞书密钥：
   ```bash
   cp .env.example .env
   ```

4. 启动服务：
   ```bash
   python main.py
   ```
   随后在浏览器访问 `http://localhost:8000` 即可预览。

---

## 更新日志 (Changelog)

### v1.1.0 (最新版)
- ✨ **智能防冲突机制**：接入飞书的日历忙闲接口 (`calendar/v4/freebusy/list`)。系统会自动查询面试官的飞书日程，一旦发现某个时间段已被其他会议占用，将自动在前端禁用该时间段（变灰且带删除线），彻底避免面试撞车。
- 🌍 **国际化改造**：将用户界面全面更新为地道的纯英文版本，以更好地适配各类产品经理候选人。
- 🎨 **UI 体验提升**：在保持极客/黑客风格的基础上，新增了欢迎致辞。

### v1.0.0
- 🎉 首次发布。
- 📅 接入飞书 API，支持自动创建日程与视频会议链接。
- 💻 采用 GitHub 暗黑模式及 Fira Code 字体，打造极客命令行风格 UI。
- 🍪 引入 Cookie 机制，支持候选人查询、修改和取消预约。
- ☁️ 支持 Vercel 及 Railway 一键云端部署。

---
*Powered by ALEX*
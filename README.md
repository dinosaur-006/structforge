# StructForge — 电商爆款视频结构迁移引擎

从优质带货样例中提取结构骨架 → 迁移到你的商品 → 生成 AI 画面 + 配音 + 字幕的新视频

## 快速启动

### 1. 环境要求

- Python 3.12+
- Node.js 18+
- FFmpeg (PATH 可访问)

### 2. 配置 API Key

```bash
cd ai-services
cp .env.example .env
```

编辑 `.env`:
```env
# 必需: LLM (结构提取+脚本迁移+提示词生成)
STRUCTFORGE_DOUBAO_LLM_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3/chat/completions
STRUCTFORGE_DOUBAO_LLM_API_KEY=your-key-here
STRUCTFORGE_DOUBAO_LLM_MODEL=ep-xxxxxxxxxxxx-xxxxx

# 必需: AI 图片生成 (RunningHub ComfyUI)
STRUCTFORGE_RUNNINGHUB_API_KEY=your-32-char-hex-key

# 可选: 语音转写 (不用则自动跳过)
STRUCTFORGE_VOLCANO_ASR_ENDPOINT=
STRUCTFORGE_VOLCANO_ASR_API_KEY=
```

### 3. 启动后端

```bash
cd ai-services
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 启动前端

```bash
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`

### 5. 使用流程

1. **分析台** → 上传一条电商带货视频，等待 AI 分析 (~60s)
2. **编辑台** → 输入你的产品名和卖点，可选上传产品图
3. 点击「生成视频脚本」→ 进入结果展示台
4. 逐段选择生成模式 (生图/生视频)，点击 RENDER ALL
5. 渲染完成 → 播放 AI 生成的视频

## 技术栈

React 18 + TypeScript | Python FastAPI | Doubao LLM | ComfyUI Flux | Edge TTS | FFmpeg | SQLite

## 项目文档

- [项目说明](docs/PROJECT.md) — AI架构、结构定义、迁移方法
- [演示方案](docs/DEMO.md) — 演示流程脚本
- [AI工具声明](docs/AI_TOOLS.md) — 工具清单、自主设计说明
- [赛题评估](docs/赛题对照评估报告.md) — 赛题逐项评分预估

## 视频素材资源

以下平台可获取免版权电商带货视频用于演示:

| 平台 | 链接 | 说明 |
|------|------|------|
| Pexels | https://www.pexels.com/search/videos/ecommerce/ | 免版权电商类视频 |
| Coverr | https://coverr.co/ | 免费商业视频素材 |
| Mixkit | https://mixkit.co/free-stock-video/ | 免费高清视频 |

建议搜索关键词: "product review", "unboxing", "commercial", "food advertisement"

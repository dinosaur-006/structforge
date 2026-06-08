# StructForge — 爆款结构迁移引擎

将优质视频的创作结构（脚本节奏、包装手法、剪辑模式）迁移到新商品和素材上，**迁移创作方法而非复制内容**。

## 快速开始

```powershell
# 1. 安装依赖
npm install
cd ai-services && python -m pip install -r requirements.txt && cd ..

# 2. 配置 API（编辑 ai-services/.env）
# STRUCTFORGE_DOUBAO_LLM_ENDPOINT=<你的豆包API地址>
# STRUCTFORGE_DOUBAO_LLM_API_KEY=<你的API Key>
# STRUCTFORGE_DOUBAO_LLM_MODEL=<你的模型ID>
# STRUCTFORGE_CELERY_TASK_ALWAYS_EAGER=true

# 3. 启动后端（终端1）
cd ai-services
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# 4. 启动前端（终端2）
cd ..
npm run dev

# 5. 打开 http://localhost:5173
```

首次启动会自动创建 Demo 项目，无需上传视频即可体验全部功能。

## 产品流程

```
上传样例视频 → AI 结构拆解 → 输入新素材 → 缺口补全 → 脚本生成 → 视频渲染导出
```

## 核心能力

| 能力 | 说明 |
|------|------|
| 结构拆解 | 4 类结构（脚本/节奏/包装/健康度），图表可视化 |
| 素材匹配 | 视觉分析 + 场景分类 + 槽位匹配推荐 |
| 缺口补全 | 4 策略（包装/AIGC/重组/重排），一键自动修复 |
| 结构迁移 | 5 版本风格（默认/高点击/快节奏/高转化/高质感） |
| 自然语言编辑 | Ctrl+K 唤醒，一句话调整视频结构 |
| 视频渲染 | FFmpeg 逐分镜合成，ASS 字幕叠加 |
| 可解释性 | 来源追踪 + 决策面板 + 公式化评估 |

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19 + TypeScript + Zustand + Tailwind CSS + Recharts |
| 后端 | FastAPI + SQLite + Celery + Redis |
| AI | Doubao-Seed-2.0-lite（结构提取 + 脚本生成 + 视觉理解） |
| 媒体 | FFmpeg + PySceneDetect + WhisperX + Pillow |
| 测试 | Vitest + Pytest + Playwright |

## 项目结构

```
├── src/                    # 前端 React 源码
│   ├── pages/              # 5 个路由页面
│   ├── components/         # UI 组件
│   ├── services/api.ts     # API 客户端
│   └── store/index.ts      # Zustand 状态管理
├── ai-services/            # 后端 FastAPI 源码
│   ├── services/           # 业务逻辑（20+ 服务模块）
│   ├── routes/             # API 路由
│   ├── models/             # 数据模型 + SQLite 仓库
│   ├── tasks/              # Celery 异步任务
│   └── tests/              # Pytest 测试
├── docs/                   # 文档
│   ├── PROJECT.md          # 项目说明文档
│   └── cases/              # 案例文档
└── docker-compose.yml      # Docker 部署配置
```

## 文档

- [项目说明文档](docs/PROJECT.md)
- [演示脚本](docs/cases/demo-walkthrough.md)
- [赛题完成度清单](docs/cases/competition-checklist.md)

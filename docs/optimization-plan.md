# StructForge 全面优化规划 v2

## 第一部分：赛题评审疼点修复

### Phase 1: 致命问题 ✅ 已完成

| # | 疼点 | 修复 | 文件 |
|---|------|------|------|
| P1-1 | 结构迁移=模板填充 | LLM输出5个可执行制作参数【镜/字/速/情/视】 | `migrator.py` |
| P1-2 | 渲染=PPT导出 | Ken Burns缩放动画 (zoompan filter) | `compositor.py` |
| P1-3 | 评分无现实锚点 | LLM prompt加入平台基准(完播率→分,点击率→分) | `llm_structure.py` |

### Phase 2: 关键问题 ✅ 已完成

| # | 疼点 | 修复 | 文件 |
|---|------|------|------|
| P2-2 | 缺口检测=关键词 | 缺口描述升级为详细创作指导(含画面类型+拍摄建议) | `gap_detector.py` |
| P2-3 | 五段模板硬编码 | 动态段落数(3-8段),基于场景检测+LLM判断 | `llm_structure.py` |
| P3-5 | 结构重排不触发 | 放宽触发条件(有edit_plan即可) | `migrator.py` |

### Phase 3: 剩余赛题问题

| # | 疼点 | 解决方案 |
|---|------|---------|
| P2-1 | 结构提取浅(无镜头类型) | Vision prompt加shot_type/motion_type标注 |
| P2-5 | 素材重组只截0s | Vision帧标签匹配最佳片段 |
| P2-6 | 渲染无转场 | FFmpeg xfade(dissolve/slide) |
| P3-2 | TTS段落间不连贯 | 整段脚本一次TTS→按时间戳切分 |
| P3-3 | BGM为空 | FFmpeg生成氛围音轨/内置CC0音乐 |
| P3-4 | 无用户引导 | 首页三步引导卡片 |
| P3-6 | 无案例库 | seed.py增加美妆/3C/食品demo |

---

## 第二部分：产品化优化（对标可上线产品）

### Phase 4: 摩擦消除（本周，高影响低工作量）

| # | 疼点 | 当前 | 解决方案 | 文件 |
|---|------|------|---------|------|
| P4-1 | 上传无进度 | 选文件即开始分析 | 上传进度条 "正在上传 45%" | `VideoUploader.tsx`, `api.ts` |
| P4-2 | 错误信息技术化 | "FinalScript segment ids must exactly match" | 错误码→中文映射表, 前端统一显示 | `errorMessages.ts`, 各catch块 |
| P4-3 | 无品牌感 | 标签页显示Vite图标 | favicon + title "StructForge" + og标签 | `index.html` |
| P4-4 | 成功操作无反馈 | 创建/删除静默完成 | Store所有mutation加success toast | `store/index.ts` |
| P4-5 | 加载态不统一 | 空白/骨架/转圈混用 | 统一标准:<1s无,1-3s骨架,>3s进度 | 各页面 |
| P4-6 | 分析完成后无引导 | 结果在下方容易被忽略 | 顶部醒目成功横幅引导下一步 | `AnalyzePage.tsx` |
| P4-7 | LLM失败无降级 | 3次重试后报错中断 | 自动降级到本地回退+toast提示 | `pipeline.py`,`migrator.py` |
| P4-8 | 渲染进度太粗 | 只显示百分比 | 显示"正在渲染分镜 2/5" | `compositor.py`, `ExportDialog.tsx` |

### Phase 5: 可用性提升（中工作量）

| # | 疼点 | 当前 | 解决方案 | 文件 |
|---|------|------|---------|------|
| P5-1 | 项目列表不可搜索 | 50个项目只能肉眼找 | 搜索框+状态筛选+排序 | `ProjectListPage.tsx` |
| P5-2 | 无版本历史 | 旧脚本被覆盖 | 侧边版本历史面板+一键恢复 | `ResultPage.tsx` |
| P5-3 | 渲染不可取消 | 点导出不能反悔 | DELETE取消+清理临时文件 | `routes/render.py` |
| P5-4 | 分析无中间结果 | 进度条只显示百分比 | SSE推送中间结果实时展示 | `pipeline.py`,`AnalyzePage.tsx` |
| P5-5 | 断网无恢复 | 中断后无法继续 | 网络恢复自动续传 | `api.ts`,`store/index.ts` |

### Phase 6: 体验打磨（低优先级）

| # | 疼点 | 解决方案 | 文件 |
|---|------|---------|------|
| P6-1 | TTS段落不连贯 | 整段TTS+按时间戳切分 | `tts_engine.py` |
| P6-2 | 素材重组不智能 | Vision帧标签匹配最佳片段 | `gap_filler.py` |
| P6-3 | 无案例库 | seed.py增加3品类demo | `seed.py` |
| P6-4 | 快捷键不可见 | AppLayout底部"?快捷键"入口+cheat sheet | `AppLayout.tsx` |
| P6-5 | 无帮助入口 | 右下角固定"?"按钮+FAQ浮层 | `HelpButton.tsx` |
| P6-6 | BGM目录空 | FFmpeg生成氛围音轨 | `bgm_engine.py` |
| P6-7 | 版本对比不直观 | 并排对比/叠层slider | `ResultPage.tsx` |
| P6-8 | 渲染无转场 | FFmpeg xfade | `compositor.py` |

---

## 执行顺序

```
Phase 4 (立即) → Phase 5 (本周) → Phase 6 (后续) → Phase 3剩余 (最后)
```

每个Phase完成后验证: `pytest` + `vitest` + `tsc` 全部通过。

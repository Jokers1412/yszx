# 云枢智学 · 前端（双 SPA 独立部署）

> 设计依据：`docs/design/02.整体架构设计.md`（§4.3 目录规划）。当前状态：**基础工程骨架**（2026-11-23）。
> 技术栈（02 P2 定稿）：Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts 5。

## 结构

| 目录 | 说明 | dev 端口 |
|---|---|---|
| `portal/` | 学员端 SPA（13 页，与 prototype/portal 对应） | 5173 |
| `admin/` | 管理端 SPA（12 页，与 prototype/admin 对应）+ v-permission 指令 | 5174 |
| `shared/` | 双端共享契约类型（统一响应/分页/枚举，对齐 04），经 `@shared/*` 别名引入 | — |

## 快速开始

```bash
cd frontend/portal && npm install && npm run dev   # http://localhost:5173
cd frontend/admin  && npm install && npm run dev   # http://localhost:5174
```

开发期 `/api` 由 vite proxy 转发到 `http://localhost:8000`（FastAPI）；
生产由 Nginx 托管静态资源并反代 `/api`（02 §1.3.5）。

## 约定

- **登录态**：双端独立 JWT 存 localStorage（键 `yszx_*` 前缀）；refresh「记住我」30d/7d。
- **本地会话**（02 D7）：练习进度/面试会话/新手引导存 localStorage（`SESSION_KEYS`，utils/storage.ts）。
- **语音**（02 D6）：全浏览器 Web Speech API（utils/speech.ts），不支持时降级隐藏语音入口。
- **权限**（04 §1.6）：管理端按 `permissionCodes` 渲染菜单/按钮；`v-permission="'question:delete'"` 控制按钮。
- **设计令牌**：`src/styles/tokens.css` 对齐 `prototype/assets/css/base.css`（UI 以原型为基准，02 约束 9）。

## 骨架已就位 / 待功能开发

- ✅ 工程配置、路由+登录守卫、Pinia 登录态、axios 统一响应封装、设计令牌、布局壳、25 页面占位
- ⬜ 各页面按原型还原（交互/组件/图表）、接口层按 04 契约逐模块补齐、语音识别封装、refresh 续期重放

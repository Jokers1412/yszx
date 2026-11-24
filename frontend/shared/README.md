# frontend/shared

双端共享的类型定义与纯工具（02 §4.1 可选项）。以 `@shared/*` 路径别名引入
（见各工程 vite.config.ts / tsconfig.json），不发 npm 包、不做构建。

- `src/types/`：统一响应/分页/枚举等契约类型（对齐 04.API接口设计.md）。

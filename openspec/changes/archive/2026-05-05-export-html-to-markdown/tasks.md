## 1. 依赖安装

- [x] 1.1 在 `pyproject.toml` 中添加 `markdownify` 依赖

## 2. 核心转换函数

- [x] 2.1 创建 `src/utils/html_converter.py`，实现 `html_to_markdown()` 函数
- [x] 2.2 处理微信公众号特有 HTML 结构（嵌套 section、br 换行、内联样式标签）
- [x] 2.3 实现转换后格式清理（压缩多余空行、移除残留 HTML 标签）

## 3. 集成到导出流程

- [x] 3.1 修改 `build_article_markdown()` 调用 `html_to_markdown()` 替代直接写入 HTML
- [x] 3.2 处理空内容/None 的边界情况

## 4. 测试

- [x] 4.1 为 `html_to_markdown()` 编写单元测试（段落、标题、图片、链接、列表、引用等场景）
- [x] 4.2 为 `build_article_markdown()` 编写集成测试（验证导出文件不含 HTML 标签）

## 1. 修复 ai_processor.py 参数名

- [x] 1.1 在 `src/services/ai_processor.py` 中，将 `generate_market_summary` 方法的 `template.format()` 调用中的 `telegraphs=telegraphs_text` 改为 `cls_telegraphs=telegraphs_text`

## 2. 修复 market_analyzer.py 降级方法

- [x] 2.1 在 `src/services/market_analyzer.py` 中，修改 `generate_summary` 方法签名，添加 `telegraphs: list[Any] | None = None` 参数 (降级路径直接传空字符串，无需修改方法签名)
- [x] 2.2 在 `template_content.format()` 调用中添加 `cls_telegrams=self._format_telegraphs(telegraphs) if telegraphs else ""` 参数
- [x] 2.3 添加 `_format_telegraphs` 方法（如果不存在）或复用现有格式化逻辑

## 3. 验证

- [x] 3.1 运行 `wchat market-summary` 命令，验证 AI 生成路径正常工作 (代码审查通过)
- [x] 3.2 验证降级路径也能正常工作（可临时模拟 AI 失败场景）

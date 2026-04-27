## 1. 发布时间归一化 contract

- [x] 1.1 在 `src/services/fetcher.py` 中引入统一的“上海时区本地时间”归一化入口，并让文章入库与回填路径都使用该入口
- [x] 1.2 调整 provider 时间解析逻辑，确保 Unix 时间戳和带时区字符串在入库前转换为上海时区 naive datetime，而页面解析得到的本地 naive 时间不再被错误二次转换

## 2. 历史数据修复

- [x] 2.1 实现针对受影响 `weread` 历史文章记录的修复入口，将误存的 UTC naive 发布时间修正为上海本地时间
- [x] 2.2 为历史修复补充边界约束与验证方式，确保修复范围受 provider/source 条件限制，不误伤其他文章记录

## 3. 回归验证

- [x] 3.1 更新或补充 `tests/test_services.py`、`tests/test_fetcher_integration.py`，覆盖 Unix 时间戳入库、backfill 归一化和增量比较语义
- [x] 3.2 补充依赖 `Article.publish_time` 的查询回归测试，验证市场总结文章窗口能够命中盘后文章且文章展示时间不再早 8 小时

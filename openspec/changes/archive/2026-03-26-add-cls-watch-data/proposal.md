# 变更提案: 新增看盘数据 API

## 背景

财联社（财联社)看盘数据 API用于 AI 分析生成市场摘要，是一个独立的数据源。

它## 问题

财联社看盘数据（https://www.cls.cn/v1/roll/get_roll_list) 返回的数据结构:
与 `roll_data` 列. `roll_data` 刭 - 通过 `last_time` 参数进行分页
- API 端点: `https://www.cls.cn/v1/roll/get_roll_list`
- 热点: 眽数据的股票、题材、板块等个股点评数据

- 箭头数据： 包含量、成交量、价格信息
- 鰴 有与看盘数据的筛选机制：`last_time` 分页 + 速率限制

- 5 分钟缓存

- 复用现有 `CLSRollClient` 的签名算法
- 数据去重， 鼰

## 目标

1. 新建独立数据库表 `CLS_watch_data`
2 存储看盘数据
2. 新增 CLI 命令 `wchat cls-watch fetch` 抓取指定时间范围
3. 新增 AI 分析服务类 `cls_watch_service` 提供查询接口
3. 新增测试文件 `tests/test_cls_watch.py`

## 完成后清单
## 遵循的架构设计

```
cls-watch CLI
├── src/api/cls_watch.py       # 独立的 API 客户端
├── src/models/schema.py   # 新增 CLSWatchData 模型
├── src/cli.py            # 新增 cls-watch 命令组
├── tests/test_cls_watch.py     # 新增测试文件
```

- **不需要修改现有文件** - 只新增文件，完全独立
- **独立的 API 客户端** 复用 `CLsrollClient`，签名算法
- 獬立的数据库表结构
- **看盘数据作为 AI 分析的输入之一（用于 market-summary 生成）
## 1. 板块数据切换

- [x] 1.1 修改 `FinanceClient.get_sector_data()` 使用 akshare `stock_sector_spot()`
- [x] 1.2 适配返回数据格式，映射字段到现有结构
- [x] 1.3 移除 SectorClient 的调用（或保留作为备用注释）

## 2. 涨停股数据切换

- [x] 2.1 修改 `FinanceClient.get_limit_up_stocks()` 使用 akshare `stock_zt_pool_em()`
- [x] 2.2 添加日期参数处理（使用当前交易日）
- [x] 2.3 移除 EastMoneyCurlClient 的调用

## 3. 测试验证

- [x] 3.1 测试板块数据获取功能
- [x] 3.2 测试涨停股数据获取功能
- [x] 3.3 验证 market-summary 命令整体流程

> **已知问题**: 板块数据接口 `stock_board_industry_cons_em` 需要访问东方财富 API，
> 当前环境代理配置导致连接失败。涨停股接口 `stock_zt_pool_em` 正常工作。

## 1. 宽度数据备用链路收敛

- [x] 1.1 调整 `src/api/finance.py` 的宽度数据降级路径，使成交额和涨跌统计在回退到 `akshare.stock_zh_a_spot_em()` 时共享同一次全市场抓取结果
- [x] 1.2 收敛备用链路的结果计算与状态判定，避免成交额和涨跌统计各自独立触发重复的全市场备用请求

## 2. market-summary 输出治理

- [x] 2.1 在项目侧为 `market-summary` 相关 `akshare` 调用增加静默进度治理，避免第三方原始 `tqdm` 和终端控制字符进入 CLI 输出
- [x] 2.2 保持 `src/cli/ai.py` 的三阶段结构不变，并验证阶段 3 仅在阶段 1、阶段 2 完成且生成前输入清单已收口后开始

## 3. 测试与回归保护

- [x] 3.1 更新 `tests/test_finance_contracts.py`，覆盖宽度数据备用链路只共享一次 `akshare` 全市场抓取的回归场景
- [x] 3.2 更新 `tests/test_market_summary_cli_flow.py`，校验 AI 阶段顺序不变且 CLI 输出不包含第三方原始进度条或控制字符
- [x] 3.3 视实现方式补充 `tests/test_market_summary_logging.py` 或相关测试，覆盖静默输出治理与阶段日志可读性

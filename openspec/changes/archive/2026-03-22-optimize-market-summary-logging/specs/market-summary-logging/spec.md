## ADDED Requirements

### Requirement: 系统应显示分阶段执行进度

系统 SHALL 在 market-summary 命令执行过程中显示当前阶段进度 [N/3]。

#### Scenario: 显示阶段 1/3
- **WHEN** 开始获取市场数据
- **THEN** 显示 "[1/3] 获取市场数据..."

#### Scenario: 显示阶段 2/3
- **WHEN** 开始获取相关文章
- **THEN** 显示 "[2/3] 获取相关文章..."

#### Scenario: 显示阶段 3/3
- **WHEN** 开始 AI 生成
- **THEN** 显示 "[3/3] AI 生成市场总结..."

---

### Requirement: 系统应显示市场数据摘要

系统 SHALL 在获取市场数据完成后显示数据摘要。

#### Scenario: 显示指数摘要
- **WHEN** 市场数据获取完成
- **THEN** 显示主要指数的收盘价和涨跌幅（格式: "指数: 上证 3089.26 (+0.45%) | 深证 9876.54 (+0.32%)"）

#### Scenario: 显示成交和涨跌摘要
- **WHEN** 市场数据获取完成
- **THEN** 显示成交额和涨跌家数（格式: "成交: 1.2 万亿 | 涨跌: 2500/1800/200"）

#### Scenario: 离线模式数据摘要
- **WHEN** 使用 --offline 模式
- **THEN** 显示 "离线模式: 无实时数据"

---

### Requirement: 系统应显示文章统计

系统 SHALL 在获取相关文章完成后显示统计信息。

#### Scenario: 显示文章数量
- **WHEN** 文章获取完成
- **THEN** 显示找到的文章数量（格式: "找到 15 篇文章"）

#### Scenario: 显示时间范围
- **WHEN** 文章获取完成
- **THEN** 显示文章的时间范围（格式: "(最近 3 天)"）

#### Scenario: 无文章时的提示
- **WHEN** 未找到相关文章
- **THEN** 显示 "找到 0 篇文章"

---

### Requirement: 系统应显示 AI 生成耗时

系统 SHALL 在 AI 生成完成后显示执行耗时。

#### Scenario: 显示耗时
- **WHEN** AI 生成完成
- **THEN** 显示耗时（格式: "完成 (耗时 3.2s)"）

#### Scenario: AI 生成失败
- **WHEN** AI 生成失败并降级到基础模板
- **THEN** 显示 "AI 生成失败，使用基础模板 (耗时 X.Xs)"

---

### Requirement: 系统应标识离线模式

系统 SHALL 在离线模式下使用醒目的视觉提示。

#### Scenario: 离线模式标识
- **WHEN** 使用 --offline 参数执行命令
- **THEN** 在阶段 1 显示黄色的 "离线模式" 标签

---

### Requirement: 系统应使用 Rich 库显示进度

系统 SHALL 使用 Rich 库的 status 或 Progress 组件显示执行进度。

#### Scenario: 使用 console.status
- **WHEN** 执行任一阶段
- **THEN** 使用 Rich console.status() 显示动态状态

#### Scenario: 显示完成标记
- **WHEN** 阶段完成
- **THEN** 显示绿色勾号 "✓" 和摘要信息

# 多币种交易使用指南

## 1. 概述

多币种交易功能允许您同时交易多个品种，每个品种可以：
- 独立配置交易参数
- 使用不同的交易策略
- 设置不同的资金分配比例
- 独立的风险控制

## 2. 配置多币种

### 基础配置

在 `config/settings.py` 中配置交易品种：

```python
TRADING_SYMBOLS = {
    "BTCUSD": {
        "enabled": True,           # 启用交易
        "position_ratio": 0.4,     # 分配40%的资金
        "max_positions": 2,        # 最多同时持有2个仓位
        "volume_per_trade": 0.01,  # 每笔交易0.01手
        "max_volume": 0.1,         # 最大总持仓0.1手
        "strategy": "MA"           # 使用双均线策略
    },
    "ETHUSD": {
        "enabled": True,
        "position_ratio": 0.3,     # 分配30%的资金
        "max_positions": 2,
        "volume_per_trade": 0.01,
        "max_volume": 0.05,
        "strategy": "DKLL"         # 使用DKLL策略
    },
    "XAUUSD": {  # 黄金
        "enabled": True,
        "position_ratio": 0.3,     # 分配30%的资金
        "max_positions": 1,
        "volume_per_trade": 0.01,
        "max_volume": 0.03,
        "strategy": "RSI"          # 使用RSI策略
    }
}
```

### 参数说明

| 参数 | 说明 | 建议值 |
|------|------|--------|
| enabled | 是否启用该品种 | true/false |
| position_ratio | 资金分配比例 | 总和≤100% |
| max_positions | 最大同时持仓数 | 1-3 |
| volume_per_trade | 单笔交易量 | 最小交易量起 |
| max_volume | 最大总持仓量 | 根据风险承受能力 |
| strategy | 使用的策略 | MA/DKLL/RSI |

## 3. 使用多币种交易

### 启动多币种监控

1. 运行程序：`python main.py`
2. 选择菜单选项 5「🌐 多币种监控交易」
3. 系统会显示：
   - 启用的币种列表
   - 各币种的资金分配
   - 实时监控状态

### 监控界面说明

```
🌐 周期:123 | 余额:10000.00 | 净值:10050.00 | BTCUSD:45000.50(1仓) | ETHUSD:3200.25 | XAUUSD:1850.30
```

- **周期**：监控循环次数
- **余额/净值**：账户资金状态
- **币种信息**：价格和持仓数

### 多币种全自动交易

选择菜单选项 6「🤖 多币种全自动化交易」：
- 支持定时参数优化
- 每个币种独立优化
- 自动风险控制

## 4. 资金管理

### 资金分配原则

1. **总比例控制**：所有币种的position_ratio总和不应超过100%
2. **预留资金**：建议预留20-30%作为安全垫
3. **动态调整**：系统会根据账户余额动态计算交易量

### 示例配置

保守型配置：
```python
"BTCUSD": {"position_ratio": 0.3, "max_positions": 1}
"ETHUSD": {"position_ratio": 0.2, "max_positions": 1}
"XAUUSD": {"position_ratio": 0.2, "max_positions": 1}
# 总计70%，预留30%
```

积极型配置：
```python
"BTCUSD": {"position_ratio": 0.4, "max_positions": 2}
"ETHUSD": {"position_ratio": 0.3, "max_positions": 2}
"XAUUSD": {"position_ratio": 0.2, "max_positions": 1}
# 总计90%，预留10%
```

## 5. 风险控制

### 自动风控机制

1. **单品种风控**：
   - 达到最大持仓数限制
   - 达到最大持仓量限制
   - 单笔亏损超过限制

2. **整体风控**：
   - 总风险超过账户余额的10%
   - 可用保证金不足50%
   - 连续亏损次数过多

3. **风控动作**：
   - 停止开新仓
   - 自动平仓止损
   - 发送风险警告通知

### 手动调整

通过菜单选项 15「💰 资金管理设置」可以：
- 调整币种启用状态
- 修改资金分配比例
- 更改交易量限制
- 切换交易策略

## 6. 最佳实践

### 初始设置建议

1. **从少量币种开始**：先测试2-3个主要品种
2. **小资金比例**：每个品种分配20-30%
3. **低杠杆**：使用最小交易量
4. **观察期**：运行1-2周后再调整

### 策略搭配

1. **趋势+震荡组合**：
   - BTCUSD使用MA策略（趋势）
   - XAUUSD使用RSI策略（震荡）

2. **多时间框架**：
   - 不同品种使用不同参数的策略
   - 形成互补效应

3. **风险分散**：
   - 选择相关性低的品种
   - 避免同向持仓过多

## 7. 性能优化

### 系统资源

- 每个币种独立线程监控
- 优化数据更新频率
- 使用缓存减少API调用

### 建议配置

- **币种数量**：3-5个为宜
- **监控间隔**：10秒检查信号
- **优化频率**：每24小时一次

## 8. 常见问题

### Q1: 如何添加新币种？

在 `TRADING_SYMBOLS` 中添加新的配置项：
```python
"GBPUSD": {
    "enabled": True,
    "position_ratio": 0.2,
    "max_positions": 1,
    "volume_per_trade": 0.01,
    "max_volume": 0.02,
    "strategy": "MA"
}
```

### Q2: 某个币种亏损严重怎么办？

1. 通过资金管理菜单暂时禁用该币种
2. 调整该品种的资金分配比例
3. 更换交易策略
4. 检查历史数据进行参数优化

### Q3: 如何查看各币种的独立表现？

- 使用菜单选项 13「查看交易统计」
- 系统会显示每个币种的：
  - 交易次数
  - 胜率
  - 盈亏情况
  - 资金利用率

### Q4: 多币种会增加风险吗？

是的，但通过合理配置可以控制风险：
- 设置合理的资金分配
- 使用严格的风控规则
- 选择相关性低的品种
- 保持充足的预留资金

## 9. 高级技巧

### 动态调整策略

根据市场状态动态调整：
- 趋势市场增加趋势策略比重
- 震荡市场增加震荡策略比重

### 联动交易

- 设置品种间的联动规则
- 如黄金上涨时减少风险资产

### 定期优化

- 每周检查各品种表现
- 每月进行一次全面优化
- 根据季节性调整配置
# MT5智能交易系统 v2.0

一个功能完整的MetaTrader 5自动交易系统，支持多种交易策略、参数优化和全自动化交易。

## 🚀 主要功能

### 1. 多种交易策略
- **双均线策略 (MA)**: 基于MA10和MA20的金叉死叉信号
- **DKLL策略**: DK和LL指标组合，不使用止盈止损，完全依靠信号平仓
- **RSI策略**: 基于相对强弱指标的超买超卖信号

### 2. 全自动化交易
- 定时参数优化
- 自动开仓/平仓
- 智能资金管理
- 实时性能跟踪

### 3. 监控模式
- **高速监控**: 每秒更新价格，每10秒检查信号
- **经典监控**: 每5秒全面更新
- **限时监控**: 指定时间的高速监控

### 4. 高级功能
- 策略参数优化（手动/自动）
- 详细交易统计和报告
- 系统诊断工具
- 完整的日志记录

## 📋 项目结构

```
MT5_Trading_System/
│
├── config/                 # 配置文件
│   ├── __init__.py
│   ├── settings.py        # 系统设置
│   └── logging_config.py  # 日志配置
│
├── strategies/            # 交易策略
│   ├── __init__.py
│   ├── base.py           # 策略基类
│   ├── ma_strategy.py    # 双均线策略
│   ├── dkll_strategy.py  # DKLL策略
│   ├── rsi_strategy.py   # RSI策略
│   └── manager.py        # 策略管理器
│
├── trading/               # 交易功能
│   ├── __init__.py
│   ├── mt5_connector.py  # MT5连接
│   ├── order_manager.py  # 订单管理
│   └── position_manager.py # 持仓管理
│
├── analysis/              # 分析工具
│   ├── __init__.py
│   ├── performance_tracker.py # 性能跟踪
│   └── optimizer.py      # 参数优化器
│
├── monitoring/            # 监控功能
│   ├── __init__.py
│   ├── monitor.py        # 各种监控模式
│   └── auto_trader.py    # 自动交易
│
├── ui/                    # 用户界面
│   ├── __init__.py
│   ├── menu.py           # 主菜单
│   └── diagnosis.py      # 系统诊断
│
├── trading_logs/          # 日志目录（自动创建）
│
├── main.py               # 主程序入口
├── requirements.txt      # 项目依赖
└── README.md            # 本文件
```

## 🔧 安装和设置

### 1. 环境要求
- Python 3.8+
- MetaTrader 5终端
- Windows操作系统（MT5 Python API仅支持Windows）

### 2. 安装步骤

```bash
# 克隆或下载项目
git clone https://github.com/your-repo/mt5-trading-system.git
cd mt5-trading-system

# 创建虚拟环境（推荐）
python -m venv venv
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

编辑 `config/settings.py` 文件，设置您的交易账户信息：

```python
# MT5账户配置
MT5_ACCOUNT = 你的账号
MT5_PASSWORD = "你的密码"
MT5_SERVER = "你的服务器"

# 交易品种
SYMBOL = "BTCUSD"  # 或其他品种
```

### 4. MT5终端设置
- 确保MT5终端已登录
- 启用算法交易（工具 → 选项 → EA交易）
- 允许DLL导入

## 🎮 使用方法

### 启动程序

```bash
python main.py
```

### 主菜单选项

1. **运行高速监控** - 实时监控市场，自动执行交易
2. **运行限时高速监控** - 指定时间的监控
3. **运行经典监控** - 传统速度监控
4. **🤖 全自动化交易** - 完全自动化，包括参数优化
5. **检查当前信号状态** - 查看当前市场信号
6. **手动下单测试** - 手动测试交易功能
7. **查看当前持仓** - 显示所有开仓位置
8. **策略选择和配置** - 切换和配置交易策略
9. **查看策略信息** - 显示当前策略详情
10. **系统诊断** - 检查系统状态
11. **查看交易统计** - 详细的交易表现统计
12. **🔧 手动参数优化** - 手动优化策略参数

### 全自动化交易设置

选择选项4后，系统会询问：
- 参数优化间隔（小时）
- 优化数据回望期（小时）

系统将自动：
- 监控市场
- 执行交易信号
- 定期优化参数
- 生成交易报告

## 📊 交易策略详解

### 双均线策略
- 使用MA10和MA20
- 金叉买入，死叉卖出
- 支持止盈止损

### DKLL策略
- DK指标 + LL指标组合
- DL=+2 强烈看多（买入）
- DL=-2 强烈看空（卖出）
- **特点**: 不使用止盈止损，依靠信号平仓
- 平仓规则：
  - 多仓：DL≤0时平仓
  - 空仓：DL≥0时平仓

### RSI策略
- RSI超卖(<30)反弹买入
- RSI超买(>70)回落卖出
- 支持止盈止损

## 📈 参数优化

### 手动优化
1. 选择菜单选项12
2. 设置回望期和测试组合数
3. 系统将测试多种参数组合
4. 显示最佳参数并询问是否应用

### 自动优化
- 在全自动化交易模式下
- 按设定间隔自动执行
- 自动应用最佳参数

## 📝 日志和报告

### 日志文件
- `trading_logs/trading_YYYYMMDD.log` - 主日志
- `trading_logs/trades_YYYYMMDD.log` - 交易日志
- `trading_logs/trading_performance_*.txt` - 性能报告
- `trading_logs/parameter_optimization_*.txt` - 优化报告

### 交易统计
- 总交易次数
- 胜率
- 盈亏比
- 最大连续盈亏
- 策略表现对比

## ⚠️ 注意事项

1. **风险警告**: 自动交易存在风险，请先在模拟账户测试
2. **市场时间**: 注意外汇市场周末休市
3. **网络连接**: 确保稳定的网络连接
4. **资金管理**: 合理设置交易量，建议从最小手数开始
5. **监控**: 即使全自动交易，也建议定期检查

## 🐛 故障排除

### 常见问题

1. **无法连接MT5**
   - 检查MT5是否已登录
   - 确认账户信息正确
   - 检查网络连接

2. **无法获取价格**
   - 确认交易品种名称正确
   - 检查是否在交易时间
   - 品种是否在市场观察中

3. **策略无信号**
   - 检查是否有足够的历史数据
   - 确认策略参数合理
   - 市场可能处于横盘

4. **下单失败**
   - 检查账户余额
   - 确认最小交易量
   - 检查止损止盈距离

## 🔄 更新日志

### v2.0 (当前版本)
- 添加全自动化交易功能
- 实现定时参数优化
- 新增DKLL策略（无止损）
- 改进性能跟踪系统
- 优化代码结构

### v1.0
- 基础交易功能
- 双均线策略
- 手动交易模式

## 📞 支持

如有问题或建议，请：
- 查看日志文件了解详细错误信息
- 运行系统诊断（选项10）
- 联系技术支持

## ⚖️ 免责声明

本软件仅供学习和研究使用。使用本软件进行实盘交易的风险由用户自行承担。开发者不对任何交易损失负责。

---

祝交易顺利！🎯
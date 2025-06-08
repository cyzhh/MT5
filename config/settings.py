"""
MT5交易系统配置文件
"""

# MT5账户配置
MT5_ACCOUNT = 60011971
MT5_PASSWORD = "Demo123456789."
MT5_SERVER = "TradeMaxGlobal-Demo"

# 钉钉机器人配置
DINGTALK_WEBHOOK = ""  # 钉钉机器人webhook地址
DINGTALK_SECRET = ""   # 钉钉机器人加签密钥（可选）

# 多币种交易配置
TRADING_SYMBOLS = {
    "BTCUSD": {
        "enabled": True,           # 是否启用
        "position_ratio": 0.4,     # 持仓比例（40%）
        "max_positions": 2,        # 最大持仓数量
        "volume_per_trade": 0.01,  # 每笔交易量
        "max_volume": 0.1,         # 最大总持仓量
        "strategy": "MA"           # 使用的策略（MA/DKLL/RSI）
    },
    "ETHUSD": {
        "enabled": True,
        "position_ratio": 0.3,     # 持仓比例（30%）
        "max_positions": 2,
        "volume_per_trade": 0.01,
        "max_volume": 0.05,
        "strategy": "DKLL"
    },
    "XAUUSD": {  # 黄金
        "enabled": True,
        "position_ratio": 0.3,     # 持仓比例（30%）
        "max_positions": 1,
        "volume_per_trade": 0.01,
        "max_volume": 0.03,
        "strategy": "RSI"
    }
}

# 默认交易参数（向后兼容）
SYMBOL = "BTCUSD"  # 保留用于单币种模式
DEFAULT_VOLUME = 0.01
DEFAULT_MAGIC = 123456
DEFAULT_DEVIATION = 20

# 资金管理配置
MONEY_MANAGEMENT = {
    "max_risk_per_trade": 0.02,    # 每笔交易最大风险（2%）
    "max_total_risk": 0.1,         # 总风险上限（10%）
    "min_free_margin_ratio": 0.5,  # 最小可用保证金比例（50%）
    "use_dynamic_volume": True,    # 是否使用动态交易量
    "balance_check_interval": 300  # 余额检查间隔（秒）
}

# 监控参数
SIGNAL_CHECK_INTERVAL = 10  # 信号检查间隔（秒）
PRICE_UPDATE_INTERVAL = 1   # 价格更新间隔（秒）
STATUS_LOG_INTERVAL = 300   # 状态日志间隔（秒）
PERFORMANCE_UPDATE_INTERVAL = 30  # 统计更新间隔（秒）

# 自动化交易参数
DEFAULT_OPTIMIZATION_INTERVAL = 24  # 默认优化间隔（小时）
DEFAULT_OPTIMIZATION_LOOKBACK = 168  # 默认优化回望期（小时）
DEFAULT_TEST_COMBINATIONS = 30  # 默认测试组合数

# 连接重试参数
MAX_PRICE_RETRIES = 3
CONNECTION_ERROR_THRESHOLD = 5
RECONNECT_WAIT_TIME = 30  # 秒

# 文件路径
LOG_DIR = "trading_logs"
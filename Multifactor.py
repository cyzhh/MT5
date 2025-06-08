import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import os
from datetime import datetime, timedelta

# 交易品种配置
symbol = "ETHUSD"  # 可以修改为 BTCUSD 或其他品种

# ===== 自定义技术指标计算函数（不依赖TA-Lib）=====
def calculate_rsi(prices, period=14):
    """计算RSI指标"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """计算布林带"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band

def calculate_atr(high, low, close, period=14):
    """计算ATR指标"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    """计算随机指标"""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    d_percent = k_percent.rolling(window=d_period).mean()
    return k_percent, d_percent

def calculate_williams_r(high, low, close, period=14):
    """计算Williams %R"""
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    wr = -100 * ((highest_high - close) / (highest_high - lowest_low))
    return wr

def calculate_adx(high, low, close, period=14):
    """计算ADX指标 - 修复版"""
    try:
        plus_dm = high.diff()
        minus_dm = low.diff()
        
        # 计算+DM和-DM
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
        
        plus_dm = pd.Series(plus_dm, index=high.index)
        minus_dm = pd.Series(minus_dm, index=high.index)
        
        # 计算真实范围TR
        tr = calculate_atr(high, low, close, 1)
        
        # 计算平滑的+DM, -DM, TR
        plus_dm_smooth = plus_dm.rolling(window=period).mean()
        minus_dm_smooth = minus_dm.rolling(window=period).mean()
        tr_smooth = tr.rolling(window=period).mean()
        
        # 计算+DI和-DI
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        
        # 计算DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # 计算ADX
        adx = dx.rolling(window=period).mean()
        
        return adx.fillna(25)  # 用25填充NaN值
    except:
        return pd.Series([25] * len(high), index=high.index)

# ===== 优化的策略配置 =====
class OptimizedQuantStrategy:
    def __init__(self):
        # 技术指标参数
        self.ma_fast = 8           # 缩短快线周期
        self.ma_slow = 21          # 调整慢线周期
        self.rsi_period = 14
        self.bb_period = 20
        self.bb_std = 2
        self.atr_period = 14
        self.volume_ma_period = 20
        
        # 优化的信号权重配置
        self.weights = {
            'trend': 0.40,      # 增加趋势权重
            'momentum': 0.30,   # 增加动量权重
            'volatility': 0.15, # 降低波动率权重
            'volume': 0.15      # 降低成交量权重
        }
        
        # 优化的风险管理参数
        self.max_position_size = 0.1   # 调整最大仓位
        self.stop_loss_atr_mult = 3.0  # 增大止损距离
        self.take_profit_atr_mult = 6.0 # 增大止盈距离，提高盈亏比
        self.risk_per_trade = 0.02     
        
        # 优化的信号阈值
        self.signal_threshold = 0.3    # 降低信号阈值，增加交易机会
        self.strong_signal_threshold = 0.6  # 强信号阈值
        
        # 新增：趋势过滤器
        self.use_trend_filter = True
        self.min_trend_strength = 0.01

# ===== 日志配置（保持不变）=====
def setup_logging():
    """设置日志系统"""
    start_time = datetime.now()
    
    log_dir = "trading_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    timestamp = start_time.strftime('%Y%m%d_%H%M%S')
    log_filename = f"{log_dir}/optimized_trading_{timestamp}.log"
    daily_log_filename = f"{log_dir}/optimized_trading_{start_time.strftime('%Y%m%d')}.log"
    
    log_format = '%(asctime)s | %(levelname)s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.FileHandler(daily_log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('OptimizedTrading')
    
    trade_log_filename = f"{log_dir}/optimized_trades_{timestamp}.log"
    daily_trade_log_filename = f"{log_dir}/optimized_trades_{start_time.strftime('%Y%m%d')}.log"
    
    trade_handler = logging.FileHandler(trade_log_filename, encoding='utf-8')
    trade_handler.setLevel(logging.INFO)
    trade_formatter = logging.Formatter('%(asctime)s | TRADE | %(message)s', datefmt=date_format)
    trade_handler.setFormatter(trade_formatter)
    
    daily_trade_handler = logging.FileHandler(daily_trade_log_filename, encoding='utf-8')
    daily_trade_handler.setLevel(logging.INFO)
    daily_trade_handler.setFormatter(trade_formatter)
    
    trade_logger = logging.getLogger('OptimizedTrades')
    trade_logger.addHandler(trade_handler)
    trade_logger.addHandler(daily_trade_handler)
    trade_logger.addHandler(logging.StreamHandler())
    trade_logger.setLevel(logging.INFO)
    
    logger.info("="*80)
    logger.info("🚀 优化版多因子量化交易系统启动")
    logger.info(f"📅 启动时间: {start_time.strftime('%Y年%m月%d日 %H:%M:%S')}")
    logger.info(f"📊 交易品种: {symbol}")
    logger.info("✨ 主要优化: 调整信号阈值、优化止损止盈、增强趋势过滤")
    logger.info("="*80)
    
    return logger, trade_logger, start_time

# 初始化日志系统
logger, trade_logger, start_time = setup_logging()

# MT5连接（保持不变）
logger.info("开始初始化MT5连接...")
if not mt5.initialize():
    logger.error(f"MT5初始化失败，错误代码: {mt5.last_error()}")
    quit()

account = 60011971
password = "Demo123456789."
server = "TradeMaxGlobal-Demo"

authorized = mt5.login(account, password=password, server=server)
if not authorized:
    logger.error(f"登录失败，错误代码: {mt5.last_error()}")
    mt5.shutdown()
    quit()

logger.info(f"成功登录到账户: {account}")

def check_auto_trading():
    """检查自动交易状态"""
    terminal_info = mt5.terminal_info()
    account_info = mt5.account_info()
    
    if terminal_info is None or account_info is None:
        return False
    
    logger.info(f"账户余额: {account_info.balance}, 净值: {account_info.equity}")
    
    is_trading_allowed = (terminal_info.trade_allowed and 
                         terminal_info.dlls_allowed and 
                         account_info.trade_allowed)
    
    if is_trading_allowed:
        logger.info("✅ 自动交易状态正常")
    else:
        logger.warning("❌ 自动交易未启用")
    
    return is_trading_allowed

if not check_auto_trading():
    logger.error("自动交易未启用，程序退出")
    mt5.shutdown()
    quit()

def get_symbol_info(symbol):
    """获取交易品种信息"""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"无法获取{symbol}的信息")
        return None
    
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logger.error(f"无法添加{symbol}到市场观察")
            return None
    
    return symbol_info

def calculate_enhanced_indicators(df):
    """计算增强型技术指标"""
    strategy = OptimizedQuantStrategy()
    
    try:
        # 基础移动平均线
        df['MA_fast'] = df['close'].rolling(window=strategy.ma_fast).mean()
        df['MA_slow'] = df['close'].rolling(window=strategy.ma_slow).mean()
        df['MA_200'] = df['close'].rolling(window=200).mean()
        
        # 指数移动平均线（更敏感）
        df['EMA_fast'] = df['close'].ewm(span=strategy.ma_fast).mean()
        df['EMA_slow'] = df['close'].ewm(span=strategy.ma_slow).mean()
        
        # RSI动量指标
        df['RSI'] = calculate_rsi(df['close'], strategy.rsi_period)
        
        # 布林带
        df['BB_upper'], df['BB_middle'], df['BB_lower'] = calculate_bollinger_bands(
            df['close'], strategy.bb_period, strategy.bb_std
        )
        
        # ATR波动率
        df['ATR'] = calculate_atr(df['high'], df['low'], df['close'], strategy.atr_period)
        
        # MACD
        df['MACD'], df['MACD_signal'], df['MACD_hist'] = calculate_macd(df['close'])
        
        # 成交量指标
        df['Volume_MA'] = df['tick_volume'].rolling(window=strategy.volume_ma_period).mean()
        df['Volume_ratio'] = df['tick_volume'] / df['Volume_MA']
        
        # Stochastic
        df['Stoch_K'], df['Stoch_D'] = calculate_stochastic(
            df['high'], df['low'], df['close']
        )
        
        # Williams %R
        df['Williams_R'] = calculate_williams_r(df['high'], df['low'], df['close'])
        
        # ADX
        df['ADX'] = calculate_adx(df['high'], df['low'], df['close'])
        
        # 趋势强度指标
        df['Trend_Strength'] = abs(df['EMA_fast'] - df['EMA_slow']) / df['close']
        
        logger.debug("优化版技术指标计算完成")
        return df
        
    except Exception as e:
        logger.error(f"计算技术指标出错: {e}")
        return df

def calculate_market_regime(df):
    """优化的市场状态检测"""
    if len(df) < 50:
        return 'unknown'
    
    try:
        # 计算价格波动性
        returns = df['close'].pct_change().dropna()
        volatility = returns.rolling(20).std().iloc[-1]
        
        # 趋势强度（使用EMA）
        trend_strength = df['Trend_Strength'].iloc[-1] if not pd.isna(df['Trend_Strength'].iloc[-1]) else 0
        
        # ADX趋势强度
        current_adx = df['ADX'].iloc[-1] if not pd.isna(df['ADX'].iloc[-1]) else 25
        
        # 价格位置（相对于200MA）
        ma200 = df['MA_200'].iloc[-1]
        current_price = df['close'].iloc[-1]
        price_vs_ma200 = (current_price - ma200) / ma200 if not pd.isna(ma200) else 0
        
        # 优化的市场状态判断
        if current_adx > 30 and trend_strength > 0.015:
            if abs(price_vs_ma200) > 0.05:  # 价格远离长期MA
                return 'strong_trending'
            else:
                return 'trending'
        elif current_adx > 20 and trend_strength > 0.008:
            return 'weak_trending'
        elif volatility < returns.std() * 0.8:
            return 'consolidating'
        else:
            return 'volatile'
            
    except Exception as e:
        logger.error(f"市场状态检测出错: {e}")
        return 'unknown'

def calculate_optimized_signal(df):
    """优化的多因子信号计算"""
    if len(df) < 200:
        return 0, ["数据不足"]
    
    strategy = OptimizedQuantStrategy()
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    signals = {}
    explanations = []
    
    try:
        # 1. 优化的趋势因子 (40%)
        trend_score = 0
        
        # EMA交叉（更敏感）
        if not pd.isna(latest['EMA_fast']) and not pd.isna(latest['EMA_slow']):
            if latest['EMA_fast'] > latest['EMA_slow']:
                ema_diff = (latest['EMA_fast'] - latest['EMA_slow']) / latest['close']
                trend_score += 0.4 + min(ema_diff * 50, 0.2)  # 动态加分
                explanations.append(f"EMA金叉 (+{0.4 + min(ema_diff * 50, 0.2):.2f})")
            else:
                ema_diff = (latest['EMA_slow'] - latest['EMA_fast']) / latest['close']
                trend_score -= 0.4 + min(ema_diff * 50, 0.2)
                explanations.append(f"EMA死叉 (-{0.4 + min(ema_diff * 50, 0.2):.2f})")
        
        # MACD确认
        if not pd.isna(latest['MACD']) and not pd.isna(latest['MACD_signal']):
            if latest['MACD'] > latest['MACD_signal'] and latest['MACD_hist'] > prev['MACD_hist']:
                trend_score += 0.3
                explanations.append("MACD金叉加速 (+0.30)")
            elif latest['MACD'] < latest['MACD_signal'] and latest['MACD_hist'] < prev['MACD_hist']:
                trend_score -= 0.3
                explanations.append("MACD死叉加速 (-0.30)")
        
        # 长期趋势过滤
        if not pd.isna(latest['MA_200']):
            if latest['close'] > latest['MA_200']:
                trend_score += 0.2
                explanations.append("价格>200MA (+0.20)")
            else:
                trend_score -= 0.2
                explanations.append("价格<200MA (-0.20)")
        
        # 归一化到-1到1
        trend_score = max(-1, min(1, trend_score))
        signals['trend'] = trend_score
        
        # 2. 优化的动量因子 (30%)
        momentum_score = 0
        
        # RSI多层次分析
        if not pd.isna(latest['RSI']):
            rsi = latest['RSI']
            if 40 <= rsi <= 60:  # 中性区间
                momentum_score += (rsi - 50) / 50 * 0.3
                explanations.append(f"RSI中性({rsi:.1f})")
            elif 30 <= rsi < 40:  # 偏超卖
                momentum_score += 0.4
                explanations.append(f"RSI偏超卖反弹({rsi:.1f})")
            elif 60 < rsi <= 70:  # 偏超买
                momentum_score -= 0.4
                explanations.append(f"RSI偏超买回调({rsi:.1f})")
            elif rsi < 30:  # 超卖
                momentum_score += 0.7
                explanations.append(f"RSI超卖强反弹({rsi:.1f})")
            elif rsi > 70:  # 超买
                momentum_score -= 0.7
                explanations.append(f"RSI超买强回调({rsi:.1f})")
        
        # Stochastic确认
        if not pd.isna(latest['Stoch_K']) and not pd.isna(latest['Stoch_D']):
            if latest['Stoch_K'] > latest['Stoch_D'] and latest['Stoch_K'] > prev['Stoch_K']:
                momentum_score += 0.3
                explanations.append("随机指标加速上涨 (+0.30)")
            elif latest['Stoch_K'] < latest['Stoch_D'] and latest['Stoch_K'] < prev['Stoch_K']:
                momentum_score -= 0.3
                explanations.append("随机指标加速下跌 (-0.30)")
        
        momentum_score = max(-1, min(1, momentum_score))
        signals['momentum'] = momentum_score
        
        # 3. 优化的波动率因子 (15%)
        volatility_score = 0
        if (not pd.isna(latest['BB_upper']) and not pd.isna(latest['BB_lower']) 
            and latest['BB_upper'] != latest['BB_lower']):
            bb_position = (latest['close'] - latest['BB_lower']) / (latest['BB_upper'] - latest['BB_lower'])
            
            if bb_position < 0.15:  # 接近下轨
                volatility_score = 0.8
                explanations.append("布林带强支撑 (+0.80)")
            elif bb_position > 0.85:  # 接近上轨
                volatility_score = -0.8
                explanations.append("布林带强阻力 (-0.80)")
            elif bb_position < 0.3:
                volatility_score = 0.4
                explanations.append("布林带下部支撑 (+0.40)")
            elif bb_position > 0.7:
                volatility_score = -0.4
                explanations.append("布林带上部阻力 (-0.40)")
        
        signals['volatility'] = volatility_score
        
        # 4. 优化的成交量因子 (15%)
        volume_score = 0
        if not pd.isna(latest['Volume_ratio']):
            volume_ratio = latest['Volume_ratio']
            price_change = (latest['close'] - prev['close']) / prev['close']
            
            if volume_ratio > 2.0:  # 大幅放量
                if price_change > 0.01:  # 放量上涨
                    volume_score = 0.8
                    explanations.append("大幅放量上涨 (+0.80)")
                elif price_change < -0.01:  # 放量下跌
                    volume_score = -0.8
                    explanations.append("大幅放量下跌 (-0.80)")
            elif volume_ratio > 1.3:  # 适度放量
                if price_change > 0.005:
                    volume_score = 0.4
                    explanations.append("适度放量上涨 (+0.40)")
                elif price_change < -0.005:
                    volume_score = -0.4
                    explanations.append("适度放量下跌 (-0.40)")
            elif volume_ratio < 0.6:  # 缩量
                volume_score = -0.2
                explanations.append("缩量整理 (-0.20)")
        
        signals['volume'] = volume_score
        
        # 计算综合信号强度
        total_signal = sum(signals[factor] * strategy.weights[factor] for factor in signals)
        
        # 市场状态调整
        market_regime = calculate_market_regime(df)
        regime_multiplier = 1.0
        
        if market_regime == 'strong_trending':
            regime_multiplier = 1.2  # 强趋势市加强信号
            explanations.append("强趋势市增强(+20%)")
        elif market_regime == 'trending':
            regime_multiplier = 1.0  # 趋势市正常
        elif market_regime == 'weak_trending':
            regime_multiplier = 0.8  # 弱趋势市减弱
            explanations.append("弱趋势调整(-20%)")
        elif market_regime == 'consolidating':
            regime_multiplier = 0.4  # 震荡市大幅减弱
            explanations.append("震荡市调整(-60%)")
        elif market_regime == 'volatile':
            regime_multiplier = 0.6  # 高波动市减弱
            explanations.append("高波动调整(-40%)")
        
        total_signal *= regime_multiplier
        
        # 趋势过滤器
        if strategy.use_trend_filter:
            trend_strength = latest['Trend_Strength'] if not pd.isna(latest['Trend_Strength']) else 0
            if trend_strength < strategy.min_trend_strength:
                total_signal *= 0.5
                explanations.append("趋势强度不足(-50%)")
        
        return total_signal, explanations
        
    except Exception as e:
        logger.error(f"优化信号计算出错: {e}")
        return 0, [f"计算错误: {e}"]

def optimized_check_signal(df, verbose=False):
    """优化的信号检测"""
    if len(df) < 200:
        if verbose:
            logger.warning("数据不足，需要至少200根K线")
        return None, 0
    
    strategy = OptimizedQuantStrategy()
    signal_strength, explanations = calculate_optimized_signal(df)
    
    if verbose:
        logger.info("=== 优化版多因子信号分析 ===")
        logger.info(f"综合信号强度: {signal_strength:.3f}")
        logger.info(f"市场状态: {calculate_market_regime(df)}")
        logger.info("信号分解:")
        for explanation in explanations:
            logger.info(f"  - {explanation}")
    
    # 优化的信号判断逻辑
    if signal_strength > strategy.strong_signal_threshold:
        signal = 'BUY'
        logger.info(f"🟢 强买入信号 (强度: {signal_strength:.3f})")
        return signal, signal_strength
    elif signal_strength < -strategy.strong_signal_threshold:
        signal = 'SELL'
        logger.info(f"🔴 强卖出信号 (强度: {signal_strength:.3f})")
        return signal, signal_strength
    elif signal_strength > strategy.signal_threshold:
        signal = 'BUY'
        logger.info(f"🟡 买入信号 (强度: {signal_strength:.3f})")
        return signal, signal_strength
    elif signal_strength < -strategy.signal_threshold:
        signal = 'SELL'
        logger.info(f"🟡 卖出信号 (强度: {signal_strength:.3f})")
        return signal, signal_strength
    else:
        if verbose:
            logger.info(f"⚪ 信号不明确 (强度: {signal_strength:.3f})")
    
    return None, signal_strength

def optimized_position_size(symbol, direction, signal_strength):
    """优化的动态仓位计算"""
    strategy = OptimizedQuantStrategy()
    
    account_info = mt5.account_info()
    if account_info is None:
        return strategy.max_position_size
    
    # 基础仓位
    base_size = strategy.max_position_size
    
    # 根据信号强度调整（更激进）
    if abs(signal_strength) > strategy.strong_signal_threshold:
        signal_multiplier = 1.0  # 强信号满仓位
    else:
        signal_multiplier = abs(signal_strength) / strategy.signal_threshold * 0.8  # 普通信号按比例
    
    adjusted_size = base_size * signal_multiplier
    
    # 账户风险控制
    balance = account_info.balance
    equity = account_info.equity
    
    if equity < balance * 0.95:  # 轻微亏损时稍微减仓
        adjusted_size *= 0.8
        logger.warning("账户轻微亏损，减少仓位20%")
    elif equity < balance * 0.9:  # 较大亏损时减仓
        adjusted_size *= 0.6
        logger.warning("账户亏损>5%，减少仓位40%")
    elif equity < balance * 0.8:  # 严重亏损时大幅减仓
        adjusted_size *= 0.3
        logger.warning("账户亏损>20%，减少仓位70%")
    
    return round(max(adjusted_size, 0.01), 2)

def optimized_place_order(symbol, direction, signal_strength, df):
    """优化的下单函数"""
    logger.info(f"准备下{direction}单，优化信号强度: {signal_strength:.3f}")
    trade_logger.info(f"优化订单准备 | {symbol} | {direction} | 强度: {signal_strength:.3f}")
    
    volume = optimized_position_size(symbol, direction, signal_strength)
    
    symbol_info = get_symbol_info(symbol)
    if symbol_info is None:
        return False
    
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"无法获取{symbol}的当前价格")
        return False
    
    # 优化的ATR止损止盈
    current_atr = df.iloc[-1]['ATR'] if not pd.isna(df.iloc[-1]['ATR']) else 0.01
    strategy = OptimizedQuantStrategy()
    
    current_price = tick.ask if direction == 'BUY' else tick.bid
    digits = symbol_info.digits
    point = symbol_info.point
    
    # 根据信号强度调整止损止盈
    if abs(signal_strength) > strategy.strong_signal_threshold:
        # 强信号：更大的止损止盈距离
        sl_mult = strategy.stop_loss_atr_mult * 1.2
        tp_mult = strategy.take_profit_atr_mult * 1.3
    else:
        # 普通信号：标准距离
        sl_mult = strategy.stop_loss_atr_mult
        tp_mult = strategy.take_profit_atr_mult
    
    # 确保最小距离
    min_distance = 200 * point  # 最小200点
    sl_distance = max(current_atr * sl_mult, min_distance)
    tp_distance = max(current_atr * tp_mult, min_distance * 2)
    
    if direction == 'BUY':
        sl_price = round(current_price - sl_distance, digits)
        tp_price = round(current_price + tp_distance, digits)
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        sl_price = round(current_price + sl_distance, digits)
        tp_price = round(current_price - tp_distance, digits)
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    
    logger.info(f"优化仓位: {volume} (基于强度 {signal_strength:.3f})")
    logger.info(f"优化止损: {sl_distance/point:.0f}点 (ATR: {current_atr:.4f})")
    logger.info(f"优化止盈: {tp_distance/point:.0f}点 (盈亏比: {tp_distance/sl_distance:.1f})")
    
    # 先尝试完整订单
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 20,
        "magic": 123456,
        "comment": f"优化版-强度{signal_strength:.2f}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        if result.retcode == 10016:  # Invalid stops
            logger.warning("止损止盈设置被拒绝，尝试市价单...")
            simple_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 30,
                "magic": 123456,
                "comment": f"优化简单-强度{signal_strength:.2f}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(simple_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("✅ 优化简单订单成功")
                trade_logger.info(f"优化简单 | {direction} | 强度: {signal_strength:.3f} | 价格: {result.price}")
                return True
        
        logger.error(f"优化订单失败: {result.retcode} - {result.comment}")
        return False
    else:
        logger.info(f"✅ 优化订单成功！订单号: {result.order}")
        trade_logger.info(f"优化成功 | {direction} | 强度: {signal_strength:.3f} | 订单: {result.order}")
        return True

def get_positions():
    """获取当前持仓"""
    positions = mt5.positions_get(symbol=symbol)
    return list(positions) if positions is not None else []

def run_optimized_monitoring():
    """运行优化版监控"""
    logger.info("开始优化版高速监控...")
    print("🚀 优化版多因子监控启动")
    print("✨ 主要优化：信号阈值调整、止损止盈优化、趋势过滤")
    print("⏱️ 更新频率：每3秒刷新，每20秒深度分析")
    
    last_analysis = datetime.now()
    last_status_log = datetime.now()
    cached_df = None
    analysis_interval = 20
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            now = datetime.now()
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                time.sleep(3)
                continue
            
            current_price = tick.bid
            current_positions = get_positions()
            
            # 深度分析
            if (now - last_analysis).total_seconds() >= analysis_interval:
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500)
                if latest_rates is None:
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                current_df = calculate_enhanced_indicators(current_df)
                
                cached_df = current_df
                last_analysis = now
                
                signal, signal_strength = optimized_check_signal(current_df, verbose=True)
                
                if signal is not None and len(current_positions) == 0:
                    logger.info(f"🎯 优化版检测到{signal}信号，强度: {signal_strength:.3f}")
                    if optimized_place_order(symbol, signal, signal_strength, current_df):
                        print(f"\n✅ 优化版{signal}订单成功！强度: {signal_strength:.3f}")
                    else:
                        print(f"\n❌ 优化版{signal}下单失败！")
                
                # 详细显示
                if len(current_df) > 0:
                    latest_data = current_df.iloc[-1]
                    market_regime = calculate_market_regime(current_df)
                    trend_strength = latest_data['Trend_Strength'] if not pd.isna(latest_data['Trend_Strength']) else 0
                    
                    print(f"\r📊 {latest_data['time']} | 价格: {current_price:.2f} | 强度: {signal_strength:.3f} | 状态: {market_regime} | 趋势: {trend_strength:.4f} | 持仓: {len(current_positions)}", end="")
            else:
                time_remaining = analysis_interval - (now - last_analysis).total_seconds()
                print(f"\r💹 价格: {current_price:.2f} | 持仓: {len(current_positions)} | 下次分析: {time_remaining:.0f}s | 周期: {cycle_count}", end="")
            
            # 状态记录
            if (now - last_status_log).total_seconds() >= 300:
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"优化版账户 | 余额: {account_info.balance:.2f} | 净值: {account_info.equity:.2f}")
                last_status_log = now
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        logger.info("优化版监控被停止")
        print(f"\n优化版监控结束，共 {cycle_count} 周期")

def check_optimized_signal():
    """检查优化版信号"""
    logger.info("检查优化版当前信号状态")
    
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 500)
    if rates is None:
        print("❌ 无法获取数据")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = calculate_enhanced_indicators(df)
    
    signal, signal_strength = optimized_check_signal(df, verbose=True)
    
    if signal is not None:
        print(f"\n🎯 优化版信号: {signal}, 强度: {signal_strength:.3f}")
    else:
        print(f"\n⚪ 无明确信号, 强度: {signal_strength:.3f}")
    
    # 关键指标展示
    latest = df.iloc[-1]
    market_regime = calculate_market_regime(df)
    
    print("\n=== 优化版关键指标 ===")
    print(f"当前价格: {latest['close']:.2f}")
    print(f"EMA快线: {latest['EMA_fast']:.2f}, EMA慢线: {latest['EMA_slow']:.2f}")
    print(f"RSI: {latest['RSI']:.1f}")
    print(f"ATR: {latest['ATR']:.4f}")
    print(f"趋势强度: {latest['Trend_Strength']:.4f}")
    print(f"市场状态: {market_regime}")

def show_positions():
    """显示持仓"""
    positions = get_positions()
    
    if not positions:
        print("📭 当前无持仓")
        return
    
    print(f"\n💼 当前持仓: {len(positions)}个")
    for i, pos in enumerate(positions, 1):
        print(f"{i}. 票据: {pos.ticket} | {'🟢买入' if pos.type == 0 else '🔴卖出'} | "
              f"数量: {pos.volume} | 开仓: {pos.price_open} | "
              f"当前: {pos.price_current} | 盈亏: {pos.profit:.2f}")

def main_menu():
    """优化版主菜单"""
    print("\n=== 🚀 优化版多因子量化交易系统 ===")
    print("1. 🎯 运行优化版监控")
    print("2. 🔍 检查优化版信号")
    print("3. 💼 查看当前持仓")
    print("0. 🚪 退出")
    
    try:
        choice = input("\n请选择 (0-3): ").strip()
        logger.info(f"用户选择: {choice}")
        
        if choice == "1":
            run_optimized_monitoring()
        elif choice == "2":
            check_optimized_signal()
        elif choice == "3":
            show_positions()
        elif choice == "0":
            return
        else:
            print("❌ 无效选择")
    except KeyboardInterrupt:
        logger.info("程序被中断")
    except Exception as e:
        logger.error(f"程序错误: {e}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    try:
        logger.info(f"获取{symbol}历史数据进行优化分析...")
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1000)
        if rates is None:
            logger.error("无法获取历史数据")
            quit()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = calculate_enhanced_indicators(df)
        
        signal, signal_strength = optimized_check_signal(df, verbose=True)
        if signal is not None:
            print(f"🎯 初始优化分析: {signal}信号，强度: {signal_strength:.3f}")
        else:
            print(f"⚪ 初始优化分析: 无明确信号，强度: {signal_strength:.3f}")
        
        main_menu()
        
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
    finally:
        logger.info("优化版系统结束")
        print("👋 优化版程序已退出")
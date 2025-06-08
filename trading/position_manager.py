"""
持仓管理模块
"""
import logging
import pandas as pd
from datetime import datetime
import MetaTrader5 as mt5
from config.settings import SYMBOL

logger = logging.getLogger('MT5_Trading')

def get_positions(symbol=SYMBOL):
    """获取当前持仓"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    
    if positions:
        logger.debug(f"当前持仓数量: {len(positions)}")
        for pos in positions:
            logger.debug(f"持仓 - 票据: {pos.ticket}, 类型: {'买入' if pos.type == 0 else '卖出'}, 盈亏: {pos.profit:.2f}")
    
    return list(positions)

def check_signal_with_positions(df, current_positions, strategy_manager, verbose=False):
    """检查交易信号 - 考虑当前持仓情况"""
    current_strategy = strategy_manager.get_current_strategy()
    strategy_name = current_strategy.get_name()
    
    try:
        df_with_indicators = strategy_manager.calculate_indicators(df)
        signal = strategy_manager.generate_signal(df_with_indicators, verbose)
        
        # 如果没有持仓，正常处理开仓信号
        if len(current_positions) == 0:
            return signal, []
        
        # 如果有持仓，检查是否需要平仓
        close_orders = []
        
        # DKLL策略的特殊处理：检查平仓信号
        if strategy_name == "DKLL策略":
            latest = df_with_indicators.iloc[-1]
            dl_value = latest.get('DL', 0) if not pd.isna(latest.get('DL', 0)) else 0
            
            for pos in current_positions:
                should_close = False
                close_reason = ""
                
                if pos.type == mt5.POSITION_TYPE_BUY:  # 多仓
                    # DL从正值变为负值或0，平多仓
                    if dl_value <= 0:
                        should_close = True
                        close_reason = f"DKLL平多信号 (DL={dl_value})"
                elif pos.type == mt5.POSITION_TYPE_SELL:  # 空仓
                    # DL从负值变为正值或0，平空仓
                    if dl_value >= 0:
                        should_close = True
                        close_reason = f"DKLL平空信号 (DL={dl_value})"
                
                if should_close:
                    close_orders.append({
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'reason': close_reason
                    })
                    if verbose:
                        logger.info(f"检测到平仓信号: 票据{pos.ticket}, {close_reason}")
        
        # 其他策略的平仓逻辑（如果需要）
        else:
            # 对于有止盈止损的策略，如果检测到反向信号，也可以平仓
            if signal and len(current_positions) > 0:
                for pos in current_positions:
                    # 检查是否是反向信号
                    is_reverse_signal = False
                    if ((pos.type == mt5.POSITION_TYPE_BUY and signal == 'SELL') or
                        (pos.type == mt5.POSITION_TYPE_SELL and signal == 'BUY')):
                        is_reverse_signal = True
                    
                    if is_reverse_signal:
                        close_orders.append({
                            'ticket': pos.ticket,
                            'symbol': pos.symbol,
                            'reason': f"{strategy_name}反向信号"
                        })
                        if verbose:
                            logger.info(f"检测到反向信号平仓: 票据{pos.ticket}, 当前持仓{'多' if pos.type == 0 else '空'}，信号{signal}")
        
        # 如果有平仓信号，则不产生新的开仓信号
        if close_orders:
            return None, close_orders
        else:
            return signal, []
            
    except Exception as e:
        logger.error(f"信号检查失败: {e}")
        return None, []

def log_market_status(df, strategy_manager):
    """记录市场状态"""
    if len(df) < 1:
        return
    
    latest = df.iloc[-1]
    price = latest['close']
    
    # 获取当前策略信息
    current_strategy = strategy_manager.get_current_strategy()
    strategy_name = current_strategy.get_name() if current_strategy else "未知"
    
    # 根据不同策略显示不同指标
    if strategy_name == "双均线策略":
        ma10 = latest['MA10'] if not pd.isna(latest['MA10']) else 0
        ma20 = latest['MA20'] if not pd.isna(latest['MA20']) else 0
        indicator_info = f"MA10: {ma10:.2f} | MA20: {ma20:.2f} | MA差值: {ma10-ma20:.2f}"
    elif strategy_name == "DKLL策略":
        dk = latest['DK'] if 'DK' in latest and not pd.isna(latest['DK']) else 0
        ll = latest['LL'] if 'LL' in latest and not pd.isna(latest['LL']) else 0
        dl = latest['DL'] if 'DL' in latest and not pd.isna(latest['DL']) else 0
        indicator_info = f"DK: {dk} | LL: {ll} | DL: {dl}"
    elif strategy_name == "RSI策略":
        rsi = latest['RSI'] if 'RSI' in latest and not pd.isna(latest['RSI']) else 0
        indicator_info = f"RSI: {rsi:.2f}"
    else:
        indicator_info = "指标计算中..."
    
    # 每5分钟记录一次详细市场状态
    current_minute = datetime.now().minute
    if current_minute % 5 == 0:
        logger.info(f"市场状态 | 策略: {strategy_name} | 价格: {price:.2f} | {indicator_info}")
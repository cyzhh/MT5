"""
订单管理模块
"""
import logging
import MetaTrader5 as mt5
from config.settings import DEFAULT_MAGIC, DEFAULT_DEVIATION
from .mt5_connector import get_symbol_info, get_real_time_price

logger = logging.getLogger('MT5_Trading')
trade_logger = logging.getLogger('MT5_Trades')

def place_order(symbol, direction, volume, strategy_manager, performance_tracker):
    """下单函数"""
    logger.info(f"准备下{direction}单，交易量: {volume}")
    trade_logger.info(f"订单准备 | {symbol} | {direction} | 数量: {volume}")
    
    symbol_info = get_symbol_info(symbol)
    if symbol_info is None:
        logger.error("无法获取交易品种信息，下单失败")
        return False
    
    tick = get_real_time_price(symbol)
    if tick is None:
        logger.error(f"无法获取{symbol}的当前价格，下单失败")
        return False
    
    current_price = tick.ask if direction == 'BUY' else tick.bid
    digits = symbol_info.digits
    point = symbol_info.point
    
    # 获取当前策略
    current_strategy = strategy_manager.get_current_strategy()
    strategy_name = current_strategy.get_name()
    
    # 检查策略是否需要止盈止损
    use_stop_loss = strategy_name != "DKLL策略"  # DKLL策略不使用止盈止损
    use_take_profit = strategy_name != "DKLL策略"
    
    logger.info(f"当前价格: {current_price}, 价格精度: {digits}位小数")
    logger.info(f"当前策略: {strategy_name}, 使用止损: {use_stop_loss}, 使用止盈: {use_take_profit}")
    
    if direction == 'BUY':
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max
    
    if volume < min_volume:
        volume = min_volume
        logger.warning(f"交易量调整至最小值: {volume}")
    elif volume > max_volume:
        volume = max_volume
        logger.warning(f"交易量调整至最大值: {volume}")
    
    # 创建基础订单请求
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": f"Python自动交易-{strategy_name}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    # 如果需要止盈止损，才进行计算和设置
    if use_stop_loss or use_take_profit:
        # 获取交易商的止损止盈限制
        stops_level = symbol_info.trade_stops_level
        freeze_level = symbol_info.trade_freeze_level
        
        logger.info(f"最小止损距离: {stops_level}点, 冻结距离: {freeze_level}点")
        
        # 计算安全的止损止盈距离
        min_distance = max(stops_level, freeze_level, 1000) * point
        sl_distance = max(min_distance * 2, 5000 * point)
        tp_distance = max(min_distance * 3, 10000 * point)
        
        if direction == 'BUY':
            sl_price = round(current_price - sl_distance, digits)
            tp_price = round(current_price + tp_distance, digits)
        else:
            sl_price = round(current_price + sl_distance, digits)
            tp_price = round(current_price - tp_distance, digits)
        
        # 验证距离
        if direction == 'BUY':
            actual_sl_distance = abs(price - sl_price)
            actual_tp_distance = abs(tp_price - price)
        else:
            actual_sl_distance = abs(sl_price - price)
            actual_tp_distance = abs(price - tp_price)
        
        logger.info(f"止损距离: {actual_sl_distance/point:.0f}点, 止盈距离: {actual_tp_distance/point:.0f}点")
        
        # 调整距离如果不够
        if actual_sl_distance < min_distance:
            logger.warning(f"止损距离不足，调整中...")
            if direction == 'BUY':
                sl_price = round(current_price - min_distance * 2, digits)
            else:
                sl_price = round(current_price + min_distance * 2, digits)
            actual_sl_distance = min_distance * 2
        
        if actual_tp_distance < min_distance:
            logger.warning(f"止盈距离不足，调整中...")
            if direction == 'BUY':
                tp_price = round(current_price + min_distance * 3, digits)
            else:
                tp_price = round(current_price - min_distance * 3, digits)
            actual_tp_distance = min_distance * 3
        
        # 添加止损止盈到订单请求
        if use_stop_loss and actual_sl_distance >= min_distance:
            request["sl"] = sl_price
            logger.info(f"设置止损: {sl_price}")
        
        if use_take_profit and actual_tp_distance >= min_distance:
            request["tp"] = tp_price
            logger.info(f"设置止盈: {tp_price}")
        
        logger.info(f"订单参数 - 价格: {price}, 止损: {request.get('sl', '未设置')}, 止盈: {request.get('tp', '未设置')}")
    else:
        logger.info(f"DKLL策略订单 - 价格: {price}, 不设置止盈止损，依靠信号平仓")
    
    logger.info("发送订单请求...")
    trade_logger.info(f"订单发送 | {symbol} | {direction} | 价格: {price} | SL: {request.get('sl', '未设置')} | TP: {request.get('tp', '未设置')} | 策略: {strategy_name}")
    
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        error_msg = f"订单提交失败 - 错误代码: {result.retcode}, 错误信息: {result.comment}"
        logger.error(error_msg)
        trade_logger.error(f"订单失败 | {symbol} | {direction} | 错误: {result.retcode} - {result.comment}")
        
        # 如果因为止损止盈问题失败，尝试不设置止损止盈
        if result.retcode == 10016 and (use_stop_loss or use_take_profit):  # Invalid stops
            logger.info("尝试不设置止损止盈重新下单...")
            simple_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": DEFAULT_DEVIATION,
                "magic": DEFAULT_MAGIC,
                "comment": f"Python自动交易-{strategy_name}-简单订单",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(simple_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("简单订单（无止损止盈）提交成功")
                trade_logger.info(f"简单订单成功 | {symbol} | {direction} | 订单号: {result.order} | 成交价: {result.price}")
                
                # 记录开仓到统计系统
                performance_tracker.record_order_open(
                    ticket=result.order,
                    symbol=symbol,
                    order_type=order_type,
                    volume=volume,
                    open_price=result.price,
                    strategy_name=strategy_name
                )
                return True
        
        return False
    else:
        success_msg = f"订单提交成功 - 订单号: {result.order}, 成交价: {result.price}"
        logger.info(success_msg)
        trade_logger.info(f"订单成功 | {symbol} | {direction} | 订单号: {result.order} | 成交价: {result.price} | 数量: {volume} | 策略: {strategy_name}")
        
        # 记录开仓到统计系统
        performance_tracker.record_order_open(
            ticket=result.order,
            symbol=symbol,
            order_type=order_type,
            volume=volume,
            open_price=result.price,
            strategy_name=strategy_name
        )
        
        return True

def close_position(ticket, symbol, reason, performance_tracker):
    """平仓函数"""
    logger.info(f"准备平仓 - 票据: {ticket}, 原因: {reason}")
    
    # 获取持仓信息
    position = None
    positions = mt5.positions_get()
    if positions:
        for pos in positions:
            if pos.ticket == ticket:
                position = pos
                break
    
    if position is None:
        logger.error(f"未找到票据 {ticket} 的持仓")
        return False
    
    symbol = position.symbol
    volume = position.volume
    position_type = position.type
    
    # 获取当前价格
    tick = get_real_time_price(symbol)
    if tick is None:
        logger.error(f"无法获取{symbol}的当前价格，平仓失败")
        return False
    
    # 确定平仓方向和价格
    if position_type == mt5.POSITION_TYPE_BUY:
        close_type = mt5.ORDER_TYPE_SELL
        close_price = tick.bid
        direction = "SELL"
    else:
        close_type = mt5.ORDER_TYPE_BUY
        close_price = tick.ask
        direction = "BUY"
    
    # 创建平仓请求
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": close_type,
        "position": ticket,
        "price": close_price,
        "deviation": DEFAULT_DEVIATION,
        "magic": DEFAULT_MAGIC,
        "comment": f"Python平仓-{reason}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    logger.info(f"平仓参数 - 票据: {ticket}, 方向: {direction}, 数量: {volume}, 价格: {close_price}")
    trade_logger.info(f"平仓请求 | {symbol} | {direction} | 票据: {ticket} | 价格: {close_price} | 原因: {reason}")
    
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        error_msg = f"平仓失败 - 错误代码: {result.retcode}, 错误信息: {result.comment}"
        logger.error(error_msg)
        trade_logger.error(f"平仓失败 | {symbol} | 票据: {ticket} | 错误: {result.retcode} - {result.comment}")
        return False
    else:
        success_msg = f"平仓成功 - 票据: {ticket}, 平仓价: {result.price}"
        logger.info(success_msg)
        trade_logger.info(f"平仓成功 | {symbol} | 票据: {ticket} | 平仓价: {result.price} | 原因: {reason}")
        
        # 记录平仓到统计系统
        profit = position.profit  # 从持仓信息获取盈亏
        performance_tracker.record_order_close(
            ticket=ticket,
            close_price=result.price,
            profit=profit
        )
        
        return True
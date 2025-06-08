"""
各种监控模式
"""
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5
from config.settings import (
    SYMBOL, SIGNAL_CHECK_INTERVAL, PRICE_UPDATE_INTERVAL,
    DEFAULT_VOLUME, PERFORMANCE_UPDATE_INTERVAL
)
from trading.mt5_connector import get_real_time_price, check_connection_status
from trading.order_manager import place_order, close_position
from trading.position_manager import get_positions, check_signal_with_positions, log_market_status

logger = logging.getLogger('MT5_Trading')
trade_logger = logging.getLogger('MT5_Trades')

def run_continuous_monitoring(strategy_manager, performance_tracker):
    """运行持续监控 - 高速版"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始高速持续监控交易信号... 当前策略: {current_strategy.get_name()}")
    print("按 Ctrl+C 停止监控")
    print(f"监控模式: 高速 (每秒更新价格，每10秒检查信号) | 策略: {current_strategy.get_name()}")
    
    last_signal_check = datetime.now()
    last_status_log = datetime.now()
    last_ma_calculation = datetime.now()
    
    # 缓存数据以提升性能
    cached_df = None
    connection_error_count = 0  # 连接错误计数
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            now = datetime.now()
            
            # 快速获取当前价格（每秒更新）
            tick = get_real_time_price(SYMBOL)
            if tick is None:
                connection_error_count += 1
                logger.warning(f"第{connection_error_count}次无法获取实时价格")
                
                if connection_error_count >= 5:
                    logger.error("连续5次无法获取价格，可能的原因：")
                    logger.error("1. 当前时间市场休市")
                    logger.error("2. 网络连接问题")
                    logger.error("3. MT5服务器连接断开")
                    
                    # 检查是否是周末
                    weekday = now.weekday()
                    if weekday >= 5:  # 周六(5)或周日(6)
                        logger.info("当前是周末，外汇市场休市")
                        print(f"\n🔔 检测到周末市场休市，暂停监控60秒...")
                        time.sleep(60)
                        connection_error_count = 0
                        continue
                    
                    # 尝试重新连接
                    logger.info("尝试重新连接MT5...")
                    if check_connection_status():
                        logger.info("重新连接成功")
                        connection_error_count = 0
                    else:
                        logger.error("重新连接失败，等待30秒后继续尝试")
                        time.sleep(30)
                        continue
                
                time.sleep(5)  # 等待5秒后重试
                continue
            else:
                # 成功获取价格，重置错误计数
                if connection_error_count > 0:
                    logger.info("价格获取恢复正常")
                    connection_error_count = 0
            
            current_price = tick.bid
            current_positions = get_positions()
            
            # 每10秒获取K线数据并检查信号
            if (now - last_signal_check).total_seconds() >= SIGNAL_CHECK_INTERVAL:
                logger.debug(f"执行信号检查 (第{cycle_count}次循环)")
                
                latest_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 100)  # 根据策略需要调整数据量
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                
                # 使用策略管理器计算指标
                current_df = strategy_manager.calculate_indicators(current_df)
                
                cached_df = current_df
                last_signal_check = now
                
                # 详细信号检查
                signal = strategy_manager.generate_signal(current_df, verbose=True)
                
                if signal and len(current_positions) == 0:
                    logger.info(f"🚨 检测到{signal}信号，立即下单！")
                    if place_order(SYMBOL, signal, DEFAULT_VOLUME, strategy_manager, performance_tracker):
                        trade_logger.info(f"高速监控交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！继续监控...")
                    else:
                        trade_logger.error(f"高速监控失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                        print(f"\n❌ {signal}下单失败！继续监控...")
                
                # 更新状态显示
                display_monitoring_status(cached_df, current_price, current_positions, 
                                        current_strategy, cycle_count)
            else:
                # 快速模式：只显示价格变化
                display_quick_monitoring_status(current_price, current_positions, 
                                              last_signal_check, now, cycle_count, 
                                              connection_error_count)
            
            # 每5分钟记录详细状态
            if (now - last_status_log).total_seconds() >= 300:
                if cached_df is not None:
                    log_market_status(cached_df, strategy_manager)
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"账户状态 | 余额: {account_info.balance:.2f} | 净值: {account_info.equity:.2f} | 保证金: {account_info.margin:.2f}")
                last_status_log = now
            
            # 动态调整睡眠时间
            time.sleep(PRICE_UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("高速监控被用户停止")
        print(f"\n监控结束，共执行 {cycle_count} 个监控周期")

def run_classic_monitoring(strategy_manager, performance_tracker):
    """运行经典监控模式 (原速度)"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始经典模式监控... 当前策略: {current_strategy.get_name()}")
    print("按 Ctrl+C 停止监控")
    print(f"监控模式: 经典 (每5秒全面更新) | 策略: {current_strategy.get_name()}")
    
    last_signal_check = datetime.now()
    last_status_log = datetime.now()
    
    try:
        while True:
            latest_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
            if latest_rates is None:
                logger.error("无法获取最新数据")
                time.sleep(30)
                continue
            
            current_df = pd.DataFrame(latest_rates)
            current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
            
            # 使用策略管理器计算指标
            current_df = strategy_manager.calculate_indicators(current_df)
            
            # 每分钟详细检查一次信号
            now = datetime.now()
            verbose = (now - last_signal_check).seconds >= 60
            if verbose:
                last_signal_check = now
            
            # 每5分钟记录一次状态
            if (now - last_status_log).seconds >= 300:
                log_market_status(current_df, strategy_manager)
                last_status_log = now
            
            signal = strategy_manager.generate_signal(current_df, verbose=verbose)
            current_positions = get_positions()
            
            current_time = current_df.iloc[-1]['time']
            current_price = current_df.iloc[-1]['close']
            
            # 根据策略显示不同信息
            display_classic_monitoring_status(current_df, current_time, current_price, 
                                            current_positions, current_strategy)
            
            if signal and len(current_positions) == 0:
                logger.info(f"检测到{signal}信号，准备下单")
                if place_order(SYMBOL, signal, DEFAULT_VOLUME, strategy_manager, performance_tracker):
                    trade_logger.info(f"经典监控交易 | {current_strategy.get_name()} | {signal}信号触发成功")
                    print("\n✅ 订单已提交！继续监控...")
                else:
                    trade_logger.error(f"经典监控失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                    print("\n❌ 下单失败！继续监控...")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("经典监控被用户停止")

def run_timed_monitoring(strategy_manager, performance_tracker, minutes):
    """运行限时监控 - 高速版"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始高速限时监控 {minutes} 分钟，当前策略: {current_strategy.get_name()}")
    end_time = datetime.now() + timedelta(minutes=minutes)
    
    if current_strategy.get_name() == "DKLL策略":
        print("🔔 DKLL策略：不使用止盈止损，完全依靠信号平仓")
    
    cached_df = None
    last_signal_check = datetime.now()
    last_performance_update = datetime.now()
    cycle_count = 0
    connection_error_count = 0
    
    try:
        while datetime.now() < end_time:
            cycle_count += 1
            now = datetime.now()
            remaining = end_time - now
            
            # 快速获取当前价格
            tick = get_real_time_price(SYMBOL)
            if tick is None:
                connection_error_count += 1
                logger.warning(f"第{connection_error_count}次无法获取实时价格")
                time.sleep(2)
                continue
            else:
                if connection_error_count > 0:
                    logger.info("价格获取恢复正常")
                    connection_error_count = 0
                
            current_price = tick.bid
            current_positions = get_positions()
            
            # 每30秒更新一次交易统计
            if (now - last_performance_update).total_seconds() >= PERFORMANCE_UPDATE_INTERVAL:
                performance_tracker.update_positions_from_mt5()
                last_performance_update = now
            
            # 每10秒检查信号
            if (now - last_signal_check).total_seconds() >= SIGNAL_CHECK_INTERVAL:
                latest_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                
                cached_df = current_df
                last_signal_check = now
                
                # 使用新的信号检查函数
                signal, close_orders = check_signal_with_positions(
                    current_df, current_positions, strategy_manager, verbose=True
                )
                
                # 处理平仓信号
                if close_orders:
                    for close_order in close_orders:
                        logger.info(f"限时监控中检测到平仓信号: {close_order['reason']}")
                        if close_position(close_order['ticket'], close_order['symbol'], 
                                        close_order['reason'], performance_tracker):
                            trade_logger.info(f"限时监控平仓 | {current_strategy.get_name()} | {close_order['reason']}成功")
                            print(f"\n✅ 平仓成功: {close_order['reason']}")
                            performance_tracker.print_summary()
                
                # 处理开仓信号
                elif signal and len(current_positions) == 0:
                    logger.info(f"限时监控中检测到{signal}信号")
                    if place_order(SYMBOL, signal, DEFAULT_VOLUME, strategy_manager, performance_tracker):
                        trade_logger.info(f"限时监控交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！")
                        performance_tracker.print_summary()
            
            # 显示状态
            display_timed_monitoring_status(
                cached_df, current_price, current_positions, current_strategy,
                remaining, performance_tracker, connection_error_count
            )
            
            time.sleep(1)  # 高速更新
            
        logger.info(f"限时监控结束，共监控了 {minutes} 分钟，执行了 {cycle_count} 个周期")
        
        # 显示最终统计
        performance_tracker.update_positions_from_mt5()
        performance_tracker.print_summary()
        
    except KeyboardInterrupt:
        logger.info("限时监控被用户中断")
        performance_tracker.update_positions_from_mt5()
        performance_tracker.print_summary()

def display_monitoring_status(cached_df, current_price, current_positions, current_strategy, cycle_count):
    """显示监控状态"""
    if cached_df is not None and len(cached_df) > 0:
        latest_kline = cached_df.iloc[-1]
        kline_time = latest_kline['time']
        
        # 根据策略显示不同指标
        if current_strategy.get_name() == "双均线策略":
            ma10 = latest_kline['MA10'] if not pd.isna(latest_kline['MA10']) else 0
            ma20 = latest_kline['MA20'] if not pd.isna(latest_kline['MA20']) else 0
            indicator_info = f"MA10: {ma10:.2f} | MA20: {ma20:.2f}"
        elif current_strategy.get_name() == "DKLL策略":
            dk = latest_kline.get('DK', 0)
            ll = latest_kline.get('LL', 0)
            dl = latest_kline.get('DL', 0)
            indicator_info = f"DK: {dk} | LL: {ll} | DL: {dl}"
        elif current_strategy.get_name() == "RSI策略":
            rsi = latest_kline.get('RSI', 0)
            indicator_info = f"RSI: {rsi:.2f}"
        else:
            indicator_info = "计算中..."
        
        print(f"\r🔍 {kline_time} | 实时: {current_price:.2f} | K线: {latest_kline['close']:.2f} | {indicator_info} | 持仓: {len(current_positions)} | 周期: {cycle_count}", end="")
    else:
        print(f"\r💹 实时价格: {current_price:.2f} | 持仓: {len(current_positions)} | 周期: {cycle_count}", end="")

def display_quick_monitoring_status(current_price, current_positions, last_signal_check, now, 
                                   cycle_count, connection_error_count):
    """显示快速监控状态"""
    time_remaining = SIGNAL_CHECK_INTERVAL - (now - last_signal_check).total_seconds()
    error_info = f" | 连接错误: {connection_error_count}" if connection_error_count > 0 else ""
    print(f"\r💹 实时: {current_price:.2f} | 持仓: {len(current_positions)} | 下次检查: {time_remaining:.0f}s | 周期: {cycle_count}{error_info}", end="")

def display_classic_monitoring_status(current_df, current_time, current_price, current_positions, current_strategy):
    """显示经典监控状态"""
    if current_strategy.get_name() == "双均线策略":
        ma10 = current_df.iloc[-1]['MA10']
        ma20 = current_df.iloc[-1]['MA20']
        print(f"\r📊 {current_time} | 价格: {current_price:.2f} | MA10: {ma10:.2f} | MA20: {ma20:.2f} | 持仓: {len(current_positions)}", end="")
    elif current_strategy.get_name() == "DKLL策略":
        dk = current_df.iloc[-1].get('DK', 0)
        ll = current_df.iloc[-1].get('LL', 0)
        dl = current_df.iloc[-1].get('DL', 0)
        print(f"\r📊 {current_time} | 价格: {current_price:.2f} | DK: {dk} | LL: {ll} | DL: {dl} | 持仓: {len(current_positions)}", end="")
    elif current_strategy.get_name() == "RSI策略":
        rsi = current_df.iloc[-1].get('RSI', 0)
        print(f"\r📊 {current_time} | 价格: {current_price:.2f} | RSI: {rsi:.2f} | 持仓: {len(current_positions)}", end="")
    else:
        print(f"\r📊 {current_time} | 价格: {current_price:.2f} | 持仓: {len(current_positions)}", end="")

def display_timed_monitoring_status(cached_df, current_price, current_positions, current_strategy,
                                   remaining, performance_tracker, connection_error_count):
    """显示限时监控状态"""
    if cached_df is not None and len(cached_df) > 0:
        latest_kline = cached_df.iloc[-1]
        
        # 根据策略显示不同指标
        if current_strategy.get_name() == "双均线策略":
            ma10 = latest_kline['MA10'] if not pd.isna(latest_kline['MA10']) else 0
            ma20 = latest_kline['MA20'] if not pd.isna(latest_kline['MA20']) else 0
            indicator_info = f"MA10: {ma10:.2f} | MA20: {ma20:.2f}"
        elif current_strategy.get_name() == "DKLL策略":
            dk = latest_kline.get('DK', 0)
            ll = latest_kline.get('LL', 0)
            dl = latest_kline.get('DL', 0)
            indicator_info = f"DK: {dk} | LL: {ll} | DL: {dl}"
        elif current_strategy.get_name() == "RSI策略":
            rsi = latest_kline.get('RSI', 0)
            indicator_info = f"RSI: {rsi:.2f}"
        else:
            indicator_info = "计算中..."
            
        # 添加交易统计
        stats = performance_tracker.get_statistics()
        stats_info = f"交易: {stats['total_trades']} | 胜率: {stats['win_rate']:.1f}% | 盈亏: {stats['total_profit']:+.2f}"
        error_info = f" | 错误: {connection_error_count}" if connection_error_count > 0 else ""
        
        print(f"\r⏱️ {remaining.seconds//60}:{remaining.seconds%60:02d} | 实时: {current_price:.2f} | K线: {latest_kline['close']:.2f} | {indicator_info} | 持仓: {len(current_positions)} | {stats_info}{error_info}", end="")
    else:
        stats = performance_tracker.get_statistics()
        stats_info = f"交易: {stats['total_trades']} | 盈亏: {stats['total_profit']:+.2f}"
        error_info = f" | 错误: {connection_error_count}" if connection_error_count > 0 else ""
        print(f"\r⏱️ {remaining.seconds//60}:{remaining.seconds%60:02d} | 实时: {current_price:.2f} | 持仓: {len(current_positions)} | {stats_info}{error_info}", end="")
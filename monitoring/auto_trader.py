"""
全自动化交易模块
"""
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5
from config.settings import (
    SYMBOL, SIGNAL_CHECK_INTERVAL, PRICE_UPDATE_INTERVAL,
    PERFORMANCE_UPDATE_INTERVAL, DEFAULT_VOLUME
)
from trading.mt5_connector import get_real_time_price, check_connection_status
from trading.order_manager import place_order, close_position
from trading.position_manager import get_positions, check_signal_with_positions, log_market_status

logger = logging.getLogger('MT5_Trading')
trade_logger = logging.getLogger('MT5_Trades')

def run_automated_trading(strategy_manager, performance_tracker, parameter_optimizer,
                         optimization_interval_hours: int = 24, 
                         optimization_lookback_hours: int = 168):
    """运行全自动化交易流程
    
    Args:
        optimization_interval_hours: 参数优化间隔（小时）
        optimization_lookback_hours: 优化时回望的历史数据长度（小时）
    """
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始全自动化交易流程...")
    logger.info(f"当前策略: {current_strategy.get_name()}")
    logger.info(f"参数优化间隔: {optimization_interval_hours} 小时")
    logger.info(f"优化数据长度: {optimization_lookback_hours} 小时")
    
    print("🤖 全自动化交易模式启动")
    print("按 Ctrl+C 停止自动化交易")
    print(f"策略: {current_strategy.get_name()}")
    print(f"参数优化间隔: {optimization_interval_hours} 小时")
    print(f"下次优化时间: {(datetime.now() + timedelta(hours=optimization_interval_hours)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if current_strategy.get_name() == "DKLL策略":
        print("🔔 DKLL策略：不使用止盈止损，完全依靠信号平仓")
    
    # 初始化时间戳
    last_optimization_time = datetime.now()
    last_signal_check = datetime.now()
    last_status_log = datetime.now()
    last_performance_update = datetime.now()
    
    # 缓存数据以提升性能
    cached_df = None
    connection_error_count = 0
    optimization_count = 0
    
    # 记录初始参数
    initial_params = current_strategy.get_params().copy()
    logger.info(f"初始策略参数: {initial_params}")
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            now = datetime.now()
            
            # 检查是否需要参数优化
            time_since_last_optimization = (now - last_optimization_time).total_seconds() / 3600  # 转换为小时
            
            if time_since_last_optimization >= optimization_interval_hours:
                optimization_count += 1
                logger.info("="*60)
                logger.info(f"开始第 {optimization_count} 次自动参数优化...")
                print(f"\n🔧 开始第 {optimization_count} 次参数优化...")
                
                # 暂时记录当前参数
                current_params = current_strategy.get_params().copy()
                
                try:
                    # 执行参数优化
                    optimized_params = parameter_optimizer.optimize_strategy(
                        strategy_name=current_strategy.get_name(),
                        symbol=SYMBOL,
                        optimization_hours=optimization_lookback_hours,
                        test_combinations=30  # 可以调整测试组合数量
                    )
                    
                    if optimized_params:
                        # 应用新参数
                        current_strategy.set_params(optimized_params)
                        logger.info(f"参数优化完成，新参数已应用: {optimized_params}")
                        print(f"✅ 参数优化完成！新参数: {optimized_params}")
                        
                        # 记录参数变化
                        trade_logger.info(f"自动参数优化 | 策略: {current_strategy.get_name()} | 原参数: {current_params} | 新参数: {optimized_params}")
                        
                        # 显示参数对比
                        print("\n📊 参数对比:")
                        for param_name in current_params.keys():
                            old_val = current_params[param_name]
                            new_val = optimized_params[param_name]
                            change = "📈" if new_val > old_val else "📉" if new_val < old_val else "➡️"
                            print(f"  {param_name}: {old_val} → {new_val} {change}")
                        
                    else:
                        logger.warning("参数优化失败，保持当前参数")
                        print("⚠️ 参数优化失败，继续使用当前参数")
                    
                except Exception as e:
                    logger.error(f"参数优化过程中发生错误: {e}")
                    print(f"❌ 参数优化出错: {e}")
                
                last_optimization_time = now
                next_optimization = now + timedelta(hours=optimization_interval_hours)
                print(f"🕒 下次优化时间: {next_optimization.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("="*60)
            
            # 快速获取当前价格（每秒更新）
            tick = get_real_time_price(SYMBOL)
            if tick is None:
                connection_error_count += 1
                logger.warning(f"第{connection_error_count}次无法获取实时价格")
                
                if connection_error_count >= 5:
                    logger.error("连续5次无法获取价格，尝试重新连接...")
                    
                    # 检查是否是周末
                    weekday = now.weekday()
                    if weekday >= 5:  # 周六(5)或周日(6)
                        logger.info("当前是周末，外汇市场休市")
                        print(f"\n🔔 检测到周末市场休市，暂停监控60秒...")
                        time.sleep(60)
                        connection_error_count = 0
                        continue
                    
                    # 尝试重新连接
                    if check_connection_status():
                        logger.info("重新连接成功")
                        connection_error_count = 0
                    else:
                        logger.error("重新连接失败，等待30秒后继续尝试")
                        time.sleep(30)
                        continue
                
                time.sleep(5)
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
            
            # 每10秒获取K线数据并检查信号
            if (now - last_signal_check).total_seconds() >= SIGNAL_CHECK_INTERVAL:
                logger.debug(f"执行信号检查 (第{cycle_count}次循环)")
                
                latest_rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 100)
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                
                cached_df = current_df
                last_signal_check = now
                
                # 使用新的信号检查函数，考虑持仓情况
                signal, close_orders = check_signal_with_positions(
                    current_df, current_positions, strategy_manager, verbose=False
                )
                
                # 处理平仓信号
                if close_orders:
                    for close_order in close_orders:
                        logger.info(f"🔻 自动化交易执行平仓: {close_order['reason']}")
                        if close_position(close_order['ticket'], close_order['symbol'], 
                                        close_order['reason'], performance_tracker):
                            print(f"\n✅ 自动平仓成功: 票据{close_order['ticket']} ({close_order['reason']})")
                            performance_tracker.print_summary()
                        else:
                            print(f"\n❌ 自动平仓失败: 票据{close_order['ticket']}")
                
                # 处理开仓信号（只在无持仓时）
                elif signal and len(current_positions) == 0:
                    logger.info(f"🚨 自动化交易检测到{signal}信号，立即下单！")
                    if place_order(SYMBOL, signal, DEFAULT_VOLUME, strategy_manager, performance_tracker):
                        trade_logger.info(f"全自动交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ 自动{signal}订单已提交！继续监控...")
                        performance_tracker.print_summary()
                    else:
                        trade_logger.error(f"全自动交易失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                        print(f"\n❌ 自动{signal}下单失败！继续监控...")
                
                # 更新状态显示
                display_auto_trading_status(
                    cached_df, current_price, current_positions, current_strategy,
                    performance_tracker, cycle_count, optimization_count, 
                    time_since_last_optimization, optimization_interval_hours
                )
            else:
                # 快速模式：只显示价格变化
                display_quick_status(
                    current_price, current_positions, performance_tracker,
                    last_signal_check, now, cycle_count, connection_error_count,
                    optimization_count, time_since_last_optimization, optimization_interval_hours
                )
            
            # 每5分钟记录详细状态
            if (now - last_status_log).total_seconds() >= 300:
                if cached_df is not None:
                    log_market_status(cached_df, strategy_manager)
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"账户状态 | 余额: {account_info.balance:.2f} | 净值: {account_info.equity:.2f} | 保证金: {account_info.margin:.2f}")
                
                # 记录交易统计和优化状态
                stats = performance_tracker.get_statistics()
                hours_to_next_optimization = optimization_interval_hours - time_since_last_optimization
                logger.info(f"自动化交易统计 | 总交易: {stats['total_trades']} | 胜率: {stats['win_rate']:.2f}% | 总盈亏: {stats['total_profit']:+.2f} | 余额变化: {stats['balance_change']:+.2f}")
                logger.info(f"参数优化状态 | 已优化: {optimization_count}次 | 距离下次: {hours_to_next_optimization:.1f}小时 | 当前参数: {current_strategy.get_params()}")
                last_status_log = now
            
            # 动态调整睡眠时间
            time.sleep(PRICE_UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("全自动化交易被用户停止")
        print(f"\n全自动化交易结束")
        print(f"运行周期数: {cycle_count}")
        print(f"参数优化次数: {optimization_count}")
        
        # 显示最终统计
        performance_tracker.update_positions_from_mt5()
        performance_tracker.print_summary()
        
        # 显示参数变化历史
        final_params = current_strategy.get_params()
        print(f"\n📊 参数变化:")
        print(f"  初始参数: {initial_params}")
        print(f"  最终参数: {final_params}")
        
        param_changed = initial_params != final_params
        if param_changed:
            print("  ✅ 参数在运行过程中已优化")
        else:
            print("  ➡️ 参数未发生变化")

def display_auto_trading_status(cached_df, current_price, current_positions, current_strategy,
                               performance_tracker, cycle_count, optimization_count,
                               time_since_last_optimization, optimization_interval_hours):
    """显示自动交易状态"""
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
        
        # 添加交易统计和优化信息到显示
        stats = performance_tracker.get_statistics()
        stats_info = f"交易: {stats['total_trades']} | 胜率: {stats['win_rate']:.1f}% | 盈亏: {stats['total_profit']:+.2f}"
        
        # 计算距离下次优化的时间
        hours_to_next_optimization = optimization_interval_hours - time_since_last_optimization
        optimization_info = f"优化: {optimization_count}次 | 下次: {hours_to_next_optimization:.1f}h"
        
        print(f"\r🤖 {kline_time} | 实时: {current_price:.2f} | K线: {latest_kline['close']:.2f} | {indicator_info} | 持仓: {len(current_positions)} | {stats_info} | {optimization_info} | 周期: {cycle_count}", end="")
    else:
        stats = performance_tracker.get_statistics()
        stats_info = f"交易: {stats['total_trades']} | 胜率: {stats['win_rate']:.1f}% | 盈亏: {stats['total_profit']:+.2f}"
        hours_to_next_optimization = optimization_interval_hours - time_since_last_optimization
        optimization_info = f"优化: {optimization_count}次 | 下次: {hours_to_next_optimization:.1f}h"
        print(f"\r🤖 实时价格: {current_price:.2f} | 持仓: {len(current_positions)} | {stats_info} | {optimization_info} | 周期: {cycle_count}", end="")

def display_quick_status(current_price, current_positions, performance_tracker,
                        last_signal_check, now, cycle_count, connection_error_count,
                        optimization_count, time_since_last_optimization, optimization_interval_hours):
    """显示快速状态"""
    time_remaining = SIGNAL_CHECK_INTERVAL - (now - last_signal_check).total_seconds()
    error_info = f" | 连接错误: {connection_error_count}" if connection_error_count > 0 else ""
    stats = performance_tracker.get_statistics()
    stats_info = f"交易: {stats['total_trades']} | 盈亏: {stats['total_profit']:+.2f}"
    hours_to_next_optimization = optimization_interval_hours - time_since_last_optimization
    optimization_info = f"优化: {optimization_count}次 | 下次: {hours_to_next_optimization:.1f}h"
    print(f"\r🤖 实时: {current_price:.2f} | 持仓: {len(current_positions)} | {stats_info} | {optimization_info} | 下次检查: {time_remaining:.0f}s | 周期: {cycle_count}{error_info}", end="")
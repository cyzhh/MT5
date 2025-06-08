import MetaTrader5 as mt5
import pandas as pd
import time
import logging
import os
from datetime import datetime, timedelta

symbol = "BTCUSD"

# ===== 日志配置 =====
def setup_logging():
    """设置日志系统"""
    # 创建logs目录
    log_dir = "trading_logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 生成日志文件名（按日期）
    log_filename = f"{log_dir}/trading_{datetime.now().strftime('%Y%m%d')}.log"
    
    # 配置日志格式
    log_format = '%(asctime)s | %(levelname)s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),  # 输出到文件
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    # 创建专用的日志记录器
    logger = logging.getLogger('MT5_Trading')
    
    # 创建单独的交易日志文件
    trade_log_filename = f"{log_dir}/trades_{datetime.now().strftime('%Y%m%d')}.log"
    trade_handler = logging.FileHandler(trade_log_filename, encoding='utf-8')
    trade_handler.setLevel(logging.INFO)
    trade_formatter = logging.Formatter('%(asctime)s | TRADE | %(message)s', datefmt=date_format)
    trade_handler.setFormatter(trade_formatter)
    
    # 创建交易专用日志记录器
    trade_logger = logging.getLogger('MT5_Trades')
    trade_logger.addHandler(trade_handler)
    trade_logger.addHandler(logging.StreamHandler())
    trade_logger.setLevel(logging.INFO)
    
    logger.info("="*60)
    logger.info("MT5自动交易程序启动")
    logger.info(f"日志文件: {log_filename}")
    logger.info(f"交易日志: {trade_log_filename}")
    logger.info("="*60)
    
    return logger, trade_logger

# 初始化日志系统
logger, trade_logger = setup_logging()

# 初始化连接
logger.info("开始初始化MT5连接...")
if not mt5.initialize():
    logger.error(f"MT5初始化失败，错误代码: {mt5.last_error()}")
    quit()

logger.info("MT5初始化成功")

# 登录交易账户
account = 60011971
password = "Demo123456789."
server = "TradeMaxGlobal-Demo"

logger.info(f"尝试登录账户: {account}, 服务器: {server}")
authorized = mt5.login(account, password=password, server=server)
if not authorized:
    logger.error(f"登录失败，错误代码: {mt5.last_error()}")
    mt5.shutdown()
    quit()

logger.info(f"成功登录到账户: {account}")

def check_auto_trading():
    """检查自动交易状态"""
    logger.info("检查自动交易状态...")
    
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        logger.error("无法获取终端信息")
        return False
    
    logger.info(f"终端信息 - 自动交易启用: {terminal_info.trade_allowed}, EA交易启用: {terminal_info.dlls_allowed}")
    
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("无法获取账户信息")
        return False
    
    logger.info(f"账户信息 - 交易启用: {account_info.trade_allowed}, 交易模式: {account_info.trade_mode}")
    logger.info(f"账户余额: {account_info.balance}, 净值: {account_info.equity}, 保证金: {account_info.margin}")
    
    is_trading_allowed = (terminal_info.trade_allowed and 
                         terminal_info.dlls_allowed and 
                         account_info.trade_allowed)
    
    if is_trading_allowed:
        logger.info("✅ 自动交易状态正常")
    else:
        logger.warning("❌ 自动交易未启用")
    
    return is_trading_allowed

# 检查交易状态
if not check_auto_trading():
    logger.error("自动交易未启用，程序退出")
    mt5.shutdown()
    quit()

def get_symbol_info(symbol):
    """获取交易品种信息"""
    logger.debug(f"获取{symbol}的交易品种信息...")
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"无法获取{symbol}的信息")
        return None
    
    if not symbol_info.visible:
        logger.info(f"尝试添加{symbol}到市场观察...")
        if not mt5.symbol_select(symbol, True):
            logger.error(f"无法添加{symbol}到市场观察")
            return None
        logger.info(f"{symbol}已添加到市场观察")
    
    logger.debug(f"{symbol}信息 - 点差: {symbol_info.spread}, 最小交易量: {symbol_info.volume_min}")
    return symbol_info

def check_signal(df, verbose=False):
    """检查交易信号 - 增加详细输出"""
    if len(df) < 2:
        if verbose:
            logger.warning("数据不足，需要至少2根K线")
        return None
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 确保MA数据有效
    if pd.isna(latest['MA10']) or pd.isna(latest['MA20']) or pd.isna(prev['MA10']) or pd.isna(prev['MA20']):
        if verbose:
            logger.warning("MA数据无效")
        return None
    
    if verbose:
        logger.info("=== 信号检查详情 ===")
        logger.info(f"前一根K线: MA10={prev['MA10']:.2f}, MA20={prev['MA20']:.2f}")
        logger.info(f"当前K线: MA10={latest['MA10']:.2f}, MA20={latest['MA20']:.2f}")
        logger.info(f"最新价格: {latest['close']:.2f}")
    
    # 金叉信号
    if prev['MA10'] < prev['MA20'] and latest['MA10'] > latest['MA20']:
        signal = 'BUY'
        logger.info(f"🔔 检测到金叉信号 (BUY) - MA10从{prev['MA10']:.2f}升至{latest['MA10']:.2f}")
        return signal
    # 死叉信号
    elif prev['MA10'] > prev['MA20'] and latest['MA10'] < latest['MA20']:
        signal = 'SELL'
        logger.info(f"🔔 检测到死叉信号 (SELL) - MA10从{prev['MA10']:.2f}降至{latest['MA10']:.2f}")
        return signal
    
    if verbose:
        ma_diff = latest['MA10'] - latest['MA20']
        logger.info(f"无信号 - MA差值: {ma_diff:.2f}")
    
    return None

def place_order(symbol, direction, volume=0.01):
    """下单函数"""
    logger.info(f"准备下{direction}单，交易量: {volume}")
    trade_logger.info(f"订单准备 | {symbol} | {direction} | 数量: {volume}")
    
    symbol_info = get_symbol_info(symbol)
    if symbol_info is None:
        logger.error("无法获取交易品种信息，下单失败")
        return False
    
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error(f"无法获取{symbol}的当前价格")
        return False
    
    current_price = tick.ask if direction == 'BUY' else tick.bid
    digits = symbol_info.digits
    point = symbol_info.point
    
    # 获取交易商的止损止盈限制
    stops_level = symbol_info.trade_stops_level
    freeze_level = symbol_info.trade_freeze_level
    
    logger.info(f"当前价格: {current_price}, 价格精度: {digits}位小数")
    logger.info(f"最小止损距离: {stops_level}点, 冻结距离: {freeze_level}点")
    
    # 计算安全的止损止盈距离（确保大于最小要求）
    min_distance = max(stops_level, freeze_level, 1000) * point  # 至少1000点
    sl_distance = max(min_distance * 2, 5000 * point)  
    tp_distance = max(min_distance * 3, 10000 * point) 
    
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
    
    # 验证止损止盈价格是否符合要求
    if direction == 'BUY':
        actual_sl_distance = abs(price - sl_price)
        actual_tp_distance = abs(tp_price - price)
    else:
        actual_sl_distance = abs(sl_price - price)
        actual_tp_distance = abs(price - tp_price)
    
    logger.info(f"止损距离: {actual_sl_distance/point:.0f}点, 止盈距离: {actual_tp_distance/point:.0f}点")
    
    # 如果距离仍然不够，调整为更大的距离
    if actual_sl_distance < min_distance:
        logger.warning(f"止损距离不足，调整中...")
        if direction == 'BUY':
            sl_price = round(current_price - min_distance * 2, digits)
        else:
            sl_price = round(current_price + min_distance * 2, digits)
    
    if actual_tp_distance < min_distance:
        logger.warning(f"止盈距离不足，调整中...")
        if direction == 'BUY':
            tp_price = round(current_price + min_distance * 3, digits)
        else:
            tp_price = round(current_price - min_distance * 3, digits)
    
    min_volume = symbol_info.volume_min
    max_volume = symbol_info.volume_max
    
    if volume < min_volume:
        volume = min_volume
        logger.warning(f"交易量调整至最小值: {volume}")
    elif volume > max_volume:
        volume = max_volume
        logger.warning(f"交易量调整至最大值: {volume}")
    
    logger.info(f"订单参数 - 价格: {price}, 止损: {sl_price} ({abs(price-sl_price)/point:.0f}点), 止盈: {tp_price} ({abs(tp_price-price)/point:.0f}点)")
    
    # 创建订单请求，如果止损止盈仍有问题，尝试不设置止损止盈
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "Python自动交易",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    
    # 只有在止损止盈距离足够时才添加
    if actual_sl_distance >= min_distance:
        request["sl"] = sl_price
    else:
        logger.warning("止损距离不足，暂不设置止损")
        
    if actual_tp_distance >= min_distance:
        request["tp"] = tp_price
    else:
        logger.warning("止盈距离不足，暂不设置止盈")
    
    logger.info("发送订单请求...")
    trade_logger.info(f"订单发送 | {symbol} | {direction} | 价格: {price} | SL: {request.get('sl', '未设置')} | TP: {request.get('tp', '未设置')}")
    
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        error_msg = f"订单提交失败 - 错误代码: {result.retcode}, 错误信息: {result.comment}"
        logger.error(error_msg)
        trade_logger.error(f"订单失败 | {symbol} | {direction} | 错误: {result.retcode} - {result.comment}")
        
        # 如果仍然失败，尝试只下市价单，不设置止损止盈
        if result.retcode == 10016:  # Invalid stops
            logger.info("尝试不设置止损止盈重新下单...")
            simple_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,
                "magic": 123456,
                "comment": "Python自动交易-简单订单",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(simple_request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info("简单订单（无止损止盈）提交成功")
                trade_logger.info(f"简单订单成功 | {symbol} | {direction} | 订单号: {result.order} | 成交价: {result.price}")
                return True
        
        return False
    else:
        success_msg = f"订单提交成功 - 订单号: {result.order}, 成交价: {result.price}"
        logger.info(success_msg)
        trade_logger.info(f"订单成功 | {symbol} | {direction} | 订单号: {result.order} | 成交价: {result.price} | 数量: {volume}")
        return True

def get_positions():
    """获取当前持仓"""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    
    if positions:
        logger.debug(f"当前持仓数量: {len(positions)}")
        for pos in positions:
            logger.debug(f"持仓 - 票据: {pos.ticket}, 类型: {'买入' if pos.type == 0 else '卖出'}, 盈亏: {pos.profit:.2f}")
    
    return list(positions)

def log_market_status(df):
    """记录市场状态"""
    if len(df) < 1:
        return
    
    latest = df.iloc[-1]
    price = latest['close']
    ma10 = latest['MA10'] if not pd.isna(latest['MA10']) else 0
    ma20 = latest['MA20'] if not pd.isna(latest['MA20']) else 0
    
    # 每5分钟记录一次详细市场状态
    current_minute = datetime.now().minute
    if current_minute % 5 == 0:
        logger.info(f"市场状态 | 价格: {price:.2f} | MA10: {ma10:.2f} | MA20: {ma20:.2f} | MA差值: {ma10-ma20:.2f}")

def main_with_options():
    """主程序 - 带选项菜单"""
    logger.info("显示程序菜单")
    
    print("\n=== 交易程序选项 ===")
    print("1. 运行高速监控 (每秒更新，每10秒检查信号)")
    print("2. 运行限时高速监控 (指定时间)")
    print("3. 运行经典监控 (每5秒更新)")
    print("4. 检查当前信号状态")
    print("5. 手动下单测试")
    print("6. 查看当前持仓")
    print("0. 退出")
    
    try:
        choice = input("\n请选择操作 (0-6): ").strip()
        logger.info(f"用户选择: {choice}")
        
        if choice == "1":
            run_continuous_monitoring()
        elif choice == "2":
            minutes = input("监控多少分钟? (默认10): ").strip()
            minutes = int(minutes) if minutes.isdigit() else 10
            logger.info(f"用户选择限时高速监控: {minutes}分钟")
            run_timed_monitoring(minutes)
        elif choice == "3":
            run_classic_monitoring()
        elif choice == "4":
            check_current_signal()
        elif choice == "5":
            test_manual_order()
        elif choice == "6":
            show_positions()
        elif choice == "0":
            logger.info("用户选择退出程序")
            return
        else:
            logger.warning(f"无效选择: {choice}")
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断 (Ctrl+C)")
    except Exception as e:
        logger.error(f"程序发生错误: {e}", exc_info=True)
    finally:
        logger.info("关闭MT5连接")
        mt5.shutdown()

def run_classic_monitoring():
    """运行经典监控模式 (原速度)"""
    logger.info("开始经典模式监控...")
    print("按 Ctrl+C 停止监控")
    print("监控模式: 经典 (每5秒全面更新)")
    
    last_signal_check = datetime.now()
    last_status_log = datetime.now()
    
    try:
        while True:
            latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if latest_rates is None:
                logger.error("无法获取最新数据")
                time.sleep(30)
                continue
            
            current_df = pd.DataFrame(latest_rates)
            current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
            current_df['MA10'] = current_df['close'].rolling(window=10).mean()
            current_df['MA20'] = current_df['close'].rolling(window=20).mean()
            
            # 每分钟详细检查一次信号
            now = datetime.now()
            verbose = (now - last_signal_check).seconds >= 60
            if verbose:
                last_signal_check = now
            
            # 每5分钟记录一次状态
            if (now - last_status_log).seconds >= 300:
                log_market_status(current_df)
                last_status_log = now
            
            signal = check_signal(current_df, verbose=verbose)
            current_positions = get_positions()
            
            current_time = current_df.iloc[-1]['time']
            current_price = current_df.iloc[-1]['close']
            ma10 = current_df.iloc[-1]['MA10']
            ma20 = current_df.iloc[-1]['MA20']
            
            print(f"\r📊 {current_time} | 价格: {current_price:.2f} | MA10: {ma10:.2f} | MA20: {ma20:.2f} | 持仓: {len(current_positions)}", end="")
            
            if signal and len(current_positions) == 0:
                logger.info(f"检测到{signal}信号，准备下单")
                if place_order(symbol, signal, volume=0.01):
                    trade_logger.info(f"经典监控交易 | {signal}信号触发成功")
                    print("\n✅ 订单已提交！继续监控...")
                else:
                    trade_logger.error(f"经典监控失败 | {signal}信号触发但下单失败")
                    print("\n❌ 下单失败！继续监控...")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("经典监控被用户停止")

def run_continuous_monitoring():
    """运行持续监控 - 高速版"""
    logger.info("开始高速持续监控交易信号...")
    print("按 Ctrl+C 停止监控")
    print("监控模式: 高速 (每秒更新价格，每10秒检查信号)")
    
    last_signal_check = datetime.now()
    last_status_log = datetime.now()
    last_ma_calculation = datetime.now()
    
    # 缓存数据以提升性能
    cached_df = None
    signal_check_interval = 10  # 秒
    price_update_interval = 1   # 秒
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            now = datetime.now()
            
            # 快速获取当前价格（每秒更新）
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning("无法获取实时价格")
                time.sleep(2)
                continue
            
            current_price = tick.bid
            current_positions = get_positions()
            
            # 每10秒获取K线数据并检查信号
            if (now - last_signal_check).total_seconds() >= signal_check_interval:
                logger.debug(f"执行信号检查 (第{cycle_count}次循环)")
                
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)  # 减少数据量提升速度
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                current_df['MA10'] = current_df['close'].rolling(window=10).mean()
                current_df['MA20'] = current_df['close'].rolling(window=20).mean()
                
                cached_df = current_df
                last_signal_check = now
                
                # 详细信号检查
                signal = check_signal(current_df, verbose=True)
                
                if signal and len(current_positions) == 0:
                    logger.info(f"🚨 检测到{signal}信号，立即下单！")
                    if place_order(symbol, signal, volume=0.01):
                        trade_logger.info(f"高速监控交易 | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！继续监控...")
                    else:
                        trade_logger.error(f"高速监控失败 | {signal}信号触发但下单失败")
                        print(f"\n❌ {signal}下单失败！继续监控...")
                
                # 更新状态显示
                if cached_df is not None and len(cached_df) > 0:
                    latest_kline = cached_df.iloc[-1]
                    ma10 = latest_kline['MA10'] if not pd.isna(latest_kline['MA10']) else 0
                    ma20 = latest_kline['MA20'] if not pd.isna(latest_kline['MA20']) else 0
                    kline_time = latest_kline['time']
                    
                    print(f"\r🔍 {kline_time} | 实时: {current_price:.2f} | K线: {latest_kline['close']:.2f} | MA10: {ma10:.2f} | MA20: {ma20:.2f} | 持仓: {len(current_positions)} | 周期: {cycle_count}", end="")
                else:
                    print(f"\r💹 实时价格: {current_price:.2f} | 持仓: {len(current_positions)} | 周期: {cycle_count}", end="")
            else:
                # 快速模式：只显示价格变化
                time_remaining = signal_check_interval - (now - last_signal_check).total_seconds()
                print(f"\r💹 实时: {current_price:.2f} | 持仓: {len(current_positions)} | 下次检查: {time_remaining:.0f}s | 周期: {cycle_count}", end="")
            
            # 每5分钟记录详细状态
            if (now - last_status_log).total_seconds() >= 300:
                if cached_df is not None:
                    log_market_status(cached_df)
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"账户状态 | 余额: {account_info.balance:.2f} | 净值: {account_info.equity:.2f} | 保证金: {account_info.margin:.2f}")
                last_status_log = now
            
            # 动态调整睡眠时间
            time.sleep(price_update_interval)
            
    except KeyboardInterrupt:
        logger.info("高速监控被用户停止")
        print(f"\n监控结束，共执行 {cycle_count} 个监控周期")

def run_timed_monitoring(minutes):
    """运行限时监控 - 高速版"""
    logger.info(f"开始高速限时监控 {minutes} 分钟")
    end_time = datetime.now() + timedelta(minutes=minutes)
    
    cached_df = None
    last_signal_check = datetime.now()
    signal_check_interval = 10  # 秒
    cycle_count = 0
    
    try:
        while datetime.now() < end_time:
            cycle_count += 1
            now = datetime.now()
            remaining = end_time - now
            
            # 快速获取当前价格
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning("无法获取实时价格")
                time.sleep(2)
                continue
                
            current_price = tick.bid
            current_positions = get_positions()
            
            # 每10秒检查信号
            if (now - last_signal_check).total_seconds() >= signal_check_interval:
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                current_df['MA10'] = current_df['close'].rolling(window=10).mean()
                current_df['MA20'] = current_df['close'].rolling(window=20).mean()
                
                cached_df = current_df
                last_signal_check = now
                
                signal = check_signal(current_df, verbose=True)
                
                if signal and len(current_positions) == 0:
                    logger.info(f"限时监控中检测到{signal}信号")
                    if place_order(symbol, signal, volume=0.01):
                        trade_logger.info(f"限时监控交易 | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！")
            
            # 显示状态
            if cached_df is not None and len(cached_df) > 0:
                latest_kline = cached_df.iloc[-1]
                ma10 = latest_kline['MA10'] if not pd.isna(latest_kline['MA10']) else 0
                ma20 = latest_kline['MA20'] if not pd.isna(latest_kline['MA20']) else 0
                print(f"\r⏱️ {remaining.seconds//60}:{remaining.seconds%60:02d} | 实时: {current_price:.2f} | K线: {latest_kline['close']:.2f} | MA10: {ma10:.2f} | MA20: {ma20:.2f} | 持仓: {len(current_positions)}", end="")
            else:
                print(f"\r⏱️ {remaining.seconds//60}:{remaining.seconds%60:02d} | 实时: {current_price:.2f} | 持仓: {len(current_positions)}", end="")
            
            time.sleep(1)  # 高速更新
            
        logger.info(f"限时监控结束，共监控了 {minutes} 分钟，执行了 {cycle_count} 个周期")
        
    except KeyboardInterrupt:
        logger.info("限时监控被用户中断")

def check_current_signal():
    """检查当前信号状态"""
    logger.info("用户请求检查当前信号状态")
    
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1000)
    if rates is None:
        logger.error("无法获取数据")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    
    signal = check_signal(df, verbose=True)
    
    if signal:
        logger.info(f"当前信号检查结果: {signal}")
    else:
        logger.info("当前信号检查结果: 无交易信号")
    
    # 记录最近的MA数据
    recent_data = df[['time', 'close', 'MA10', 'MA20']].tail(5)
    logger.info("最近5根K线的MA数据:")
    for _, row in recent_data.iterrows():
        ma_diff = row['MA10'] - row['MA20']
        logger.info(f"{row['time']} | 收盘: {row['close']:.2f} | MA10: {row['MA10']:.2f} | MA20: {row['MA20']:.2f} | 差值: {ma_diff:.2f}")

def test_manual_order():
    """手动测试下单"""
    logger.info("用户进入手动下单测试")
    
    direction = input("输入方向 (B/S): ").strip().upper()
    
    if direction not in ['B', 'S']:
        logger.warning(f"用户输入无效方向: {direction}")
        return
    
    volume = input("输入交易量 (默认0.01): ").strip()
    volume = float(volume) if volume else 0.01
    
    logger.info(f"用户设置手动订单: {direction}, 数量: {volume}")
    
    confirm = input(f"确认下{direction}单，交易量{volume}? (y/N): ").strip().lower()
    if confirm == 'y':
        logger.info("用户确认手动下单")
        place_order(symbol, direction, volume)
    else:
        logger.info("用户取消手动下单")

def show_positions():
    """显示当前持仓"""
    logger.info("用户查看当前持仓")
    
    positions = get_positions()
    
    if not positions:
        logger.info("当前无持仓")
        return
    
    logger.info(f"当前持仓数量: {len(positions)}")
    for pos in positions:
        position_info = (f"持仓详情 - 票据: {pos.ticket}, 品种: {pos.symbol}, "
                        f"类型: {'买入' if pos.type == 0 else '卖出'}, "
                        f"数量: {pos.volume}, 开仓价: {pos.price_open}, "
                        f"当前价: {pos.price_current}, 盈亏: {pos.profit:.2f}")
        logger.info(position_info)

if __name__ == "__main__":
    # 获取历史数据用于MA计算
    try:
        logger.info(f"开始获取{symbol}的历史数据...")
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1000)
        if rates is None:
            logger.error(f"无法获取{symbol}的历史数据")
            mt5.shutdown()
            quit()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        logger.info(f"成功获取{len(df)}根K线数据")
        
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}", exc_info=True)
        mt5.shutdown()
        quit()
    
    # 启动主程序
    try:
        main_with_options()
    except Exception as e:
        logger.error(f"主程序异常: {e}", exc_info=True)
    finally:
        logger.info("程序结束")
        logger.info("="*60)
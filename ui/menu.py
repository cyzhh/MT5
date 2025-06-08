"""
主菜单界面
"""
import logging
from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5
from config.settings import SYMBOL, DEFAULT_VOLUME
from trading.mt5_connector import get_real_time_price
from trading.order_manager import place_order, close_position
from trading.position_manager import get_positions, check_signal_with_positions
from monitoring.monitor import run_continuous_monitoring, run_classic_monitoring, run_timed_monitoring
from monitoring.auto_trader import run_automated_trading

logger = logging.getLogger('MT5_Trading')
trade_logger = logging.getLogger('MT5_Trades')

def main_menu(strategy_manager, performance_tracker, parameter_optimizer):
    """主程序菜单"""
    logger.info("显示程序菜单")
    
    # 显示当前策略信息
    print(f"\n当前策略: {strategy_manager.get_current_strategy().get_name()}")
    
    print("\n=== 交易程序选项 ===")
    print("1. 运行高速监控 (每秒更新，每10秒检查信号)")
    print("2. 运行限时高速监控 (指定时间)")
    print("3. 运行经典监控 (每5秒更新)")
    print("4. 🤖 全自动化交易 (含定时参数优化)")
    print("5. 检查当前信号状态")
    print("6. 手动下单测试")
    print("7. 查看当前持仓")
    print("8. 策略选择和配置")  
    print("9. 查看策略信息")   
    print("10. 系统诊断")        
    print("11. 查看交易统计")
    print("12. 🔧 手动参数优化")
    print("0. 退出")
    
    try:
        choice = input("\n请选择操作 (0-12): ").strip()
        logger.info(f"用户选择: {choice}")
        
        if choice == "1":
            run_continuous_monitoring(strategy_manager, performance_tracker)
        elif choice == "2":
            minutes = input("监控多少分钟? (默认10): ").strip()
            minutes = int(minutes) if minutes.isdigit() else 10
            logger.info(f"用户选择限时高速监控: {minutes}分钟")
            run_timed_monitoring(strategy_manager, performance_tracker, minutes)
        elif choice == "3":
            run_classic_monitoring(strategy_manager, performance_tracker)
        elif choice == "4":
            setup_automated_trading(strategy_manager, performance_tracker, parameter_optimizer)
        elif choice == "5":
            check_current_signal(strategy_manager, performance_tracker)
        elif choice == "6":
            test_manual_order(strategy_manager, performance_tracker)
        elif choice == "7":
            show_positions(strategy_manager, performance_tracker)
        elif choice == "8":
            strategy_selection_menu(strategy_manager)
        elif choice == "9":
            print("\n" + strategy_manager.get_strategy_info())
        elif choice == "10":
            from ui.diagnosis import diagnose_system
            diagnose_system(strategy_manager)
        elif choice == "11":
            view_trading_statistics(performance_tracker)
        elif choice == "12":
            manual_parameter_optimization(strategy_manager, parameter_optimizer)
        elif choice == "0":
            logger.info("用户选择退出程序")
            return False
        else:
            logger.warning(f"无效选择: {choice}")
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断 (Ctrl+C)")
    except Exception as e:
        logger.error(f"程序发生错误: {e}", exc_info=True)
    
    return True

def setup_automated_trading(strategy_manager, performance_tracker, parameter_optimizer):
    """设置全自动化交易参数"""
    logger.info("用户配置全自动化交易参数")
    
    current_strategy = strategy_manager.get_current_strategy()
    print(f"\n🤖 全自动化交易设置")
    print(f"当前策略: {current_strategy.get_name()}")
    print(f"交易品种: {SYMBOL}")
    
    # 设置优化间隔
    print(f"\n⏰ 参数优化设置:")
    optimization_interval = input("参数优化间隔（小时，默认24）: ").strip()
    try:
        optimization_interval_hours = int(optimization_interval) if optimization_interval else 24
        if optimization_interval_hours < 1:
            print("⚠️ 优化间隔至少1小时，已设置为1小时")
            optimization_interval_hours = 1
        elif optimization_interval_hours > 168:  # 7天
            print("⚠️ 优化间隔最多168小时，已设置为168小时")
            optimization_interval_hours = 168
    except ValueError:
        print("⚠️ 输入无效，使用默认24小时")
        optimization_interval_hours = 24
    
    # 设置优化回望期
    optimization_lookback = input("优化数据回望期（小时，默认168=7天）: ").strip()
    try:
        optimization_lookback_hours = int(optimization_lookback) if optimization_lookback else 168
        if optimization_lookback_hours < 24:
            print("⚠️ 回望期至少24小时，已设置为24小时")
            optimization_lookback_hours = 24
        elif optimization_lookback_hours > 720:  # 30天
            print("⚠️ 回望期最多720小时，已设置为720小时")
            optimization_lookback_hours = 720
    except ValueError:
        print("⚠️ 输入无效，使用默认168小时")
        optimization_lookback_hours = 168
    
    # 显示设置总结
    print(f"\n📋 自动化交易配置:")
    print(f"  策略: {current_strategy.get_name()}")
    print(f"  品种: {SYMBOL}")
    print(f"  优化间隔: {optimization_interval_hours} 小时")
    print(f"  回望期: {optimization_lookback_hours} 小时 ({optimization_lookback_hours//24} 天)")
    print(f"  首次优化: {(datetime.now() + timedelta(hours=optimization_interval_hours)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if current_strategy.get_name() == "DKLL策略":
        print(f"  策略特点: 不使用止盈止损，依靠信号平仓")
    
    # 确认启动
    confirm = input(f"\n确认启动全自动化交易? (y/N): ").strip().lower()
    if confirm == 'y':
        logger.info(f"用户确认启动全自动化交易 - 优化间隔: {optimization_interval_hours}h, 回望期: {optimization_lookback_hours}h")
        run_automated_trading(strategy_manager, performance_tracker, parameter_optimizer,
                            optimization_interval_hours, optimization_lookback_hours)
    else:
        logger.info("用户取消全自动化交易")
        print("已取消全自动化交易")

def check_current_signal(strategy_manager, performance_tracker):
    """检查当前信号状态"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"用户请求检查当前信号状态，当前策略: {current_strategy.get_name()}")
    
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 1000)
    if rates is None:
        logger.error("无法获取数据")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 获取当前持仓
    current_positions = get_positions()
    
    # 使用新的信号检查函数
    signal, close_orders = check_signal_with_positions(df, current_positions, strategy_manager, verbose=True)
    
    print(f"\n当前策略: {current_strategy.get_name()}")
    print(f"策略描述: {current_strategy.get_description()}")
    print(f"当前持仓: {len(current_positions)} 笔")
    
    if close_orders:
        print(f"\n🔻 检测到平仓信号:")
        for close_order in close_orders:
            print(f"   - 票据{close_order['ticket']}: {close_order['reason']}")
    elif signal:
        print(f"\n🔔 检测到开仓信号: {signal}")
    else:
        print(f"\n⚪ 当前无交易信号")
    
    # 根据策略显示相关数据
    recent_data = df.tail(5)
    logger.info("最近5根K线的数据:")
    
    for _, row in recent_data.iterrows():
        time_str = row['time'].strftime('%Y-%m-%d %H:%M')
        price_str = f"收盘: {row['close']:.2f}"
        
        if current_strategy.get_name() == "双均线策略":
            ma10 = row['MA10'] if not pd.isna(row['MA10']) else 0
            ma20 = row['MA20'] if not pd.isna(row['MA20']) else 0
            ma_diff = ma10 - ma20
            indicator_str = f"MA10: {ma10:.2f} | MA20: {ma20:.2f} | 差值: {ma_diff:.2f}"
        elif current_strategy.get_name() == "DKLL策略":
            dk = row.get('DK', 0)
            ll = row.get('LL', 0)
            dl = row.get('DL', 0)
            indicator_str = f"DK: {dk} | LL: {ll} | DL: {dl}"
        elif current_strategy.get_name() == "RSI策略":
            rsi = row.get('RSI', 0)
            indicator_str = f"RSI: {rsi:.2f}"
        else:
            indicator_str = "指标计算中..."
        
        logger.info(f"{time_str} | {price_str} | {indicator_str}")
    
    # 如果有持仓，显示持仓详情
    if current_positions:
        print(f"\n📋 当前持仓详情:")
        for pos in current_positions:
            position_type = "多仓" if pos.type == 0 else "空仓"
            current_price = get_real_time_price(pos.symbol)
            if current_price:
                price_str = f"当前价: {current_price.bid:.2f}"
            else:
                price_str = "价格获取失败"
            print(f"   票据{pos.ticket}: {position_type} {pos.symbol} | 开仓价: {pos.price_open:.2f} | {price_str} | 盈亏: {pos.profit:+.2f}")

def test_manual_order(strategy_manager, performance_tracker):
    """手动测试下单"""
    logger.info("用户进入手动下单测试")
    
    current_strategy = strategy_manager.get_current_strategy()
    print(f"\n当前策略: {current_strategy.get_name()}")
    
    if current_strategy.get_name() == "DKLL策略":
        print("🔔 DKLL策略特点：不设置止盈止损，完全依靠信号平仓")
    
    direction = input("输入方向 (BUY/SELL 或 B/S): ").strip().upper()
    
    # 标准化方向输入
    if direction in ['B', 'BUY']:
        direction = 'BUY'
    elif direction in ['S', 'SELL']:
        direction = 'SELL'
    else:
        logger.warning(f"用户输入无效方向: {direction}")
        print("❌ 无效方向，请输入 BUY/SELL 或 B/S")
        return
    
    volume = input("输入交易量 (默认0.01): ").strip()
    volume = float(volume) if volume else DEFAULT_VOLUME
    
    logger.info(f"用户设置手动订单: {direction}, 数量: {volume}, 当前策略: {current_strategy.get_name()}")
    
    # 显示当前策略的止盈止损设置
    use_sl_tp = current_strategy.get_name() != "DKLL策略"
    if use_sl_tp:
        print(f"📊 {current_strategy.get_name()}将自动设置止盈止损")
    else:
        print(f"🚫 {current_strategy.get_name()}不设置止盈止损，依靠信号平仓")
    
    confirm = input(f"确认下{direction}单，交易量{volume}? (y/N): ").strip().lower()
    if confirm == 'y':
        logger.info("用户确认手动下单")
        if place_order(SYMBOL, direction, volume, strategy_manager, performance_tracker):
            print("✅ 订单提交成功！")
            trade_logger.info(f"手动下单成功 | 策略: {current_strategy.get_name()} | 方向: {direction} | 数量: {volume}")
        else:
            print("❌ 订单提交失败！")
    else:
        logger.info("用户取消手动下单")

def show_positions(strategy_manager, performance_tracker):
    """显示当前持仓"""
    logger.info("用户查看当前持仓")
    
    positions = get_positions()
    current_strategy = strategy_manager.get_current_strategy()
    
    if not positions:
        logger.info("当前无持仓")
        print("当前无持仓")
        return
    
    print(f"\n当前持仓数量: {len(positions)}")
    print(f"当前策略: {current_strategy.get_name()}")
    
    if current_strategy.get_name() == "DKLL策略":
        print("🔔 DKLL策略特点：无止盈止损，依靠信号平仓")
    
    logger.info(f"当前持仓数量: {len(positions)}")
    
    total_profit = 0
    for i, pos in enumerate(positions, 1):
        position_type = "买入(多)" if pos.type == 0 else "卖出(空)"
        
        # 获取当前价格计算浮动盈亏
        current_tick = get_real_time_price(pos.symbol)
        if current_tick:
            current_price = current_tick.bid if pos.type == 0 else current_tick.ask
            price_info = f"当前价: {current_price:.2f}"
            
            # 计算价格变化
            if pos.type == 0:  # 多仓
                price_change = current_price - pos.price_open
            else:  # 空仓
                price_change = pos.price_open - current_price
            
            price_change_info = f"价格变化: {price_change:+.2f}"
        else:
            price_info = "当前价: 获取失败"
            price_change_info = ""
        
        # 显示持仓信息
        position_info = f"\n持仓 {i}:"
        position_info += f"\n  票据: {pos.ticket}"
        position_info += f"\n  品种: {pos.symbol}"
        position_info += f"\n  类型: {position_type}"
        position_info += f"\n  数量: {pos.volume}"
        position_info += f"\n  开仓价: {pos.price_open:.2f}"
        position_info += f"\n  {price_info}"
        if price_change_info:
            position_info += f"\n  {price_change_info}"
        position_info += f"\n  浮动盈亏: {pos.profit:+.2f}"
        position_info += f"\n  开仓时间: {datetime.fromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 如果是DKLL策略，显示当前DL值
        if current_strategy.get_name() == "DKLL策略":
            try:
                # 获取最新K线数据
                rates = mt5.copy_rates_from_pos(pos.symbol, mt5.TIMEFRAME_M5, 0, 100)
                if rates is not None:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    df_with_indicators = strategy_manager.calculate_indicators(df)
                    latest = df_with_indicators.iloc[-1]
                    dl_value = latest.get('DL', 0)
                    
                    if pos.type == 0:  # 多仓
                        if dl_value <= 0:
                            position_info += f"\n  ⚠️ 当前DL值: {dl_value} (建议平仓)"
                        else:
                            position_info += f"\n  ✅ 当前DL值: {dl_value} (持仓有效)"
                    else:  # 空仓
                        if dl_value >= 0:
                            position_info += f"\n  ⚠️ 当前DL值: {dl_value} (建议平仓)"
                        else:
                            position_info += f"\n  ✅ 当前DL值: {dl_value} (持仓有效)"
            except:
                position_info += f"\n  DL值: 计算失败"
        
        print(position_info)
        logger.info(position_info.replace('\n', ' | '))
        total_profit += pos.profit
    
    # 显示总计
    print(f"\n📊 持仓总计:")
    print(f"  总浮动盈亏: {total_profit:+.2f}")
    
    # 如果是DKLL策略，提示手动平仓选项
    if current_strategy.get_name() == "DKLL策略":
        manual_close = input("\n是否手动平仓某个持仓? (输入票据号码，直接回车跳过): ").strip()
        if manual_close.isdigit():
            ticket = int(manual_close)
            # 查找对应的持仓
            target_position = None
            for pos in positions:
                if pos.ticket == ticket:
                    target_position = pos
                    break
            
            if target_position:
                confirm = input(f"确认平仓票据{ticket}? (y/N): ").strip().lower()
                if confirm == 'y':
                    if close_position(ticket, target_position.symbol, "手动平仓", performance_tracker):
                        print("✅ 手动平仓成功！")
                        trade_logger.info(f"手动平仓成功 | 票据: {ticket}")
                    else:
                        print("❌ 手动平仓失败！")
            else:
                print(f"❌ 未找到票据号为 {manual_close} 的持仓")

def strategy_selection_menu(strategy_manager):
    """策略选择菜单"""
    logger.info("用户进入策略选择菜单")
    
    print("\n=== 策略选择菜单 ===")
    strategies = strategy_manager.get_available_strategies()
    
    for i, (key, name) in enumerate(strategies.items(), 1):
        current_mark = " (当前)" if strategy_manager.get_current_strategy().get_name() == name else ""
        print(f"{i}. {name}{current_mark}")
    
    print("0. 返回主菜单")
    
    try:
        choice = input(f"\n请选择策略 (0-{len(strategies)}): ").strip()
        
        if choice == "0":
            return
        
        choice_idx = int(choice) - 1
        strategy_keys = list(strategies.keys())
        
        if 0 <= choice_idx < len(strategy_keys):
            selected_key = strategy_keys[choice_idx]
            if strategy_manager.select_strategy(selected_key):
                print(f"\n✅ 已切换到策略: {strategies[selected_key]}")
                logger.info(f"用户切换策略: {strategies[selected_key]}")
                
                # 显示策略详细信息
                print("\n" + strategy_manager.get_strategy_info())
                
                # 询问是否修改参数
                modify = input("\n是否修改策略参数? (y/N): ").strip().lower()
                if modify == 'y':
                    modify_strategy_params(strategy_manager)
            else:
                print("❌ 策略切换失败")
        else:
            print("❌ 无效选择")
            
    except ValueError:
        print("❌ 请输入有效数字")
    except Exception as e:
        logger.error(f"策略选择出错: {e}")
        print("❌ 策略选择出错")

def modify_strategy_params(strategy_manager):
    """修改策略参数"""
    current_strategy = strategy_manager.get_current_strategy()
    if not current_strategy:
        print("❌ 没有选择策略")
        return
    
    current_params = current_strategy.get_params()
    print(f"\n当前策略参数: {current_params}")
    
    new_params = {}
    for param_name, current_value in current_params.items():
        try:
            new_value = input(f"修改 {param_name} (当前: {current_value}, 直接回车保持不变): ").strip()
            if new_value:
                # 尝试转换为适当的类型
                if isinstance(current_value, int):
                    new_params[param_name] = int(new_value)
                elif isinstance(current_value, float):
                    new_params[param_name] = float(new_value)
                else:
                    new_params[param_name] = new_value
        except ValueError:
            print(f"❌ 参数 {param_name} 格式错误，保持原值")
    
    if new_params:
        current_strategy.set_params(new_params)
        print(f"✅ 参数已更新: {new_params}")
        logger.info(f"策略参数已更新: {new_params}")
    else:
        print("参数未修改")

def view_trading_statistics(performance_tracker):
    """查看交易统计"""
    logger.info("用户查看交易统计")
    
    # 更新最新状态
    performance_tracker.update_positions_from_mt5()
    
    print("\n" + "="*60)
    print("📊 实时交易统计")
    print("="*60)
    
    stats = performance_tracker.get_statistics()
    
    # 基础统计
    print(f"📈 基础数据:")
    print(f"   总交易次数: {stats['total_trades']}")
    print(f"   盈利交易: {stats['winning_trades']} ({stats['win_rate']:.2f}%)")
    print(f"   亏损交易: {stats['losing_trades']}")
    print(f"   平手交易: {stats['breakeven_trades']}")
    
    # 盈亏统计
    print(f"\n💰 盈亏分析:")
    print(f"   总盈亏: {stats['total_profit']:+.2f}")
    print(f"   总盈利: +{stats['gross_profit']:.2f}")
    print(f"   总亏损: -{stats['gross_loss']:.2f}")
    print(f"   盈亏比: {stats['profit_factor']:.2f}")
    print(f"   平均盈利: {stats['avg_profit']:.2f}")
    print(f"   平均亏损: -{stats['avg_loss']:.2f}")
    
    # 账户变化
    print(f"\n🏦 账户变化:")
    print(f"   初始余额: {stats['session_start_balance']:.2f}")
    print(f"   当前余额: {stats['current_balance']:.2f}")
    print(f"   余额变化: {stats['balance_change']:+.2f} ({stats['balance_change_percent']:+.2f}%)")
    
    # 极值统计
    if stats['total_trades'] > 0:
        print(f"\n📊 极值统计:")
        print(f"   最大盈利: +{stats['max_profit']:.2f}")
        print(f"   最大亏损: {stats['max_loss']:.2f}")
        print(f"   最大连续盈利: {stats['max_consecutive_wins']} 次")
        print(f"   最大连续亏损: {stats['max_consecutive_losses']} 次")
        
        avg_duration_str = str(stats['avg_duration']).split('.')[0] if stats['avg_duration'] else "0:00:00"
        print(f"   平均持仓时间: {avg_duration_str}")
    
    # 策略统计
    strategy_stats = performance_tracker.get_strategy_statistics()
    if strategy_stats:
        print(f"\n🎯 策略表现:")
        for strategy, data in strategy_stats.items():
            print(f"   {strategy}: {data['total_trades']}笔 | 胜率{data['win_rate']:.1f}% | 盈亏{data['total_profit']:+.2f}")
    
    # 当前持仓
    if performance_tracker.open_positions:
        print(f"\n📋 当前持仓 ({len(performance_tracker.open_positions)}笔):")
        for ticket, pos in performance_tracker.open_positions.items():
            open_time = pos['open_time'].strftime('%m-%d %H:%M') if isinstance(pos['open_time'], datetime) else str(pos['open_time'])
            current_price = performance_tracker._get_current_price(pos['symbol'])
            if current_price:
                if pos['type'] == 'BUY':
                    unrealized_pnl = (current_price - pos['open_price']) * pos['volume']
                else:
                    unrealized_pnl = (pos['open_price'] - current_price) * pos['volume']
                print(f"   票据{ticket}: {pos['type']} {pos['symbol']} | {open_time} | 开仓价{pos['open_price']:.2f} | 浮动{unrealized_pnl:+.2f}")
            else:
                print(f"   票据{ticket}: {pos['type']} {pos['symbol']} | {open_time} | 开仓价{pos['open_price']:.2f}")
    
    print("="*60)
    
    # 询问是否生成详细报告
    generate_report = input("\n是否生成详细报告并保存到文件? (y/N): ").strip().lower()
    if generate_report == 'y':
        filename = performance_tracker.save_report_to_file()
        if filename:
            print(f"✅ 详细报告已保存到: {filename}")
        else:
            print("❌ 报告保存失败")

def manual_parameter_optimization(strategy_manager, parameter_optimizer):
    """手动参数优化菜单"""
    logger.info("用户进入手动参数优化")
    
    current_strategy = strategy_manager.get_current_strategy()
    print(f"\n🔧 参数优化")
    print(f"当前策略: {current_strategy.get_name()}")
    print(f"当前参数: {current_strategy.get_params()}")
    
    # 设置优化参数
    print(f"\n⚙️ 优化设置:")
    lookback_hours = input("历史数据回望期（小时，默认168=7天）: ").strip()
    try:
        lookback_hours = int(lookback_hours) if lookback_hours else 168
        if lookback_hours < 24:
            print("⚠️ 回望期至少24小时，已设置为24小时")
            lookback_hours = 24
        elif lookback_hours > 720:  # 30天
            print("⚠️ 回望期最多720小时，已设置为720小时")  
            lookback_hours = 720
    except ValueError:
        print("⚠️ 输入无效，使用默认168小时")
        lookback_hours = 168
    
    test_combinations = input("测试参数组合数量（默认30）: ").strip()
    try:
        test_combinations = int(test_combinations) if test_combinations else 30
        if test_combinations < 10:
            print("⚠️ 至少测试10个组合，已设置为10")
            test_combinations = 10
        elif test_combinations > 100:
            print("⚠️ 最多测试100个组合，已设置为100")
            test_combinations = 100
    except ValueError:
        print("⚠️ 输入无效，使用默认30")
        test_combinations = 30
    
    print(f"\n📊 优化配置:")
    print(f"  策略: {current_strategy.get_name()}")
    print(f"  回望期: {lookback_hours} 小时 ({lookback_hours//24} 天)")
    print(f"  测试组合: {test_combinations} 个")
    print(f"  品种: {SYMBOL}")
    
    confirm = input(f"\n确认开始参数优化? (y/N): ").strip().lower()
    if confirm == 'y':
        logger.info(f"用户确认手动参数优化 - 回望期: {lookback_hours}h, 测试组合: {test_combinations}")
        
        # 记录当前参数
        original_params = current_strategy.get_params().copy()
        print(f"\n🔄 开始优化，这可能需要几分钟...")
        
        try:
            # 执行参数优化
            optimized_params = parameter_optimizer.optimize_strategy(
                strategy_name=current_strategy.get_name(),
                symbol=SYMBOL,
                optimization_hours=lookback_hours,
                test_combinations=test_combinations
            )
            
            if optimized_params:
                print(f"\n✅ 参数优化完成！")
                print(f"原始参数: {original_params}")
                print(f"优化参数: {optimized_params}")
                
                # 显示参数对比
                print(f"\n📊 参数变化:")
                for param_name in original_params.keys():
                    old_val = original_params[param_name]
                    new_val = optimized_params[param_name]
                    if new_val > old_val:
                        change = "📈 增大"
                    elif new_val < old_val:
                        change = "📉 减小"
                    else:
                        change = "➡️ 不变"
                    print(f"  {param_name}: {old_val} → {new_val} {change}")
                
                # 询问是否应用新参数
                apply = input(f"\n是否应用优化后的参数? (y/N): ").strip().lower()
                if apply == 'y':
                    current_strategy.set_params(optimized_params)
                    print(f"✅ 新参数已应用！")
                    logger.info(f"手动参数优化完成并应用: {optimized_params}")
                    trade_logger.info(f"手动参数优化 | 策略: {current_strategy.get_name()} | 原参数: {original_params} | 新参数: {optimized_params}")
                else:
                    print(f"参数未应用，保持原始设置")
                    logger.info("用户选择不应用优化参数")
            else:
                print(f"❌ 参数优化失败，保持原始参数")
                logger.warning("参数优化失败")
                
        except Exception as e:
            logger.error(f"参数优化过程中发生错误: {e}")
            print(f"❌ 优化过程出错: {e}")
    else:
        logger.info("用户取消手动参数优化")
        print("已取消参数优化")
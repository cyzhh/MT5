"""
系统诊断功能
"""
import logging
import time
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5
from config.settings import SYMBOL
from trading.mt5_connector import check_connection_status, get_symbol_info, get_real_time_price

logger = logging.getLogger('MT5_Trading')

def diagnose_system(strategy_manager):
    """系统诊断功能"""
    logger.info("开始系统诊断...")
    print("\n=== 系统诊断 ===")
    
    # 1. 检查MT5连接
    print("1. 检查MT5连接状态...")
    if check_connection_status():
        print("   ✅ MT5连接正常")
    else:
        print("   ❌ MT5连接异常")
        return
    
    # 2. 检查交易品种
    print(f"2. 检查交易品种 {SYMBOL}...")
    symbol_info = get_symbol_info(SYMBOL)
    if symbol_info:
        print(f"   ✅ 品种信息正常")
        print(f"   - 可见: {symbol_info.visible}")
        print(f"   - 交易模式: {symbol_info.trade_mode}")
        print(f"   - 点差: {symbol_info.spread}")
        print(f"   - 最小交易量: {symbol_info.volume_min}")
    else:
        print(f"   ❌ 无法获取品种信息")
        return
    
    # 3. 检查实时价格
    print("3. 检查实时价格...")
    tick = get_real_time_price(SYMBOL)
    if tick:
        print(f"   ✅ 价格获取正常")
        print(f"   - Bid: {tick.bid}")
        print(f"   - Ask: {tick.ask}")
        print(f"   - 时间: {datetime.fromtimestamp(tick.time)}")
    else:
        print("   ❌ 无法获取实时价格")
        # 提供可能的解决方案
        print("\n可能的解决方案：")
        print("- 检查网络连接")
        print("- 确认当前是交易时间")
        print("- 重启MT5终端")
        print("- 检查服务器连接")
        return
    
    # 4. 检查历史数据
    print("4. 检查历史数据...")
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 10)
    if rates is not None and len(rates) > 0:
        print(f"   ✅ 历史数据正常，获取到 {len(rates)} 根K线")
        latest_time = pd.to_datetime(rates[-1]['time'], unit='s')
        print(f"   - 最新K线时间: {latest_time}")
    else:
        print("   ❌ 无法获取历史数据")
        return
    
    # 5. 检查账户信息
    print("5. 检查账户信息...")
    account_info = mt5.account_info()
    if account_info:
        print("   ✅ 账户信息正常")
        print(f"   - 余额: {account_info.balance}")
        print(f"   - 净值: {account_info.equity}")
        print(f"   - 可用保证金: {account_info.margin_free}")
        print(f"   - 交易允许: {account_info.trade_allowed}")
    else:
        print("   ❌ 无法获取账户信息")
        return
    
    # 6. 检查策略状态
    print("6. 检查策略状态...")
    current_strategy = strategy_manager.get_current_strategy()
    if current_strategy:
        print(f"   ✅ 当前策略: {current_strategy.get_name()}")
        
        # 测试策略计算
        try:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df_with_indicators = strategy_manager.calculate_indicators(df)
            signal = strategy_manager.generate_signal(df_with_indicators, verbose=False)
            print(f"   ✅ 策略计算正常，当前信号: {signal if signal else '无信号'}")
        except Exception as e:
            print(f"   ❌ 策略计算异常: {e}")
            return
    else:
        print("   ❌ 没有选择策略")
        return
    
    # 7. 检查市场时间
    print("7. 检查市场时间...")
    now = datetime.now()
    weekday = now.weekday()
    hour = now.hour
    
    if weekday >= 5:  # 周六或周日
        print("   ⚠️  当前是周末，外汇市场休市")
    elif hour < 6 or hour > 23:  # 简单的时间检查
        print("   ⚠️  当前可能不是主要交易时间")
    else:
        print("   ✅ 当前是正常交易时间")
    
    print("\n=== 诊断完成 ===")
    print("如果所有项目都显示✅，系统应该可以正常运行")
    
    # 询问是否进行连接测试
    test_connection = input("\n是否进行实时连接测试? (y/N): ").strip().lower()
    if test_connection == 'y':
        print("\n开始10次连续价格获取测试...")
        success_count = 0
        for i in range(10):
            tick = get_real_time_price(SYMBOL, max_retries=1)
            if tick:
                success_count += 1
                print(f"  测试 {i+1}/10: ✅ {tick.bid}")
            else:
                print(f"  测试 {i+1}/10: ❌ 失败")
            time.sleep(1)
        
        print(f"\n连接测试结果: {success_count}/10 次成功")
        if success_count >= 8:
            print("✅ 连接质量良好")
        elif success_count >= 5:
            print("⚠️ 连接质量一般，可能存在网络波动")
        else:
            print("❌ 连接质量较差，建议检查网络或重启MT5")
"""
MT5智能交易系统主程序
"""
import logging
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5

# 导入配置
from config.settings import SYMBOL
from config.logging_config import setup_logging

# 导入核心模块
from trading.mt5_connector import initialize_mt5, check_auto_trading, shutdown_mt5
from strategies.manager import StrategyManager
from analysis.performance_tracker import TradingPerformanceTracker
from analysis.optimizer import ParameterOptimizer
from ui.menu import main_menu

# 全局日志记录器
logger = None
trade_logger = None

def cleanup_and_generate_final_report(performance_tracker):
    """清理和生成最终报告"""
    logger.info("开始程序清理和最终报告生成...")
    
    try:
        # 更新最终交易状态
        performance_tracker.update_positions_from_mt5()
        
        # 生成最终报告
        print("\n" + "="*60)
        print("📋 生成最终交易报告...")
        print("="*60)
        
        stats = performance_tracker.get_statistics()
        
        if stats['total_trades'] > 0:
            # 显示会话总结
            session_duration = datetime.now() - performance_tracker.session_start_time
            print(f"\n📊 交易会话总结:")
            print(f"   会话时长: {str(session_duration).split('.')[0]}")
            print(f"   总交易: {stats['total_trades']} 笔")
            print(f"   胜率: {stats['win_rate']:.2f}%")
            print(f"   总盈亏: {stats['total_profit']:+.2f}")
            print(f"   余额变化: {stats['balance_change']:+.2f} ({stats['balance_change_percent']:+.2f}%)")
            print(f"   盈亏比: {stats['profit_factor']:.2f}")
            
            # 自动保存详细报告
            filename = performance_tracker.save_report_to_file()
            if filename:
                print(f"\n✅ 详细交易报告已自动保存到: {filename}")
                logger.info(f"最终交易报告已保存: {filename}")
            else:
                print("\n❌ 报告保存失败")
                
            # 记录到交易日志
            trade_logger.info("="*50)
            trade_logger.info("交易会话结束")
            trade_logger.info(f"会话时长: {str(session_duration).split('.')[0]}")
            trade_logger.info(f"总交易: {stats['total_trades']} 笔")
            trade_logger.info(f"胜率: {stats['win_rate']:.2f}%")
            trade_logger.info(f"总盈亏: {stats['total_profit']:+.2f}")
            trade_logger.info(f"余额变化: {stats['balance_change']:+.2f}")
            trade_logger.info("="*50)
            
        else:
            print("\n📝 本次会话没有进行任何交易")
            logger.info("交易会话结束 - 无交易记录")
            
    except Exception as e:
        logger.error(f"生成最终报告时发生错误: {e}")
        print(f"\n❌ 生成最终报告时发生错误: {e}")
    
    finally:
        logger.info("关闭MT5连接")
        shutdown_mt5()

def main():
    """主函数"""
    global logger, trade_logger
    
    # 初始化日志系统
    logger, trade_logger = setup_logging()
    
    # 初始化MT5连接
    if not initialize_mt5():
        logger.error("MT5初始化失败，程序退出")
        return
    
    # 检查自动交易状态
    if not check_auto_trading():
        logger.error("自动交易未启用，程序退出")
        shutdown_mt5()
        return
    
    # 获取历史数据用于指标计算
    try:
        logger.info(f"开始获取{SYMBOL}的历史数据...")
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 1000)
        if rates is None:
            logger.error(f"无法获取{SYMBOL}的历史数据")
            shutdown_mt5()
            return
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        logger.info(f"成功获取{len(df)}根K线数据")
        
        # 创建核心组件
        strategy_manager = StrategyManager()
        performance_tracker = TradingPerformanceTracker()
        parameter_optimizer = ParameterOptimizer()
        
        # 显示当前策略信息
        current_strategy = strategy_manager.get_current_strategy()
        logger.info(f"当前策略: {current_strategy.get_name()}")
        logger.info(f"策略描述: {current_strategy.get_description()}")
        
        # 显示交易会话开始信息
        print(f"\n🚀 MT5智能交易系统启动")
        print(f"版本: v2.1 (支持多币种交易和钉钉通知)")
        print(f"时间: {performance_tracker.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"初始余额: {performance_tracker.session_start_balance:.2f}")
        print(f"默认品种: {SYMBOL}")
        print(f"当前策略: {current_strategy.get_name()}")
        print(f"策略参数: {current_strategy.get_params()}")
        
        print(f"\n🔧 新功能:")
        print(f"  ✅ 多币种交易支持")
        print(f"  ✅ 钉钉实时通知")
        print(f"  ✅ 智能资金管理")
        print(f"  ✅ 全自动化交易")
        print(f"  ✅ 定时参数优化")
        print(f"  ✅ DKLL策略无止盈止损")
        
        if current_strategy.get_name() == "DKLL策略":
            print(f"\n🔔 当前策略特点:")
            print(f"  - 不使用止盈止损")
            print(f"  - 完全依靠信号平仓")
            print(f"  - 开仓: DL=±2")
            print(f"  - 平仓: 多仓DL≤0, 空仓DL≥0")
        
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        shutdown_mt5()
        return
    
    # 启动主程序循环
    try:
        while True:
            # 显示主菜单
            if not main_menu(strategy_manager, performance_tracker, parameter_optimizer):
                break
            
            # 询问是否继续
            continue_choice = input("\n是否继续使用程序? (y/N): ").strip().lower()
            if continue_choice != 'y':
                break
                
    except Exception as e:
        logger.error(f"主程序异常: {e}", exc_info=True)
    finally:
        # 程序退出时生成最终统计报告
        cleanup_and_generate_final_report(performance_tracker)
        logger.info("程序结束")
        logger.info("="*60)

if __name__ == "__main__":
    main()
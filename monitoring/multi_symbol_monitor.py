"""
多币种监控模块
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import MetaTrader5 as mt5
from config.settings import SIGNAL_CHECK_INTERVAL, PRICE_UPDATE_INTERVAL
from trading.mt5_connector import get_real_time_price, check_connection_status
from trading.order_manager import place_order, close_position
from trading.position_manager import get_positions, check_signal_with_positions
from trading.money_manager import MoneyManager
from notifications.dingtalk import DingTalkNotifier

logger = logging.getLogger('MultiSymbolMonitor')

class MultiSymbolMonitor:
    """多币种监控器"""
    
    def __init__(self, strategy_manager, performance_tracker, notifier: Optional[DingTalkNotifier] = None):
        self.strategy_manager = strategy_manager
        self.performance_tracker = performance_tracker
        self.money_manager = MoneyManager()
        self.notifier = notifier
        self.logger = logging.getLogger('MultiSymbolMonitor')
        
        # 为每个币种存储状态
        self.symbol_states = {}
        self.last_signal_check = {}
        self.cached_data = {}
        
        # 初始化每个币种的状态
        for symbol in self.money_manager.get_enabled_symbols():
            self.symbol_states[symbol] = {
                'last_price': None,
                'last_signal': None,
                'error_count': 0
            }
            self.last_signal_check[symbol] = datetime.now()
    
    def run_multi_symbol_monitoring(self):
        """运行多币种监控"""
        self.logger.info("开始多币种监控...")
        enabled_symbols = self.money_manager.get_enabled_symbols()
        
        print("🌐 多币种监控模式启动")
        print("按 Ctrl+C 停止监控")
        print(f"监控币种: {', '.join(enabled_symbols)}")
        
        # 显示资金分配
        allocation = self.money_manager.get_account_allocation_status()
        print("\n📊 资金分配:")
        for symbol, config in self.money_manager.symbols_config.items():
            if config['enabled']:
                print(f"  {symbol}: {config['position_ratio']:.0%} (策略: {config['strategy']})")
        
        last_status_log = datetime.now()
        last_risk_check = datetime.now()
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                now = datetime.now()
                
                # 检查每个币种
                for symbol in enabled_symbols:
                    try:
                        # 获取实时价格
                        tick = get_real_time_price(symbol)
                        if tick:
                            self.symbol_states[symbol]['last_price'] = tick.bid
                            self.symbol_states[symbol]['error_count'] = 0
                        else:
                            self.symbol_states[symbol]['error_count'] += 1
                            continue
                        
                        # 检查是否需要进行信号检查
                        if (now - self.last_signal_check[symbol]).total_seconds() >= SIGNAL_CHECK_INTERVAL:
                            self._check_symbol_signal(symbol)
                            self.last_signal_check[symbol] = now
                        
                    except Exception as e:
                        self.logger.error(f"{symbol} 处理异常: {e}")
                        self.symbol_states[symbol]['error_count'] += 1
                
                # 显示状态
                self._display_multi_symbol_status(cycle_count)
                
                # 定期风险检查（每分钟）
                if (now - last_risk_check).total_seconds() >= 60:
                    self._check_portfolio_risk()
                    last_risk_check = now
                
                # 定期详细日志（每5分钟）
                if (now - last_status_log).total_seconds() >= 300:
                    self._log_detailed_status()
                    last_status_log = now
                
                time.sleep(PRICE_UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("多币种监控被用户停止")
            print(f"\n监控结束，共执行 {cycle_count} 个监控周期")
            
            # 显示最终统计
            self._show_final_statistics()
    
    def _check_symbol_signal(self, symbol: str):
        """检查指定币种的交易信号"""
        config = self.money_manager.get_symbol_config(symbol)
        if not config:
            return
        
        # 切换到对应的策略
        original_strategy = self.strategy_manager.get_current_strategy()
        strategy_key = config['strategy']
        
        if not self.strategy_manager.select_strategy(strategy_key):
            self.logger.error(f"无法切换到策略 {strategy_key} for {symbol}")
            return
        
        try:
            # 获取K线数据
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if rates is None:
                self.logger.error(f"无法获取 {symbol} 的K线数据")
                return
            
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # 缓存数据
            self.cached_data[symbol] = df
            
            # 获取当前持仓
            current_positions = get_positions(symbol)
            
            # 检查信号
            signal, close_orders = check_signal_with_positions(
                df, current_positions, self.strategy_manager, verbose=True
            )
            
            # 处理平仓信号
            if close_orders:
                for close_order in close_orders:
                    self._handle_close_order(symbol, close_order)
            
            # 处理开仓信号
            elif signal and len(current_positions) == 0:
                self._handle_open_signal(symbol, signal, config)
            
            # 记录信号状态
            self.symbol_states[symbol]['last_signal'] = signal
            
        finally:
            # 恢复原策略
            self.strategy_manager.current_strategy = original_strategy
    
    def _handle_open_signal(self, symbol: str, signal: str, config: Dict):
        """处理开仓信号"""
        # 检查是否可以开仓
        can_open, reason = self.money_manager.check_position_limits(symbol)
        if not can_open:
            self.logger.warning(f"{symbol} 无法开仓: {reason}")
            return
        
        # 获取账户信息
        account_info = mt5.account_info()
        if not account_info:
            return
        
        # 计算交易量
        volume = self.money_manager.calculate_position_size(symbol, account_info.balance)
        if volume <= 0:
            self.logger.warning(f"{symbol} 计算的交易量为0")
            return
        
        # 确保不超过配置的交易量
        volume = min(volume, config['volume_per_trade'])
        
        self.logger.info(f"🚨 {symbol} 检测到{signal}信号，准备下单！")
        
        # 执行下单
        if place_order(symbol, signal, volume, self.strategy_manager, self.performance_tracker):
            self.logger.info(f"✅ {symbol} {signal}订单成功！")
            
            # 发送钉钉通知
            if self.notifier:
                self.notifier.send_trade_notification({
                    'action': '开仓成功',
                    'symbol': symbol,
                    'direction': signal,
                    'price': self.symbol_states[symbol]['last_price'],
                    'volume': volume,
                    'strategy': config['strategy'],
                    'balance': account_info.balance,
                    'equity': account_info.equity
                })
        else:
            self.logger.error(f"❌ {symbol} {signal}下单失败！")
            
            # 发送错误通知
            if self.notifier:
                self.notifier.send_error_notification({
                    'type': '下单失败',
                    'symbol': symbol,
                    'message': f'{signal}信号下单失败',
                    'suggestion': '请检查账户余额和交易权限'
                })
    
    def _handle_close_order(self, symbol: str, close_order: Dict):
        """处理平仓订单"""
        self.logger.info(f"🔻 {symbol} 执行平仓: {close_order['reason']}")
        
        # 获取持仓信息用于通知
        position = None
        positions = mt5.positions_get(ticket=close_order['ticket'])
        if positions and len(positions) > 0:
            position = positions[0]
        
        if close_position(close_order['ticket'], symbol, close_order['reason'], self.performance_tracker):
            self.logger.info(f"✅ {symbol} 平仓成功: 票据{close_order['ticket']}")
            
            # 发送钉钉通知
            if self.notifier and position:
                self.notifier.send_trade_notification({
                    'action': '平仓成功',
                    'symbol': symbol,
                    'direction': 'SELL' if position.type == 0 else 'BUY',
                    'price': self.symbol_states[symbol]['last_price'],
                    'volume': position.volume,
                    'profit': position.profit,
                    'reason': close_order['reason'],
                    'strategy': self.money_manager.get_symbol_config(symbol)['strategy']
                })
        else:
            self.logger.error(f"❌ {symbol} 平仓失败: 票据{close_order['ticket']}")
    
    def _check_portfolio_risk(self):
        """检查整体风险"""
        risk_summary = self.money_manager.get_risk_summary()
        
        if risk_summary.get('risk_status') != 'NORMAL':
            self.logger.warning(f"风险警告: {risk_summary['risk_status']}")
            for warning in risk_summary.get('warnings', []):
                self.logger.warning(f"  - {warning}")
            
            # 发送风险警告
            if self.notifier and risk_summary.get('warnings'):
                self.notifier.send_error_notification({
                    'type': '风险警告',
                    'message': '\n'.join(risk_summary['warnings']),
                    'suggestion': '建议检查持仓并考虑减仓'
                })
        
        # 检查每个持仓是否需要风控平仓
        all_positions = mt5.positions_get()
        if all_positions:
            for position in all_positions:
                should_close, reason = self.money_manager.should_close_position(position)
                if should_close:
                    self.logger.warning(f"风控平仓: {position.symbol} - {reason}")
                    close_position(position.ticket, position.symbol, f"风控: {reason}", self.performance_tracker)
    
    def _display_multi_symbol_status(self, cycle_count: int):
        """显示多币种状态"""
        status_parts = [f"🌐 周期:{cycle_count}"]
        
        # 账户信息
        account_info = mt5.account_info()
        if account_info:
            status_parts.append(f"余额:{account_info.balance:.2f}")
            status_parts.append(f"净值:{account_info.equity:.2f}")
        
        # 各币种状态
        for symbol in self.money_manager.get_enabled_symbols():
            state = self.symbol_states[symbol]
            price = state['last_price']
            
            if price:
                positions = get_positions(symbol)
                pos_count = len(positions) if positions else 0
                
                # 获取策略信息
                config = self.money_manager.get_symbol_config(symbol)
                
                symbol_status = f"{symbol}:{price:.2f}"
                if pos_count > 0:
                    symbol_status += f"({pos_count}仓)"
                
                status_parts.append(symbol_status)
            else:
                status_parts.append(f"{symbol}:--")
        
        # 显示状态
        print(f"\r{' | '.join(status_parts)}", end="")
    
    def _log_detailed_status(self):
        """记录详细状态"""
        self.logger.info("="*60)
        self.logger.info("多币种监控详细状态")
        
        # 账户状态
        allocation = self.money_manager.get_account_allocation_status()
        self.logger.info(f"账户余额: {allocation.get('total_balance', 0):.2f}")
        self.logger.info(f"账户净值: {allocation.get('total_equity', 0):.2f}")
        
        # 各币种状态
        for symbol, status in allocation.get('symbols', {}).items():
            self.logger.info(f"{symbol}:")
            self.logger.info(f"  分配资金: {status['allocated_balance']:.2f} ({status['position_ratio']:.0%})")
            self.logger.info(f"  持仓: {status['current_positions']}/{status['max_positions']}")
            self.logger.info(f"  持仓量: {status['current_volume']}/{status['max_volume']}")
            self.logger.info(f"  浮动盈亏: {status['current_profit']:+.2f}")
            self.logger.info(f"  利用率: {status['utilization']:.1f}%")
        
        # 风险状态
        risk_summary = self.money_manager.get_risk_summary()
        self.logger.info(f"风险状态: {risk_summary.get('risk_status', 'UNKNOWN')}")
        self.logger.info("="*60)
    
    def _show_final_statistics(self):
        """显示最终统计"""
        print("\n" + "="*60)
        print("📊 多币种交易统计")
        print("="*60)
        
        # 更新统计
        self.performance_tracker.update_positions_from_mt5()
        
        # 整体统计
        overall_stats = self.performance_tracker.get_statistics()
        print(f"\n整体表现:")
        print(f"  总交易: {overall_stats['total_trades']} 笔")
        print(f"  胜率: {overall_stats['win_rate']:.1f}%")
        print(f"  总盈亏: {overall_stats['total_profit']:+.2f}")
        print(f"  余额变化: {overall_stats['balance_change']:+.2f} ({overall_stats['balance_change_percent']:+.1f}%)")
        
        # 各币种统计
        print(f"\n各币种表现:")
        for symbol in self.money_manager.get_enabled_symbols():
            # 这里可以添加更详细的分币种统计
            positions = get_positions(symbol)
            if positions:
                total_profit = sum(pos.profit for pos in positions)
                print(f"  {symbol}: {len(positions)}个持仓, 浮动盈亏: {total_profit:+.2f}")
        
        # 资金利用情况
        allocation = self.money_manager.get_account_allocation_status()
        print(f"\n资金利用:")
        for symbol, status in allocation.get('symbols', {}).items():
            print(f"  {symbol}: 利用率 {status['utilization']:.1f}%")
        
        print("="*60)
        
        # 发送每日报告（如果需要）
        if self.notifier:
            self._send_daily_report()
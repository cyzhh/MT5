"""
交易表现统计跟踪器
"""
import logging
import os
from datetime import datetime, timedelta
import MetaTrader5 as mt5

class TradingPerformanceTracker:
    """交易表现统计跟踪器"""
    
    def __init__(self):
        self.trades = []  # 所有交易记录
        self.open_positions = {}  # 当前开仓记录
        self.session_start_time = datetime.now()
        self.session_start_balance = 0
        self.logger = logging.getLogger('PerformanceTracker')
        
        # 初始化账户余额
        self._update_initial_balance()
        
    def _update_initial_balance(self):
        """更新初始余额"""
        try:
            account_info = mt5.account_info()
            if account_info:
                self.session_start_balance = account_info.balance
                self.logger.info(f"交易会话开始，初始余额: {self.session_start_balance:.2f}")
        except Exception as e:
            self.logger.error(f"获取初始余额失败: {e}")
            self.session_start_balance = 0
    
    def record_order_open(self, ticket, symbol, order_type, volume, open_price, strategy_name, open_time=None):
        """记录开仓"""
        if open_time is None:
            open_time = datetime.now()
            
        trade_record = {
            'ticket': ticket,
            'symbol': symbol,
            'type': 'BUY' if order_type == mt5.ORDER_TYPE_BUY else 'SELL',
            'volume': volume,
            'open_price': open_price,
            'open_time': open_time,
            'strategy': strategy_name,
            'status': 'OPEN'
        }
        
        self.open_positions[ticket] = trade_record
        self.logger.info(f"记录开仓: 票据{ticket}, {trade_record['type']}, 数量{volume}, 价格{open_price}")
    
    def record_order_close(self, ticket, close_price, close_time=None, profit=None):
        """记录平仓"""
        if close_time is None:
            close_time = datetime.now()
            
        if ticket in self.open_positions:
            trade_record = self.open_positions[ticket].copy()
            trade_record['close_price'] = close_price
            trade_record['close_time'] = close_time
            trade_record['status'] = 'CLOSED'
            
            # 计算持续时间
            if isinstance(trade_record['open_time'], datetime) and isinstance(close_time, datetime):
                trade_record['duration'] = close_time - trade_record['open_time']
            else:
                trade_record['duration'] = timedelta(0)
            
            # 计算盈亏
            if profit is not None:
                trade_record['profit'] = profit
            else:
                # 简单计算（实际应该考虑点值等因素）
                if trade_record['type'] == 'BUY':
                    trade_record['profit'] = (close_price - trade_record['open_price']) * trade_record['volume']
                else:
                    trade_record['profit'] = (trade_record['open_price'] - close_price) * trade_record['volume']
            
            # 移动到已完成交易
            self.trades.append(trade_record)
            del self.open_positions[ticket]
            
            self.logger.info(f"记录平仓: 票据{ticket}, 平仓价{close_price}, 盈亏{trade_record['profit']:.2f}")
        else:
            self.logger.warning(f"未找到开仓记录: 票据{ticket}")
    
    def update_positions_from_mt5(self):
        """从MT5更新持仓状态"""
        try:
            # 获取当前MT5持仓
            current_positions = mt5.positions_get()
            current_tickets = {pos.ticket for pos in current_positions} if current_positions else set()
            
            # 检查已平仓的订单
            closed_tickets = []
            for ticket in self.open_positions.keys():
                if ticket not in current_tickets:
                    closed_tickets.append(ticket)
            
            # 处理已平仓的订单
            for ticket in closed_tickets:
                # 尝试从历史中获取平仓信息
                history_deals = mt5.history_deals_get(ticket=ticket)
                if history_deals:
                    for deal in history_deals:
                        if deal.entry == mt5.DEAL_ENTRY_OUT:  # 平仓交易
                            self.record_order_close(
                                ticket=ticket,
                                close_price=deal.price,
                                close_time=datetime.fromtimestamp(deal.time),
                                profit=deal.profit
                            )
                            break
                else:
                    # 如果无法获取历史记录，使用当前价格估算
                    self.logger.warning(f"无法获取票据{ticket}的平仓历史，使用估算")
                    current_price = self._get_current_price(self.open_positions[ticket]['symbol'])
                    if current_price:
                        self.record_order_close(ticket, current_price)
                    else:
                        # 强制平仓记录
                        self.record_order_close(ticket, self.open_positions[ticket]['open_price'])
            
        except Exception as e:
            self.logger.error(f"更新持仓状态失败: {e}")
    
    def _get_current_price(self, symbol):
        """获取当前价格"""
        try:
            tick = mt5.symbol_info_tick(symbol)
            return tick.bid if tick else None
        except:
            return None
    
    def get_statistics(self):
        """计算交易统计"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'avg_profit': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'max_profit': 0,
                'max_loss': 0,
                'avg_duration': timedelta(0),
                'current_balance': self.session_start_balance,
                'balance_change': 0
            }
        
        # 基础统计
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t['profit'] > 0]
        losing_trades = [t for t in self.trades if t['profit'] < 0]
        breakeven_trades = [t for t in self.trades if t['profit'] == 0]
        
        # 盈亏统计
        total_profit = sum(t['profit'] for t in self.trades)
        gross_profit = sum(t['profit'] for t in winning_trades)
        gross_loss = abs(sum(t['profit'] for t in losing_trades))
        
        # 计算各种比率
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        avg_profit = gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = gross_loss / len(losing_trades) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # 最大值统计
        max_profit = max([t['profit'] for t in self.trades]) if self.trades else 0
        max_loss = min([t['profit'] for t in self.trades]) if self.trades else 0
        
        # 时间统计
        durations = [t['duration'] for t in self.trades if 'duration' in t]
        avg_duration = sum(durations, timedelta(0)) / len(durations) if durations else timedelta(0)
        
        # 连续盈亏统计
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_stats()
        
        # 当前余额
        try:
            account_info = mt5.account_info()
            current_balance = account_info.balance if account_info else self.session_start_balance
        except:
            current_balance = self.session_start_balance
        
        balance_change = current_balance - self.session_start_balance
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'breakeven_trades': len(breakeven_trades),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'avg_duration': avg_duration,
            'max_consecutive_wins': max_consecutive_wins,
            'max_consecutive_losses': max_consecutive_losses,
            'session_start_balance': self.session_start_balance,
            'current_balance': current_balance,
            'balance_change': balance_change,
            'balance_change_percent': (balance_change / self.session_start_balance * 100) if self.session_start_balance > 0 else 0
        }
    
    def _calculate_consecutive_stats(self):
        """计算连续盈亏统计"""
        if not self.trades:
            return 0, 0
        
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_consecutive_wins = 0
        current_consecutive_losses = 0
        
        for trade in self.trades:
            if trade['profit'] > 0:
                current_consecutive_wins += 1
                current_consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_consecutive_wins)
            elif trade['profit'] < 0:
                current_consecutive_losses += 1
                current_consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
            else:  # breakeven
                current_consecutive_wins = 0
                current_consecutive_losses = 0
        
        return max_consecutive_wins, max_consecutive_losses
    
    def get_strategy_statistics(self):
        """按策略分组的统计"""
        strategy_stats = {}
        
        for trade in self.trades:
            strategy = trade.get('strategy', 'Unknown')
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': [],
                    'total_profit': 0,
                    'wins': 0,
                    'losses': 0
                }
            
            strategy_stats[strategy]['trades'].append(trade)
            strategy_stats[strategy]['total_profit'] += trade['profit']
            if trade['profit'] > 0:
                strategy_stats[strategy]['wins'] += 1
            elif trade['profit'] < 0:
                strategy_stats[strategy]['losses'] += 1
        
        # 计算每个策略的胜率
        for strategy, stats in strategy_stats.items():
            total = len(stats['trades'])
            stats['win_rate'] = (stats['wins'] / total * 100) if total > 0 else 0
            stats['total_trades'] = total
        
        return strategy_stats
    
    def generate_report(self):
        """生成详细报告"""
        self.update_positions_from_mt5()  # 更新最新状态
        
        stats = self.get_statistics()
        strategy_stats = self.get_strategy_statistics()
        
        report = []
        report.append("=" * 80)
        report.append("交易表现统计报告")
        report.append("=" * 80)
        report.append(f"会话开始时间: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"会话结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"会话持续时间: {datetime.now() - self.session_start_time}")
        report.append("")
        
        # 基础统计
        report.append("📊 基础统计")
        report.append("-" * 40)
        report.append(f"总交易次数: {stats['total_trades']}")
        report.append(f"盈利交易: {stats['winning_trades']}")
        report.append(f"亏损交易: {stats['losing_trades']}")
        report.append(f"平手交易: {stats['breakeven_trades']}")
        report.append(f"胜率: {stats['win_rate']:.2f}%")
        report.append("")
        
        # 盈亏统计
        report.append("💰 盈亏统计")
        report.append("-" * 40)
        report.append(f"总盈亏: {stats['total_profit']:.2f}")
        report.append(f"总盈利: {stats['gross_profit']:.2f}")
        report.append(f"总亏损: -{stats['gross_loss']:.2f}")
        report.append(f"平均盈利: {stats['avg_profit']:.2f}")
        report.append(f"平均亏损: -{stats['avg_loss']:.2f}")
        report.append(f"盈亏比: {stats['profit_factor']:.2f}")
        report.append(f"最大单笔盈利: {stats['max_profit']:.2f}")
        report.append(f"最大单笔亏损: {stats['max_loss']:.2f}")
        report.append("")
        
        # 账户统计
        report.append("🏦 账户统计")
        report.append("-" * 40)
        report.append(f"初始余额: {stats['session_start_balance']:.2f}")
        report.append(f"当前余额: {stats['current_balance']:.2f}")
        report.append(f"余额变化: {stats['balance_change']:+.2f} ({stats['balance_change_percent']:+.2f}%)")
        report.append("")
        
        # 时间统计
        report.append("⏱️ 时间统计")
        report.append("-" * 40)
        avg_duration_str = str(stats['avg_duration']).split('.')[0] if stats['avg_duration'] else "0:00:00"
        report.append(f"平均持仓时间: {avg_duration_str}")
        report.append(f"最大连续盈利: {stats['max_consecutive_wins']} 次")
        report.append(f"最大连续亏损: {stats['max_consecutive_losses']} 次")
        report.append("")
        
        # 策略统计
        if strategy_stats:
            report.append("🎯 策略表现")
            report.append("-" * 40)
            for strategy, stats_data in strategy_stats.items():
                report.append(f"{strategy}:")
                report.append(f"  交易次数: {stats_data['total_trades']}")
                report.append(f"  胜率: {stats_data['win_rate']:.2f}%")
                report.append(f"  总盈亏: {stats_data['total_profit']:.2f}")
                report.append("")
        
        # 详细交易记录
        if self.trades:
            report.append("📋 详细交易记录")
            report.append("-" * 40)
            for i, trade in enumerate(self.trades[-10:], 1):  # 只显示最近10笔
                open_time = trade['open_time'].strftime('%m-%d %H:%M') if isinstance(trade['open_time'], datetime) else str(trade['open_time'])
                close_time = trade['close_time'].strftime('%m-%d %H:%M') if isinstance(trade['close_time'], datetime) else str(trade['close_time'])
                duration = str(trade.get('duration', timedelta(0))).split('.')[0]
                profit_symbol = "+" if trade['profit'] >= 0 else ""
                
                report.append(f"{len(self.trades)-10+i:2d}. {trade['type']} {trade['symbol']} | "
                            f"{open_time}-{close_time} ({duration}) | "
                            f"{profit_symbol}{trade['profit']:.2f} | {trade['strategy']}")
            
            if len(self.trades) > 10:
                report.append(f"... 还有 {len(self.trades)-10} 笔历史交易")
        
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report_to_file(self):
        """保存报告到文件"""
        try:
            from config.settings import LOG_DIR
            log_dir = LOG_DIR
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{log_dir}/trading_performance_{timestamp}.txt"
            
            report = self.generate_report()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            self.logger.info(f"交易报告已保存到: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"保存报告失败: {e}")
            return None
    
    def print_summary(self):
        """打印简要统计"""
        stats = self.get_statistics()
        print(f"\n📊 当前会话统计:")
        print(f"交易次数: {stats['total_trades']} | 胜率: {stats['win_rate']:.1f}% | "
              f"总盈亏: {stats['total_profit']:+.2f} | 余额变化: {stats['balance_change']:+.2f}")
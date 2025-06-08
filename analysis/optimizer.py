"""
策略参数优化器
"""
import logging
import os
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
from config.settings import LOG_DIR
from strategies.ma_strategy import MAStrategy
from strategies.dkll_strategy import DKLLStrategy
from strategies.rsi_strategy import RSIStrategy

class ParameterOptimizer:
    """策略参数优化器"""
    
    def __init__(self):
        self.logger = logging.getLogger('ParameterOptimizer')
        
        # 定义各策略的参数范围
        self.parameter_ranges = {
            "双均线策略": {
                'ma_short': (5, 20),   # 短周期范围
                'ma_long': (10, 50)    # 长周期范围
            },
            "DKLL策略": {
                'n_str': (10, 30),     # DK强弱周期
                'n_A1': (5, 20),       # A1加权平均周期
                'n_A2': (10, 30),      # A2简单平均周期
                'n_LL': (10, 30)       # LL力量周期
            },
            "RSI策略": {
                'rsi_period': (10, 25),    # RSI周期
                'oversold': (20, 35),      # 超卖线
                'overbought': (65, 80)     # 超买线
            }
        }
    
    def optimize_strategy(self, strategy_name: str, symbol: str, optimization_hours: int = 24, test_combinations: int = 20):
        """优化策略参数
        
        Args:
            strategy_name: 策略名称
            symbol: 交易品种
            optimization_hours: 用于优化的历史数据小时数
            test_combinations: 测试的参数组合数量
        """
        self.logger.info(f"开始优化策略: {strategy_name}")
        
        if strategy_name not in self.parameter_ranges:
            self.logger.error(f"策略 {strategy_name} 没有定义参数范围")
            return None
        
        # 获取历史数据
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, optimization_hours * 12)  # 5分钟K线，12根/小时
        if rates is None:
            self.logger.error("无法获取历史数据进行优化")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        self.logger.info(f"获取到 {len(df)} 根K线数据用于优化")
        
        # 生成测试参数组合
        param_combinations = self._generate_parameter_combinations(strategy_name, test_combinations)
        
        best_params = None
        best_score = float('-inf')
        best_stats = None
        
        results = []
        
        self.logger.info(f"开始测试 {len(param_combinations)} 个参数组合...")
        
        for i, params in enumerate(param_combinations, 1):
            try:
                # 创建临时策略实例进行测试
                temp_strategy = self._create_strategy_instance(strategy_name, params)
                if temp_strategy is None:
                    continue
                
                # 回测参数组合
                score, stats = self._backtest_parameters(temp_strategy, df.copy())
                
                results.append({
                    'params': params,
                    'score': score,
                    'stats': stats
                })
                
                self.logger.debug(f"参数组合 {i}/{len(param_combinations)}: {params} -> 得分: {score:.4f}")
                
                # 更新最佳参数
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_stats = stats.copy()
                    self.logger.info(f"发现更好的参数组合: {params} (得分: {score:.4f})")
                
            except Exception as e:
                self.logger.error(f"测试参数组合 {params} 时发生错误: {e}")
                continue
        
        # 记录优化结果
        self.logger.info("="*60)
        self.logger.info("参数优化完成")
        self.logger.info(f"最佳参数: {best_params}")
        self.logger.info(f"最佳得分: {best_score:.4f}")
        if best_stats:
            self.logger.info(f"最佳参数统计: 总交易{best_stats['total_trades']}笔, 胜率{best_stats['win_rate']:.2f}%, 盈亏比{best_stats['profit_factor']:.2f}")
        self.logger.info("="*60)
        
        # 保存优化报告
        self._save_optimization_report(strategy_name, results, best_params, best_stats, symbol)
        
        return best_params
    
    def _generate_parameter_combinations(self, strategy_name: str, count: int):
        """生成参数组合"""
        import random
        
        param_ranges = self.parameter_ranges[strategy_name]
        combinations = []
        
        for _ in range(count):
            params = {}
            for param_name, (min_val, max_val) in param_ranges.items():
                if param_name in ['oversold', 'overbought']:
                    # 对于RSI的超买超卖线，确保oversold < overbought
                    if param_name == 'oversold':
                        params[param_name] = random.randint(min_val, max_val)
                    else:  # overbought
                        # 确保超买线大于超卖线至少10
                        min_overbought = max(min_val, params.get('oversold', 30) + 10)
                        params[param_name] = random.randint(min_overbought, max_val)
                elif param_name == 'ma_long':
                    # 确保长周期大于短周期
                    min_long = max(min_val, params.get('ma_short', 10) + 1)
                    params[param_name] = random.randint(min_long, max_val)
                else:
                    params[param_name] = random.randint(min_val, max_val)
            
            combinations.append(params)
        
        return combinations
    
    def _create_strategy_instance(self, strategy_name: str, params: dict):
        """创建策略实例"""
        if strategy_name == "双均线策略":
            return MAStrategy(params)
        elif strategy_name == "DKLL策略":
            return DKLLStrategy(params)
        elif strategy_name == "RSI策略":
            return RSIStrategy(params)
        else:
            return None
    
    def _backtest_parameters(self, strategy, df):
        """回测参数组合"""
        try:
            # 计算指标
            df_with_indicators = strategy.calculate_indicators(df)
            
            # 模拟交易
            trades = []
            position = None  # None, 'BUY', 'SELL'
            entry_price = 0
            entry_time = None
            
            for i in range(1, len(df_with_indicators)):
                current_row = df_with_indicators.iloc[i]
                signal = strategy.generate_signal(df_with_indicators.iloc[:i+1])
                
                # 处理开仓
                if signal and position is None:
                    position = signal
                    entry_price = current_row['close']
                    entry_time = current_row['time']
                
                # 处理平仓（简单的反向信号平仓）
                elif signal and position and signal != position:
                    exit_price = current_row['close']
                    exit_time = current_row['time']
                    
                    # 计算盈亏
                    if position == 'BUY':
                        profit = exit_price - entry_price
                    else:  # SELL
                        profit = entry_price - exit_price
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'type': position,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'profit': profit,
                        'duration': (exit_time - entry_time).total_seconds() / 3600  # 小时
                    })
                    
                    # 开新仓
                    position = signal
                    entry_price = current_row['close']
                    entry_time = current_row['time']
            
            # 计算统计指标
            if not trades:
                return -999, {'total_trades': 0, 'win_rate': 0, 'profit_factor': 0}
            
            total_trades = len(trades)
            winning_trades = [t for t in trades if t['profit'] > 0]
            losing_trades = [t for t in trades if t['profit'] < 0]
            
            win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
            total_profit = sum(t['profit'] for t in trades)
            gross_profit = sum(t['profit'] for t in winning_trades)
            gross_loss = abs(sum(t['profit'] for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
            
            # 计算综合得分（可以根据需要调整权重）
            if total_trades < 10:  # 交易次数太少，降低得分
                score = -999
            else:
                # 综合得分：考虑胜率、盈亏比和总盈亏
                score = (win_rate / 100) * 0.3 + min(profit_factor, 3) * 0.4 + (total_profit / abs(total_profit + 0.001)) * 0.3
            
            stats = {
                'total_trades': total_trades,
                'win_rate': win_rate,
                'total_profit': total_profit,
                'profit_factor': profit_factor,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss
            }
            
            return score, stats
            
        except Exception as e:
            self.logger.error(f"回测过程中发生错误: {e}")
            return -999, {'total_trades': 0, 'win_rate': 0, 'profit_factor': 0}
    
    def _save_optimization_report(self, strategy_name: str, results: list, best_params: dict, best_stats: dict, symbol: str):
        """保存优化报告"""
        try:
            log_dir = LOG_DIR
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{log_dir}/parameter_optimization_{strategy_name.replace('策略', '')}_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write(f"{strategy_name} 参数优化报告\n")
                f.write("="*80 + "\n")
                f.write(f"优化时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"测试组合数量: {len(results)}\n")
                f.write(f"交易品种: {symbol}\n\n")
                
                if best_params:
                    f.write("🏆 最佳参数组合:\n")
                    f.write("-"*40 + "\n")
                    for param, value in best_params.items():
                        f.write(f"{param}: {value}\n")
                    f.write("\n")
                    
                    if best_stats:
                        f.write("📊 最佳参数表现:\n")
                        f.write("-"*40 + "\n")
                        f.write(f"总交易次数: {best_stats['total_trades']}\n")
                        f.write(f"胜率: {best_stats['win_rate']:.2f}%\n")
                        f.write(f"总盈亏: {best_stats['total_profit']:.4f}\n")
                        f.write(f"盈亏比: {best_stats['profit_factor']:.2f}\n")
                        f.write("\n")
                
                # 排序结果（按得分降序）
                sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
                
                f.write("📋 所有测试结果 (前20名):\n")
                f.write("-"*80 + "\n")
                f.write(f"{'排名':<4} {'得分':<8} {'交易数':<6} {'胜率':<8} {'盈亏比':<8} {'参数'}\n")
                f.write("-"*80 + "\n")
                
                for i, result in enumerate(sorted_results[:20], 1):
                    params_str = str(result['params'])
                    f.write(f"{i:<4} {result['score']:<8.4f} {result['stats']['total_trades']:<6} "
                           f"{result['stats']['win_rate']:<8.2f} {result['stats']['profit_factor']:<8.2f} {params_str}\n")
                
                f.write("="*80 + "\n")
            
            self.logger.info(f"优化报告已保存到: {filename}")
            
        except Exception as e:
            self.logger.error(f"保存优化报告失败: {e}")
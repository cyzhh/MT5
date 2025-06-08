import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import os
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

symbol = "BTCUSD"

# ===== 策略基类定义 =====
class BaseStrategy(ABC):
    """策略基类 - 所有策略必须继承此类"""
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        self.logger = logging.getLogger(f'Strategy_{name}')
        
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算策略指标"""
        pass
    
    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> Optional[str]:
        """生成交易信号"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """获取策略描述"""
        pass
    
    def get_name(self) -> str:
        """获取策略名称"""
        return self.name
    
    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        return self.params
    
    def set_params(self, params: Dict[str, Any]):
        """设置策略参数"""
        self.params.update(params)
        self.logger.info(f"策略参数已更新: {params}")

# ===== 双均线策略 =====
class MAStrategy(BaseStrategy):
    """双均线策略 - MA10和MA20金叉死叉"""
    
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'ma_short': 10,
            'ma_long': 20
        }
        if params:
            default_params.update(params)
        
        super().__init__("双均线策略", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算双均线指标"""
        df = df.copy()
        
        ma_short = self.params['ma_short']
        ma_long = self.params['ma_long']
        
        df[f'MA{ma_short}'] = df['close'].rolling(window=ma_short).mean()
        df[f'MA{ma_long}'] = df['close'].rolling(window=ma_long).mean()
        
        # 兼容原代码的列名
        df['MA10'] = df[f'MA{ma_short}']
        df['MA20'] = df[f'MA{ma_long}']
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, verbose: bool = False) -> Optional[str]:
        """生成双均线交易信号"""
        if len(df) < 2:
            if verbose:
                self.logger.warning("数据不足，需要至少2根K线")
            return None
        
        ma_short = self.params['ma_short']
        ma_long = self.params['ma_long']
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        ma_short_col = f'MA{ma_short}'
        ma_long_col = f'MA{ma_long}'
        
        # 确保MA数据有效
        if (pd.isna(latest[ma_short_col]) or pd.isna(latest[ma_long_col]) or 
            pd.isna(prev[ma_short_col]) or pd.isna(prev[ma_long_col])):
            if verbose:
                self.logger.warning("MA数据无效")
            return None
        
        if verbose:
            self.logger.info("=== 双均线信号检查详情 ===")
            self.logger.info(f"前一根K线: MA{ma_short}={prev[ma_short_col]:.2f}, MA{ma_long}={prev[ma_long_col]:.2f}")
            self.logger.info(f"当前K线: MA{ma_short}={latest[ma_short_col]:.2f}, MA{ma_long}={latest[ma_long_col]:.2f}")
            self.logger.info(f"最新价格: {latest['close']:.2f}")
        
        # 金叉信号
        if prev[ma_short_col] < prev[ma_long_col] and latest[ma_short_col] > latest[ma_long_col]:
            signal = 'BUY'
            self.logger.info(f"🔔 检测到金叉信号 (BUY) - MA{ma_short}从{prev[ma_short_col]:.2f}升至{latest[ma_short_col]:.2f}")
            return signal
        # 死叉信号
        elif prev[ma_short_col] > prev[ma_long_col] and latest[ma_short_col] < latest[ma_long_col]:
            signal = 'SELL'
            self.logger.info(f"🔔 检测到死叉信号 (SELL) - MA{ma_short}从{prev[ma_short_col]:.2f}降至{latest[ma_short_col]:.2f}")
            return signal
        
        if verbose:
            ma_diff = latest[ma_short_col] - latest[ma_long_col]
            self.logger.info(f"无信号 - MA差值: {ma_diff:.2f}")
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        ma_short = self.params['ma_short']
        ma_long = self.params['ma_long']
        return f"双均线策略: MA{ma_short}和MA{ma_long}金叉死叉信号"

# ===== DKLL策略 =====
class DKLLStrategy(BaseStrategy):
    """DKLL策略 - DK指标和LL指标组合"""
    
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'n_str': 19,    # DK指标强弱计算周期
            'n_A1': 11,     # A1加权移动平均周期
            'n_A2': 19,     # A2简单移动平均周期
            'n_LL': 19      # LL指标力量计算周期
        }
        if params:
            default_params.update(params)
        
        super().__init__("DKLL策略", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算DKLL策略指标"""
        df = df.copy()
        
        # 获取参数
        n_str = self.params['n_str']
        n_A1 = self.params['n_A1']
        n_A2 = self.params['n_A2']
        n_LL = self.params['n_LL']
        
        # ===== 计算典型价格TYP =====
        df['TYP'] = (df['close'] + df['high'] + df['low']) / 3
        
        # ===== 计算DK指标 =====
        # 1. 计算强弱指标的基础数据
        df['MA_DK'] = df['TYP'].rolling(n_str, min_periods=1).mean()
        
        def calculate_avedev(series):
            """计算平均绝对偏差"""
            if len(series) == 0:
                return np.nan
            mean_val = series.mean()
            return (series - mean_val).abs().mean()
        
        df['AVEDEV_DK'] = df['TYP'].rolling(n_str).apply(calculate_avedev, raw=False)
        
        # 2. 计算强弱值
        df['strength'] = (df['TYP'] - df['MA_DK']) / (0.015 * df['AVEDEV_DK'])
        
        # 3. 计算A值
        df['A'] = (df['close'] * 3 + df['low'] + df['high']) / 6
        
        # 4. 计算A1 - 加权移动平均
        def calculate_weighted_ma(series, window):
            """计算加权移动平均"""
            if len(series) < window:
                return np.nan
            weights = np.arange(1, window + 1)
            return np.sum(series.iloc[-window:] * weights) / np.sum(weights)
        
        df['A1'] = df['A'].rolling(n_A1).apply(lambda x: calculate_weighted_ma(x, n_A1), raw=False)
        
        # 5. 计算A2
        df['A2'] = df['A1'].rolling(n_A2, min_periods=1).mean()
        
        # 6. 生成DK信号
        df['DK'] = 0
        long_condition = (df['strength'] > 0) & (df['A1'] > df['A2'])
        short_condition = (df['strength'] < 0) & (df['A1'] < df['A2'])
        
        df.loc[long_condition, 'DK'] = 1
        df.loc[short_condition, 'DK'] = -1
        df['DK'] = df['DK'].replace(0, np.nan).ffill().fillna(0)
        
        # ===== 计算LL指标 =====
        df['MA_LL'] = df['TYP'].rolling(n_LL, min_periods=1).mean()
        df['AVEDEV_LL'] = df['TYP'].rolling(n_LL).apply(calculate_avedev, raw=False)
        df['POWER'] = (df['TYP'] - df['MA_LL']) / (0.015 * df['AVEDEV_LL'])
        df['LL'] = np.where(df['POWER'] >= 0, 1, -1)
        
        # ===== 生成最终信号 =====
        df['DL'] = df['DK'] + df['LL']
        
        # 兼容原代码，添加MA10和MA20列
        df['MA10'] = df['TYP'].rolling(10).mean()
        df['MA20'] = df['TYP'].rolling(20).mean()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, verbose: bool = False) -> Optional[str]:
        """生成DKLL交易信号
        
        开仓逻辑：
        - DL = 2: 强烈看多，开多仓
        - DL = -2: 强烈看空，开空仓
        
        平仓逻辑（在check_signal_with_positions中处理）：
        - 多仓：当DL <= 0时平仓
        - 空仓：当DL >= 0时平仓
        """
        if len(df) < max(self.params.values()) + 5:  # 确保有足够数据
            if verbose:
                self.logger.warning(f"数据不足，DKLL策略需要至少{max(self.params.values()) + 5}根K线")
            return None
        
        latest = df.iloc[-1]
        
        # 检查DL值
        if pd.isna(latest['DL']):
            if verbose:
                self.logger.warning("DL指标数据无效")
            return None
        
        dl_value = latest['DL']
        
        if verbose:
            dk_value = latest['DK'] if not pd.isna(latest['DK']) else 0
            ll_value = latest['LL'] if not pd.isna(latest['LL']) else 0
            self.logger.info("=== DKLL信号检查详情 ===")
            self.logger.info(f"DK值: {dk_value}, LL值: {ll_value}, DL值: {dl_value}")
            self.logger.info(f"最新价格: {latest['close']:.2f}")
            self.logger.info("开仓条件：DL=+2(强多) 或 DL=-2(强空)")
            self.logger.info("平仓条件：多仓DL<=0 或 空仓DL>=0")
        
        # DL=2: 强烈看多
        if dl_value == 2:
            signal = 'BUY'
            self.logger.info(f"🔔 检测到DKLL强多信号 (BUY) - DL={dl_value}")
            return signal
        # DL=-2: 强烈看空
        elif dl_value == -2:
            signal = 'SELL'
            self.logger.info(f"🔔 检测到DKLL强空信号 (SELL) - DL={dl_value}")
            return signal
        
        if verbose:
            self.logger.info(f"无强烈信号 - DL值: {dl_value}")
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        return f"DKLL策略: DK指标({self.params['n_str']},{self.params['n_A1']},{self.params['n_A2']})和LL指标({self.params['n_LL']})组合，不使用止盈止损，完全依靠信号平仓"

# ===== RSI策略 (示例扩展策略) =====
class RSIStrategy(BaseStrategy):
    """RSI策略 - 相对强弱指标超买超卖"""
    
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            'rsi_period': 14,
            'oversold': 30,
            'overbought': 70
        }
        if params:
            default_params.update(params)
        
        super().__init__("RSI策略", default_params)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算RSI指标"""
        df = df.copy()
        
        rsi_period = self.params['rsi_period']
        
        # 计算价格变化
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        
        # 计算RSI
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 兼容原代码
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame, verbose: bool = False) -> Optional[str]:
        """生成RSI交易信号"""
        if len(df) < self.params['rsi_period'] + 5:
            if verbose:
                self.logger.warning(f"数据不足，RSI策略需要至少{self.params['rsi_period'] + 5}根K线")
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        if pd.isna(latest['RSI']) or pd.isna(prev['RSI']):
            if verbose:
                self.logger.warning("RSI数据无效")
            return None
        
        rsi_current = latest['RSI']
        rsi_prev = prev['RSI']
        oversold = self.params['oversold']
        overbought = self.params['overbought']
        
        if verbose:
            self.logger.info("=== RSI信号检查详情 ===")
            self.logger.info(f"前一RSI: {rsi_prev:.2f}, 当前RSI: {rsi_current:.2f}")
            self.logger.info(f"超卖线: {oversold}, 超买线: {overbought}")
            self.logger.info(f"最新价格: {latest['close']:.2f}")
        
        # 从超卖区域向上突破
        if rsi_prev <= oversold and rsi_current > oversold:
            signal = 'BUY'
            self.logger.info(f"🔔 检测到RSI超卖反弹信号 (BUY) - RSI从{rsi_prev:.2f}升至{rsi_current:.2f}")
            return signal
        # 从超买区域向下突破
        elif rsi_prev >= overbought and rsi_current < overbought:
            signal = 'SELL'
            self.logger.info(f"🔔 检测到RSI超买回落信号 (SELL) - RSI从{rsi_prev:.2f}降至{rsi_current:.2f}")
            return signal
        
        if verbose:
            self.logger.info(f"无信号 - RSI值: {rsi_current:.2f}")
        
        return None
    
    def get_description(self) -> str:
        """获取策略描述"""
        return f"RSI策略: RSI({self.params['rsi_period']})超买({self.params['overbought']})超卖({self.params['oversold']})信号"

# ===== 策略管理器 =====
class StrategyManager:
    """策略管理器 - 管理所有可用策略"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.current_strategy: Optional[BaseStrategy] = None
        self.logger = logging.getLogger('StrategyManager')
        
        # 注册默认策略
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认策略"""
        # 双均线策略
        ma_strategy = MAStrategy()
        self.register_strategy("MA", ma_strategy)
        
        # DKLL策略
        dkll_strategy = DKLLStrategy()
        self.register_strategy("DKLL", dkll_strategy)
        
        # RSI策略
        rsi_strategy = RSIStrategy()
        self.register_strategy("RSI", rsi_strategy)
        
        # 默认选择双均线策略（保持兼容性）
        self.current_strategy = ma_strategy
        self.logger.info("默认策略已注册，当前策略: 双均线策略")
    
    def register_strategy(self, key: str, strategy: BaseStrategy):
        """注册新策略"""
        self.strategies[key] = strategy
        self.logger.info(f"策略已注册: {key} - {strategy.get_name()}")
    
    def get_available_strategies(self) -> Dict[str, str]:
        """获取可用策略列表"""
        return {key: strategy.get_name() for key, strategy in self.strategies.items()}
    
    def select_strategy(self, key: str) -> bool:
        """选择策略"""
        if key not in self.strategies:
            self.logger.error(f"策略不存在: {key}")
            return False
        
        self.current_strategy = self.strategies[key]
        self.logger.info(f"策略已切换: {self.current_strategy.get_name()}")
        return True
    
    def get_current_strategy(self) -> Optional[BaseStrategy]:
        """获取当前策略"""
        return self.current_strategy
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用当前策略计算指标"""
        if self.current_strategy is None:
            raise ValueError("没有选择策略")
        
        return self.current_strategy.calculate_indicators(df)
    
    def generate_signal(self, df: pd.DataFrame, verbose: bool = False) -> Optional[str]:
        """使用当前策略生成信号"""
        if self.current_strategy is None:
            raise ValueError("没有选择策略")
        
        return self.current_strategy.generate_signal(df, verbose)
    
    def get_strategy_info(self) -> str:
        """获取当前策略信息"""
        if self.current_strategy is None:
            return "未选择策略"
        
        strategy = self.current_strategy
        info = f"当前策略: {strategy.get_name()}\n"
        info += f"描述: {strategy.get_description()}\n"
        info += f"参数: {strategy.get_params()}"
        return info

# ===== 交易统计类 =====
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
            log_dir = "trading_logs"
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

# ===== 参数优化器 =====
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
        self._save_optimization_report(strategy_name, results, best_params, best_stats)
        
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
    
    def _save_optimization_report(self, strategy_name: str, results: list, best_params: dict, best_stats: dict):
        """保存优化报告"""
        try:
            log_dir = "trading_logs"
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

def run_automated_trading(optimization_interval_hours: int = 24, optimization_lookback_hours: int = 168):
    """运行全自动化交易流程
    
    Args:
        optimization_interval_hours: 参数优化间隔（小时）
        optimization_lookback_hours: 优化时回望的历史数据长度（小时，默认7天）
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
    signal_check_interval = 10  # 秒
    price_update_interval = 1   # 秒
    performance_update_interval = 30  # 统计更新间隔（秒）
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
                        symbol=symbol,
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
            tick = get_real_time_price(symbol)
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
            if (now - last_performance_update).total_seconds() >= performance_update_interval:
                performance_tracker.update_positions_from_mt5()
                last_performance_update = now
            
            # 每10秒获取K线数据并检查信号
            if (now - last_signal_check).total_seconds() >= signal_check_interval:
                logger.debug(f"执行信号检查 (第{cycle_count}次循环)")
                
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                
                cached_df = current_df
                last_signal_check = now
                
                # 使用新的信号检查函数，考虑持仓情况
                signal, close_orders = check_signal_with_positions(current_df, current_positions, verbose=False)
                
                # 处理平仓信号
                if close_orders:
                    for close_order in close_orders:
                        logger.info(f"🔻 自动化交易执行平仓: {close_order['reason']}")
                        if close_position(close_order['ticket'], close_order['symbol'], close_order['reason']):
                            print(f"\n✅ 自动平仓成功: 票据{close_order['ticket']} ({close_order['reason']})")
                            performance_tracker.print_summary()
                        else:
                            print(f"\n❌ 自动平仓失败: 票据{close_order['ticket']}")
                
                # 处理开仓信号（只在无持仓时）
                elif signal and len(current_positions) == 0:
                    logger.info(f"🚨 自动化交易检测到{signal}信号，立即下单！")
                    if place_order(symbol, signal, volume=0.01):
                        trade_logger.info(f"全自动交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ 自动{signal}订单已提交！继续监控...")
                        performance_tracker.print_summary()
                    else:
                        trade_logger.error(f"全自动交易失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                        print(f"\n❌ 自动{signal}下单失败！继续监控...")
                
                # 更新状态显示
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
            else:
                # 快速模式：只显示价格变化
                time_remaining = signal_check_interval - (now - last_signal_check).total_seconds()
                error_info = f" | 连接错误: {connection_error_count}" if connection_error_count > 0 else ""
                stats = performance_tracker.get_statistics()
                stats_info = f"交易: {stats['total_trades']} | 盈亏: {stats['total_profit']:+.2f}"
                hours_to_next_optimization = optimization_interval_hours - time_since_last_optimization
                optimization_info = f"优化: {optimization_count}次 | 下次: {hours_to_next_optimization:.1f}h"
                print(f"\r🤖 实时: {current_price:.2f} | 持仓: {len(current_positions)} | {stats_info} | {optimization_info} | 下次检查: {time_remaining:.0f}s | 周期: {cycle_count}{error_info}", end="")
            
            # 每5分钟记录详细状态
            if (now - last_status_log).total_seconds() >= 300:
                if cached_df is not None:
                    log_market_status(cached_df)
                account_info = mt5.account_info()
                if account_info:
                    logger.info(f"账户状态 | 余额: {account_info.balance:.2f} | 净值: {account_info.equity:.2f} | 保证金: {account_info.margin:.2f}")
                
                # 记录交易统计和优化状态
                stats = performance_tracker.get_statistics()
                logger.info(f"自动化交易统计 | 总交易: {stats['total_trades']} | 胜率: {stats['win_rate']:.2f}% | 总盈亏: {stats['total_profit']:+.2f} | 余额变化: {stats['balance_change']:+.2f}")
                logger.info(f"参数优化状态 | 已优化: {optimization_count}次 | 距离下次: {hours_to_next_optimization:.1f}小时 | 当前参数: {current_strategy.get_params()}")
                last_status_log = now
            
            # 动态调整睡眠时间
            time.sleep(price_update_interval)
            
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

def setup_automated_trading():
    """设置全自动化交易参数"""
    logger.info("用户配置全自动化交易参数")
    
    current_strategy = strategy_manager.get_current_strategy()
    print(f"\n🤖 全自动化交易设置")
    print(f"当前策略: {current_strategy.get_name()}")
    print(f"交易品种: {symbol}")
    
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
    print(f"  品种: {symbol}")
    print(f"  优化间隔: {optimization_interval_hours} 小时")
    print(f"  回望期: {optimization_lookback_hours} 小时 ({optimization_lookback_hours//24} 天)")
    print(f"  首次优化: {(datetime.now() + timedelta(hours=optimization_interval_hours)).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if current_strategy.get_name() == "DKLL策略":
        print(f"  策略特点: 不使用止盈止损，依靠信号平仓")
    
    # 确认启动
    confirm = input(f"\n确认启动全自动化交易? (y/N): ").strip().lower()
    if confirm == 'y':
        logger.info(f"用户确认启动全自动化交易 - 优化间隔: {optimization_interval_hours}h, 回望期: {optimization_lookback_hours}h")
        run_automated_trading(optimization_interval_hours, optimization_lookback_hours)
    else:
        logger.info("用户取消全自动化交易")
        print("已取消全自动化交易")

def manual_parameter_optimization():
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
    print(f"  品种: {symbol}")
    
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
                symbol=symbol,
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

def check_connection_status():
    """检查MT5连接状态"""
    if not mt5.initialize():
        logger.error("MT5连接已断开")
        return False
    
    # 检查终端连接状态
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        logger.error("无法获取终端信息")
        return False
    
    if not terminal_info.connected:
        logger.error("MT5终端未连接到服务器")
        return False
    
    return True

def check_auto_trading():
    """检查自动交易状态"""
    logger.info("检查自动交易状态...")
    
    # 首先检查连接状态
    if not check_connection_status():
        logger.error("MT5连接异常")
        return False
    
    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        logger.error("无法获取终端信息")
        return False
    
    logger.info(f"终端信息 - 连接状态: {terminal_info.connected}, 自动交易启用: {terminal_info.trade_allowed}, EA交易启用: {terminal_info.dlls_allowed}")
    
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("无法获取账户信息")
        return False
    
    logger.info(f"账户信息 - 交易启用: {account_info.trade_allowed}, 交易模式: {account_info.trade_mode}")
    logger.info(f"账户余额: {account_info.balance}, 净值: {account_info.equity}, 保证金: {account_info.margin}")
    
    is_trading_allowed = (terminal_info.trade_allowed and 
                         terminal_info.dlls_allowed and 
                         account_info.trade_allowed and
                         terminal_info.connected)
    
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
    
    # 检查连接状态
    if not check_connection_status():
        logger.error("MT5连接异常，无法获取品种信息")
        return None
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"无法获取{symbol}的信息，可能的原因：")
        logger.error("1. 交易品种名称错误")
        logger.error("2. 服务器不支持该品种")
        logger.error("3. 网络连接问题")
        
        # 尝试获取所有可用品种
        symbols = mt5.symbols_get()
        if symbols:
            logger.info(f"当前服务器支持的品种数量: {len(symbols)}")
            # 查找相似的品种名称
            similar_symbols = [s.name for s in symbols if symbol.lower() in s.name.lower()]
            if similar_symbols:
                logger.info(f"找到相似品种: {similar_symbols[:5]}")  # 只显示前5个
        
        return None
    
    if not symbol_info.visible:
        logger.info(f"尝试添加{symbol}到市场观察...")
        if not mt5.symbol_select(symbol, True):
            logger.error(f"无法添加{symbol}到市场观察")
            return None
        logger.info(f"{symbol}已添加到市场观察")
    
    # 检查品种是否可交易
    if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
        logger.warning(f"{symbol}当前不可交易，交易模式: {symbol_info.trade_mode}")
    
    # 检查市场开放时间
    now = datetime.now()
    if hasattr(symbol_info, 'trade_time_flags'):
        logger.debug(f"{symbol}交易时间标志: {symbol_info.trade_time_flags}")
    
    logger.debug(f"{symbol}信息 - 点差: {symbol_info.spread}, 最小交易量: {symbol_info.volume_min}, 交易模式: {symbol_info.trade_mode}")
    return symbol_info

def get_real_time_price(symbol, max_retries=3):
    """获取实时价格，带重试机制"""
    for attempt in range(max_retries):
        try:
            # 检查连接状态
            if not check_connection_status():
                logger.warning(f"第{attempt+1}次尝试：MT5连接异常")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                logger.warning(f"第{attempt+1}次尝试：无法获取{symbol}的实时价格")
                
                # 检查可能的原因
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    logger.error(f"品种{symbol}不存在或不可用")
                    return None
                
                if not symbol_info.visible:
                    logger.warning(f"品种{symbol}不在市场观察中，尝试添加...")
                    mt5.symbol_select(symbol, True)
                
                # 检查市场是否开放
                current_time = datetime.now()
                logger.info(f"当前时间: {current_time}")
                logger.info(f"品种状态 - 可见: {symbol_info.visible}, 交易模式: {symbol_info.trade_mode}")
                
                if attempt < max_retries - 1:
                    logger.info(f"等待2秒后重试...")
                    time.sleep(2)
                    continue
                else:
                    logger.error("所有重试均失败，可能原因：")
                    logger.error("1. 市场休市（周末或节假日）")
                    logger.error("2. 网络连接不稳定")
                    logger.error("3. 服务器维护")
                    logger.error("4. 品种暂停交易")
                    return None
            
            # 验证价格数据的有效性
            if tick.bid <= 0 or tick.ask <= 0:
                logger.warning(f"第{attempt+1}次尝试：获取到无效价格数据 - bid: {tick.bid}, ask: {tick.ask}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            
            # 成功获取价格
            logger.debug(f"成功获取{symbol}价格 - bid: {tick.bid}, ask: {tick.ask}, 时间: {datetime.fromtimestamp(tick.time)}")
            return tick
            
        except Exception as e:
            logger.error(f"第{attempt+1}次尝试获取价格时发生异常: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
    
    return None

def close_position(ticket, symbol=None, reason="策略信号"):
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
        "deviation": 20,
        "magic": 123456,
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

def check_signal_with_positions(df, current_positions, verbose=False):
    """检查交易信号 - 考虑当前持仓情况"""
    current_strategy = strategy_manager.get_current_strategy()
    strategy_name = current_strategy.get_name()
    
    try:
        df_with_indicators = strategy_manager.calculate_indicators(df)
        signal = strategy_manager.generate_signal(df_with_indicators, verbose)
        
        # 如果没有持仓，正常处理开仓信号
        if len(current_positions) == 0:
            return signal, []
        
        # 如果有持仓，检查是否需要平仓
        close_orders = []
        
        # DKLL策略的特殊处理：检查平仓信号
        if strategy_name == "DKLL策略":
            latest = df_with_indicators.iloc[-1]
            dl_value = latest.get('DL', 0) if not pd.isna(latest.get('DL', 0)) else 0
            
            for pos in current_positions:
                should_close = False
                close_reason = ""
                
                if pos.type == mt5.POSITION_TYPE_BUY:  # 多仓
                    # DL从正值变为负值或0，平多仓
                    if dl_value <= 0:
                        should_close = True
                        close_reason = f"DKLL平多信号 (DL={dl_value})"
                elif pos.type == mt5.POSITION_TYPE_SELL:  # 空仓
                    # DL从负值变为正值或0，平空仓
                    if dl_value >= 0:
                        should_close = True
                        close_reason = f"DKLL平空信号 (DL={dl_value})"
                
                if should_close:
                    close_orders.append({
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'reason': close_reason
                    })
                    if verbose:
                        logger.info(f"检测到平仓信号: 票据{pos.ticket}, {close_reason}")
        
        # 其他策略的平仓逻辑（如果需要）
        else:
            # 对于有止盈止损的策略，如果检测到反向信号，也可以平仓
            if signal and len(current_positions) > 0:
                for pos in current_positions:
                    # 检查是否是反向信号
                    is_reverse_signal = False
                    if ((pos.type == mt5.POSITION_TYPE_BUY and signal == 'SELL') or
                        (pos.type == mt5.POSITION_TYPE_SELL and signal == 'BUY')):
                        is_reverse_signal = True
                    
                    if is_reverse_signal:
                        close_orders.append({
                            'ticket': pos.ticket,
                            'symbol': pos.symbol,
                            'reason': f"{strategy_name}反向信号"
                        })
                        if verbose:
                            logger.info(f"检测到反向信号平仓: 票据{pos.ticket}, 当前持仓{'多' if pos.type == 0 else '空'}，信号{signal}")
        
        # 如果有平仓信号，则不产生新的开仓信号
        if close_orders:
            return None, close_orders
        else:
            return signal, []
            
    except Exception as e:
        logger.error(f"信号检查失败: {e}")
        return None, []

def place_order(symbol, direction, volume=0.01):
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
        "deviation": 20,
        "magic": 123456,
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
                "deviation": 20,
                "magic": 123456,
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
    
    # 获取当前策略信息
    current_strategy = strategy_manager.get_current_strategy()
    strategy_name = current_strategy.get_name() if current_strategy else "未知"
    
    # 根据不同策略显示不同指标
    if strategy_name == "双均线策略":
        ma10 = latest['MA10'] if not pd.isna(latest['MA10']) else 0
        ma20 = latest['MA20'] if not pd.isna(latest['MA20']) else 0
        indicator_info = f"MA10: {ma10:.2f} | MA20: {ma20:.2f} | MA差值: {ma10-ma20:.2f}"
    elif strategy_name == "DKLL策略":
        dk = latest['DK'] if 'DK' in latest and not pd.isna(latest['DK']) else 0
        ll = latest['LL'] if 'LL' in latest and not pd.isna(latest['LL']) else 0
        dl = latest['DL'] if 'DL' in latest and not pd.isna(latest['DL']) else 0
        indicator_info = f"DK: {dk} | LL: {ll} | DL: {dl}"
    elif strategy_name == "RSI策略":
        rsi = latest['RSI'] if 'RSI' in latest and not pd.isna(latest['RSI']) else 0
        indicator_info = f"RSI: {rsi:.2f}"
    else:
        indicator_info = "指标计算中..."
    
    # 每5分钟记录一次详细市场状态
    current_minute = datetime.now().minute
    if current_minute % 5 == 0:
        logger.info(f"市场状态 | 策略: {strategy_name} | 价格: {price:.2f} | {indicator_info}")

def strategy_selection_menu():
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
                    modify_strategy_params()
            else:
                print("❌ 策略切换失败")
        else:
            print("❌ 无效选择")
            
    except ValueError:
        print("❌ 请输入有效数字")
    except Exception as e:
        logger.error(f"策略选择出错: {e}")
        print("❌ 策略选择出错")

def modify_strategy_params():
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

def diagnose_system():
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
    print(f"2. 检查交易品种 {symbol}...")
    symbol_info = get_symbol_info(symbol)
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
    tick = get_real_time_price(symbol)
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
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 10)
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
            tick = get_real_time_price(symbol, max_retries=1)
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

def view_trading_statistics():
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

def main_with_options():
    """主程序 - 带选项菜单"""
    logger.info("显示程序菜单")
    
    # 显示当前策略信息
    print(f"\n当前策略: {strategy_manager.get_current_strategy().get_name()}")
    
    print("\n=== 交易程序选项 ===")
    print("1. 运行高速监控 (每秒更新，每10秒检查信号)")
    print("2. 运行限时高速监控 (指定时间)")
    print("3. 运行经典监控 (每5秒更新)")
    print("4. 🤖 全自动化交易 (含定时参数优化)")  # 修复后的选项
    print("5. 检查当前信号状态")
    print("6. 手动下单测试")
    print("7. 查看当前持仓")
    print("8. 策略选择和配置")  
    print("9. 查看策略信息")   
    print("10. 系统诊断")        
    print("11. 查看交易统计")
    print("12. 🔧 手动参数优化")  # 修复后的选项
    print("0. 退出")
    
    try:
        choice = input("\n请选择操作 (0-12): ").strip()
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
            # 全自动化交易
            setup_automated_trading()
        elif choice == "5":
            check_current_signal()
        elif choice == "6":
            test_manual_order()
        elif choice == "7":
            show_positions()
        elif choice == "8":
            strategy_selection_menu()
        elif choice == "9":
            print("\n" + strategy_manager.get_strategy_info())
        elif choice == "10":
            diagnose_system()
        elif choice == "11":
            view_trading_statistics()
        elif choice == "12":
            # 手动参数优化
            manual_parameter_optimization()
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
        # 程序退出时生成最终统计报告
        cleanup_and_generate_final_report()

def cleanup_and_generate_final_report():
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
        mt5.shutdown()

def run_classic_monitoring():
    """运行经典监控模式 (原速度)"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始经典模式监控... 当前策略: {current_strategy.get_name()}")
    print("按 Ctrl+C 停止监控")
    print(f"监控模式: 经典 (每5秒全面更新) | 策略: {current_strategy.get_name()}")
    
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
            
            # 使用策略管理器计算指标
            current_df = strategy_manager.calculate_indicators(current_df)
            
            # 每分钟详细检查一次信号
            now = datetime.now()
            verbose = (now - last_signal_check).seconds >= 60
            if verbose:
                last_signal_check = now
            
            # 每5分钟记录一次状态
            if (now - last_status_log).seconds >= 300:
                log_market_status(current_df)
                last_status_log = now
            
            signal = strategy_manager.generate_signal(current_df, verbose=verbose)
            current_positions = get_positions()
            
            current_time = current_df.iloc[-1]['time']
            current_price = current_df.iloc[-1]['close']
            
            # 根据策略显示不同信息
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
            
            if signal and len(current_positions) == 0:
                logger.info(f"检测到{signal}信号，准备下单")
                if place_order(symbol, signal, volume=0.01):
                    trade_logger.info(f"经典监控交易 | {current_strategy.get_name()} | {signal}信号触发成功")
                    print("\n✅ 订单已提交！继续监控...")
                else:
                    trade_logger.error(f"经典监控失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                    print("\n❌ 下单失败！继续监控...")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("经典监控被用户停止")

def run_continuous_monitoring():
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
    signal_check_interval = 10  # 秒
    price_update_interval = 1   # 秒
    connection_error_count = 0  # 连接错误计数
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            now = datetime.now()
            
            # 快速获取当前价格（每秒更新）
            tick = get_real_time_price(symbol)
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
            if (now - last_signal_check).total_seconds() >= signal_check_interval:
                logger.debug(f"执行信号检查 (第{cycle_count}次循环)")
                
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)  # 根据策略需要调整数据量
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
                    if place_order(symbol, signal, volume=0.01):
                        trade_logger.info(f"高速监控交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！继续监控...")
                    else:
                        trade_logger.error(f"高速监控失败 | {current_strategy.get_name()} | {signal}信号触发但下单失败")
                        print(f"\n❌ {signal}下单失败！继续监控...")
                
                # 更新状态显示
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
            else:
                # 快速模式：只显示价格变化
                time_remaining = signal_check_interval - (now - last_signal_check).total_seconds()
                error_info = f" | 连接错误: {connection_error_count}" if connection_error_count > 0 else ""
                print(f"\r💹 实时: {current_price:.2f} | 持仓: {len(current_positions)} | 下次检查: {time_remaining:.0f}s | 周期: {cycle_count}{error_info}", end="")
            
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
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"开始高速限时监控 {minutes} 分钟，当前策略: {current_strategy.get_name()}")
    end_time = datetime.now() + timedelta(minutes=minutes)
    
    if current_strategy.get_name() == "DKLL策略":
        print("🔔 DKLL策略：不使用止盈止损，完全依靠信号平仓")
    
    cached_df = None
    last_signal_check = datetime.now()
    last_performance_update = datetime.now()
    signal_check_interval = 10  # 秒
    cycle_count = 0
    connection_error_count = 0
    
    try:
        while datetime.now() < end_time:
            cycle_count += 1
            now = datetime.now()
            remaining = end_time - now
            
            # 快速获取当前价格
            tick = get_real_time_price(symbol)
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
            if (now - last_performance_update).total_seconds() >= 30:
                performance_tracker.update_positions_from_mt5()
                last_performance_update = now
            
            # 每10秒检查信号
            if (now - last_signal_check).total_seconds() >= signal_check_interval:
                latest_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
                if latest_rates is None:
                    logger.error("无法获取K线数据")
                    time.sleep(5)
                    continue
                
                current_df = pd.DataFrame(latest_rates)
                current_df['time'] = pd.to_datetime(current_df['time'], unit='s')
                
                cached_df = current_df
                last_signal_check = now
                
                # 使用新的信号检查函数
                signal, close_orders = check_signal_with_positions(current_df, current_positions, verbose=True)
                
                # 处理平仓信号
                if close_orders:
                    for close_order in close_orders:
                        logger.info(f"限时监控中检测到平仓信号: {close_order['reason']}")
                        if close_position(close_order['ticket'], close_order['symbol'], close_order['reason']):
                            trade_logger.info(f"限时监控平仓 | {current_strategy.get_name()} | {close_order['reason']}成功")
                            print(f"\n✅ 平仓成功: {close_order['reason']}")
                            performance_tracker.print_summary()
                
                # 处理开仓信号
                elif signal and len(current_positions) == 0:
                    logger.info(f"限时监控中检测到{signal}信号")
                    if place_order(symbol, signal, volume=0.01):
                        trade_logger.info(f"限时监控交易 | {current_strategy.get_name()} | {signal}信号成功执行")
                        print(f"\n✅ {signal}订单已提交！")
                        performance_tracker.print_summary()
            
            # 显示状态
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
            
            time.sleep(1)  # 高速更新
            
        logger.info(f"限时监控结束，共监控了 {minutes} 分钟，执行了 {cycle_count} 个周期")
        
        # 显示最终统计
        performance_tracker.update_positions_from_mt5()
        performance_tracker.print_summary()
        
    except KeyboardInterrupt:
        logger.info("限时监控被用户中断")
        performance_tracker.update_positions_from_mt5()
        performance_tracker.print_summary()

def check_current_signal():
    """检查当前信号状态"""
    current_strategy = strategy_manager.get_current_strategy()
    logger.info(f"用户请求检查当前信号状态，当前策略: {current_strategy.get_name()}")
    
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1000)
    if rates is None:
        logger.error("无法获取数据")
        return
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 获取当前持仓
    current_positions = get_positions()
    
    # 使用新的信号检查函数
    signal, close_orders = check_signal_with_positions(df, current_positions, verbose=True)
    
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

def test_manual_order():
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
    volume = float(volume) if volume else 0.01
    
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
        if place_order(symbol, direction, volume):
            print("✅ 订单提交成功！")
            trade_logger.info(f"手动下单成功 | 策略: {current_strategy.get_name()} | 方向: {direction} | 数量: {volume}")
        else:
            print("❌ 订单提交失败！")
    else:
        logger.info("用户取消手动下单")

def show_positions():
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
                    if close_position(ticket, target_position.symbol, "手动平仓"):
                        print("✅ 手动平仓成功！")
                        trade_logger.info(f"手动平仓成功 | 票据: {ticket}")
                    else:
                        print("❌ 手动平仓失败！")
            else:
                print(f"❌ 未找到票据号为 {manual_close} 的持仓")

if __name__ == "__main__":
    # 获取历史数据用于指标计算
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
        
        # 创建全局策略管理器
        strategy_manager = StrategyManager()

        # 创建全局交易统计实例
        performance_tracker = TradingPerformanceTracker()

        # 创建全局参数优化器
        parameter_optimizer = ParameterOptimizer()
        
        # 显示当前策略信息
        current_strategy = strategy_manager.get_current_strategy()
        logger.info(f"当前策略: {current_strategy.get_name()}")
        logger.info(f"策略描述: {current_strategy.get_description()}")
        
        # 显示交易会话开始信息
        print(f"\n🚀 MT5智能交易系统启动")
        print(f"版本: v2.0 (包含全自动化交易)")
        print(f"时间: {performance_tracker.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"初始余额: {performance_tracker.session_start_balance:.2f}")
        print(f"交易品种: {symbol}")
        print(f"当前策略: {current_strategy.get_name()}")
        print(f"策略参数: {current_strategy.get_params()}")
        
        print(f"\n🔧 新功能:")
        print(f"  ✅ 全自动化交易 (选项4)")
        print(f"  ✅ 定时参数优化")
        print(f"  ✅ 手动参数优化 (选项12)")
        print(f"  ✅ DKLL策略无止盈止损")
        print(f"  ✅ 完整的交易统计")
        
        if current_strategy.get_name() == "DKLL策略":
            print(f"\n🔔 当前策略特点:")
            print(f"  - 不使用止盈止损")
            print(f"  - 完全依靠信号平仓")
            print(f"  - 开仓: DL=±2")
            print(f"  - 平仓: 多仓DL≤0, 空仓DL≥0")
        
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}", exc_info=True)
        mt5.shutdown()
        quit()
    
    # 启动主程序
    try:
        while True:
            main_with_options()
            
            # 询问是否继续
            continue_choice = input("\n是否继续使用程序? (y/N): ").strip().lower()
            if continue_choice != 'y':
                break
                
    except Exception as e:
        logger.error(f"主程序异常: {e}", exc_info=True)
    finally:
        logger.info("程序结束")
        logger.info("="*60)
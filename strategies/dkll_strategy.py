"""
DKLL策略实现
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from .base import BaseStrategy

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
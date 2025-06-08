"""
双均线策略实现
"""
import pandas as pd
from typing import Dict, Any, Optional
from .base import BaseStrategy

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
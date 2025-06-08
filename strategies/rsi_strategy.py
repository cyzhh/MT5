"""
RSI策略实现
"""
import pandas as pd
from typing import Dict, Any, Optional
from .base import BaseStrategy

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
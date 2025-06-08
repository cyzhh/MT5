"""
策略管理器
"""
import logging
from typing import Dict, Optional
import pandas as pd
from .base import BaseStrategy
from .ma_strategy import MAStrategy
from .dkll_strategy import DKLLStrategy
from .rsi_strategy import RSIStrategy

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
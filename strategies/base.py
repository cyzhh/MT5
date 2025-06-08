"""
策略基类定义
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd

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
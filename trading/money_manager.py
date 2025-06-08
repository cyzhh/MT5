"""
资金管理模块 - 处理多币种持仓和风险控制
"""
import logging
from typing import Dict, Optional, Tuple, List
import MetaTrader5 as mt5
from config.settings import TRADING_SYMBOLS, MONEY_MANAGEMENT

logger = logging.getLogger('MoneyManager')

class MoneyManager:
    """资金管理器 - 管理多币种持仓和风险"""
    
    def __init__(self):
        self.symbols_config = TRADING_SYMBOLS
        self.money_config = MONEY_MANAGEMENT
        self.logger = logging.getLogger('MoneyManager')
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证配置的有效性"""
        total_ratio = sum(cfg['position_ratio'] for cfg in self.symbols_config.values() if cfg['enabled'])
        if total_ratio > 1.0:
            self.logger.warning(f"警告：总持仓比例 {total_ratio:.1%} 超过100%")
        
        self.logger.info(f"资金管理器初始化 - 启用币种: {self.get_enabled_symbols()}")
        self.logger.info(f"总持仓比例: {total_ratio:.1%}")
    
    def get_enabled_symbols(self) -> List[str]:
        """获取启用的交易品种列表"""
        return [symbol for symbol, cfg in self.symbols_config.items() if cfg['enabled']]
    
    def get_symbol_config(self, symbol: str) -> Optional[Dict]:
        """获取指定品种的配置"""
        return self.symbols_config.get(symbol)
    
    def calculate_position_size(self, symbol: str, account_balance: float) -> float:
        """
        计算建议的持仓大小
        
        Args:
            symbol: 交易品种
            account_balance: 账户余额
            
        Returns:
            建议的交易量
        """
        config = self.get_symbol_config(symbol)
        if not config or not config['enabled']:
            return 0.0
        
        # 基础交易量
        base_volume = config['volume_per_trade']
        
        # 如果启用动态交易量
        if self.money_config['use_dynamic_volume']:
            # 根据账户余额和持仓比例计算
            allocated_balance = account_balance * config['position_ratio']
            
            # 获取品种信息
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                # 根据分配的资金计算可能的交易量
                # 这里简化处理，实际应考虑保证金要求等
                dynamic_volume = min(
                    allocated_balance * 0.01,  # 使用分配资金的1%
                    config['max_volume'] / config['max_positions']  # 单笔最大量
                )
                
                # 确保符合最小交易量要求
                min_volume = symbol_info.volume_min
                volume_step = symbol_info.volume_step
                
                # 调整到符合步长的交易量
                dynamic_volume = max(dynamic_volume, min_volume)
                dynamic_volume = round(dynamic_volume / volume_step) * volume_step
                
                base_volume = min(dynamic_volume, config['volume_per_trade'])
        
        return base_volume
    
    def check_position_limits(self, symbol: str) -> Tuple[bool, str]:
        """
        检查是否可以开新仓
        
        Returns:
            (是否可以开仓, 原因说明)
        """
        config = self.get_symbol_config(symbol)
        if not config or not config['enabled']:
            return False, f"{symbol} 未启用交易"
        
        # 获取当前持仓
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            positions = []
        
        current_positions = len(positions)
        
        # 检查持仓数量限制
        if current_positions >= config['max_positions']:
            return False, f"{symbol} 已达最大持仓数量限制 ({config['max_positions']})"
        
        # 检查总持仓量
        total_volume = sum(pos.volume for pos in positions)
        if total_volume >= config['max_volume']:
            return False, f"{symbol} 已达最大持仓量限制 ({config['max_volume']})"
        
        # 检查账户风险
        account_info = mt5.account_info()
        if account_info:
            # 检查可用保证金
            if account_info.margin_free < account_info.margin * self.money_config['min_free_margin_ratio']:
                return False, "可用保证金不足"
            
            # 检查总风险敞口
            if account_info.margin > 0:
                risk_ratio = (account_info.equity - account_info.balance) / account_info.balance
                if abs(risk_ratio) > self.money_config['max_total_risk']:
                    return False, f"总风险超过限制 ({abs(risk_ratio):.1%})"
        
        return True, "可以开仓"
    
    def get_account_allocation_status(self) -> Dict:
        """获取账户资金分配状态"""
        account_info = mt5.account_info()
        if not account_info:
            return {}
        
        status = {
            'total_balance': account_info.balance,
            'total_equity': account_info.equity,
            'free_margin': account_info.margin_free,
            'used_margin': account_info.margin,
            'symbols': {}
        }
        
        # 计算每个品种的分配和使用情况
        for symbol, config in self.symbols_config.items():
            if not config['enabled']:
                continue
            
            positions = mt5.positions_get(symbol=symbol)
            if positions is None:
                positions = []
            
            symbol_status = {
                'allocated_balance': account_info.balance * config['position_ratio'],
                'position_ratio': config['position_ratio'],
                'current_positions': len(positions),
                'max_positions': config['max_positions'],
                'current_volume': sum(pos.volume for pos in positions),
                'max_volume': config['max_volume'],
                'current_profit': sum(pos.profit for pos in positions),
                'utilization': len(positions) / config['max_positions'] * 100 if config['max_positions'] > 0 else 0
            }
            
            status['symbols'][symbol] = symbol_status
        
        return status
    
    def should_close_position(self, position) -> Tuple[bool, str]:
        """
        检查是否应该基于风险管理规则平仓
        
        Args:
            position: MT5持仓对象
            
        Returns:
            (是否应该平仓, 原因)
        """
        # 检查单笔交易风险
        account_info = mt5.account_info()
        if account_info and account_info.balance > 0:
            position_risk = abs(position.profit) / account_info.balance
            
            if position.profit < 0 and position_risk > self.money_config['max_risk_per_trade']:
                return True, f"单笔亏损超过限制 ({position_risk:.1%})"
        
        # 可以添加更多风险管理规则
        # 例如：持仓时间过长、波动率过大等
        
        return False, ""
    
    def get_risk_summary(self) -> Dict:
        """获取风险汇总信息"""
        account_info = mt5.account_info()
        if not account_info:
            return {}
        
        all_positions = mt5.positions_get()
        if all_positions is None:
            all_positions = []
        
        total_profit = sum(pos.profit for pos in all_positions)
        total_risk = abs(total_profit) / account_info.balance if account_info.balance > 0 else 0
        
        summary = {
            'total_positions': len(all_positions),
            'total_profit': total_profit,
            'total_risk_ratio': total_risk,
            'risk_status': 'NORMAL',
            'warnings': []
        }
        
        # 风险评估
        if total_risk > self.money_config['max_total_risk']:
            summary['risk_status'] = 'HIGH'
            summary['warnings'].append(f"总风险超过限制: {total_risk:.1%}")
        
        if account_info.margin_free < account_info.margin * self.money_config['min_free_margin_ratio']:
            summary['risk_status'] = 'WARNING'
            summary['warnings'].append("可用保证金不足")
        
        # 检查各品种风险
        for symbol in self.get_enabled_symbols():
            positions = [p for p in all_positions if p.symbol == symbol]
            if positions:
                symbol_profit = sum(pos.profit for pos in positions)
                symbol_risk = abs(symbol_profit) / account_info.balance if account_info.balance > 0 else 0
                
                if symbol_risk > self.money_config['max_risk_per_trade'] * 2:
                    summary['warnings'].append(f"{symbol} 风险过高: {symbol_risk:.1%}")
        
        return summary
    
    def optimize_portfolio_allocation(self, performance_data: Dict) -> Dict:
        """
        基于历史表现优化资产配置
        
        Args:
            performance_data: 各品种的历史表现数据
            
        Returns:
            优化后的配置建议
        """
        suggestions = {}
        
        # 简单的优化逻辑：根据胜率和盈亏比调整配置
        total_weight = 0
        weights = {}
        
        for symbol, data in performance_data.items():
            if symbol not in self.symbols_config:
                continue
            
            # 计算权重分数（可以使用更复杂的算法）
            win_rate = data.get('win_rate', 50) / 100
            profit_factor = data.get('profit_factor', 1)
            
            # 简单的权重计算
            weight = win_rate * profit_factor
            weights[symbol] = weight
            total_weight += weight
        
        # 归一化权重并生成建议
        if total_weight > 0:
            for symbol, weight in weights.items():
                normalized_weight = weight / total_weight
                current_ratio = self.symbols_config[symbol]['position_ratio']
                
                suggestions[symbol] = {
                    'current_ratio': current_ratio,
                    'suggested_ratio': round(normalized_weight, 2),
                    'change': round(normalized_weight - current_ratio, 2)
                }
        
        return suggestions
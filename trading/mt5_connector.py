"""
MT5连接和基础交易功能
"""
import logging
import time
from datetime import datetime
import MetaTrader5 as mt5
from config.settings import (
    MT5_ACCOUNT, MT5_PASSWORD, MT5_SERVER, 
    MAX_PRICE_RETRIES, CONNECTION_ERROR_THRESHOLD, RECONNECT_WAIT_TIME
)

logger = logging.getLogger('MT5_Trading')

def initialize_mt5():
    """初始化MT5连接"""
    logger.info("开始初始化MT5连接...")
    if not mt5.initialize():
        logger.error(f"MT5初始化失败，错误代码: {mt5.last_error()}")
        return False
    
    logger.info("MT5初始化成功")
    
    # 登录交易账户
    logger.info(f"尝试登录账户: {MT5_ACCOUNT}, 服务器: {MT5_SERVER}")
    authorized = mt5.login(MT5_ACCOUNT, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        logger.error(f"登录失败，错误代码: {mt5.last_error()}")
        mt5.shutdown()
        return False
    
    logger.info(f"成功登录到账户: {MT5_ACCOUNT}")
    return True

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

def get_real_time_price(symbol, max_retries=MAX_PRICE_RETRIES):
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

def shutdown_mt5():
    """关闭MT5连接"""
    logger.info("关闭MT5连接")
    mt5.shutdown()
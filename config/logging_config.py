"""
日志系统配置
"""
import logging
import os
from datetime import datetime
from config.settings import LOG_DIR

def setup_logging():
    """设置日志系统"""
    # 创建logs目录
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    
    # 生成日志文件名（按日期）
    log_filename = f"{LOG_DIR}/trading_{datetime.now().strftime('%Y%m%d')}.log"
    
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
    trade_log_filename = f"{LOG_DIR}/trades_{datetime.now().strftime('%Y%m%d')}.log"
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
"""
钉钉通知模块
"""
import json
import logging
import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger('DingTalkNotifier')

class DingTalkNotifier:
    """钉钉机器人通知器"""
    
    def __init__(self, webhook: str, secret: Optional[str] = None):
        """
        初始化钉钉通知器
        
        Args:
            webhook: 钉钉机器人的webhook地址
            secret: 钉钉机器人的加签密钥（可选）
        """
        self.webhook = webhook
        self.secret = secret
        self.enabled = bool(webhook)
        
        if not self.enabled:
            logger.warning("钉钉通知未启用（未配置webhook）")
    
    def _generate_sign(self) -> Dict[str, str]:
        """生成钉钉加签参数"""
        if not self.secret:
            return {}
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        
        return {
            "timestamp": timestamp,
            "sign": sign
        }
    
    def send_text(self, content: str, at_all: bool = False) -> bool:
        """
        发送文本消息
        
        Args:
            content: 消息内容
            at_all: 是否@所有人
        """
        if not self.enabled:
            return False
        
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "msgtype": "text",
                "text": {
                    "content": content
                },
                "at": {
                    "isAtAll": at_all
                }
            }
            
            # 添加签名参数
            params = self._generate_sign()
            
            response = requests.post(
                self.webhook,
                headers=headers,
                params=params,
                data=json.dumps(data),
                timeout=10
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                logger.info(f"钉钉消息发送成功: {content[:50]}...")
                return True
            else:
                logger.error(f"钉钉消息发送失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"发送钉钉消息时发生错误: {e}")
            return False
    
    def send_markdown(self, title: str, text: str, at_all: bool = False) -> bool:
        """
        发送Markdown格式消息
        
        Args:
            title: 消息标题
            text: Markdown格式的消息内容
            at_all: 是否@所有人
        """
        if not self.enabled:
            return False
        
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": text
                },
                "at": {
                    "isAtAll": at_all
                }
            }
            
            # 添加签名参数
            params = self._generate_sign()
            
            response = requests.post(
                self.webhook,
                headers=headers,
                params=params,
                data=json.dumps(data),
                timeout=10
            )
            
            result = response.json()
            if result.get("errcode") == 0:
                logger.info(f"钉钉Markdown消息发送成功: {title}")
                return True
            else:
                logger.error(f"钉钉Markdown消息发送失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"发送钉钉Markdown消息时发生错误: {e}")
            return False
    
    def send_trade_notification(self, trade_info: Dict[str, Any]):
        """发送交易通知"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建Markdown格式的消息
        title = f"交易通知 - {trade_info['action']}"
        
        # 根据动作类型选择颜色
        action_color = "green" if trade_info['action'] in ['开仓成功', '平仓成功'] else "red"
        profit_color = "green" if trade_info.get('profit', 0) >= 0 else "red"
        
        text = f"## 🔔 交易通知\n\n"
        text += f"**时间**: {timestamp}\n\n"
        text += f"**品种**: {trade_info['symbol']}\n\n"
        text += f"**动作**: <font color=\"{action_color}\">{trade_info['action']}</font>\n\n"
        text += f"**方向**: {trade_info.get('direction', 'N/A')}\n\n"
        text += f"**价格**: {trade_info.get('price', 'N/A')}\n\n"
        text += f"**数量**: {trade_info.get('volume', 'N/A')}\n\n"
        
        if 'profit' in trade_info:
            text += f"**盈亏**: <font color=\"{profit_color}\">{trade_info['profit']:+.2f}</font>\n\n"
        
        if 'strategy' in trade_info:
            text += f"**策略**: {trade_info['strategy']}\n\n"
        
        if 'reason' in trade_info:
            text += f"**原因**: {trade_info['reason']}\n\n"
        
        # 添加账户信息（如果有）
        if 'balance' in trade_info:
            text += "---\n"
            text += f"**账户余额**: {trade_info['balance']:.2f}\n\n"
            text += f"**净值**: {trade_info.get('equity', 'N/A')}\n\n"
        
        self.send_markdown(title, text)
    
    def send_signal_notification(self, signal_info: Dict[str, Any]):
        """发送信号通知"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        title = f"交易信号 - {signal_info['signal']}"
        
        text = f"## 📊 交易信号\n\n"
        text += f"**时间**: {timestamp}\n\n"
        text += f"**品种**: {signal_info['symbol']}\n\n"
        text += f"**信号**: **{signal_info['signal']}**\n\n"
        text += f"**策略**: {signal_info['strategy']}\n\n"
        text += f"**当前价格**: {signal_info.get('price', 'N/A')}\n\n"
        
        # 添加指标信息
        if 'indicators' in signal_info:
            text += f"**指标信息**: {signal_info['indicators']}\n\n"
        
        self.send_markdown(title, text)
    
    def send_daily_report(self, report_data: Dict[str, Any]):
        """发送每日报告"""
        title = "每日交易报告"
        
        text = f"## 📈 每日交易报告\n\n"
        text += f"**日期**: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        text += "### 交易统计\n"
        text += f"- 总交易次数: {report_data['total_trades']}\n"
        text += f"- 盈利交易: {report_data['winning_trades']} ({report_data['win_rate']:.1f}%)\n"
        text += f"- 亏损交易: {report_data['losing_trades']}\n\n"
        
        text += "### 盈亏分析\n"
        profit_color = "green" if report_data['total_profit'] >= 0 else "red"
        text += f"- 总盈亏: <font color=\"{profit_color}\">{report_data['total_profit']:+.2f}</font>\n"
        text += f"- 盈亏比: {report_data['profit_factor']:.2f}\n\n"
        
        text += "### 账户状态\n"
        text += f"- 初始余额: {report_data['start_balance']:.2f}\n"
        text += f"- 当前余额: {report_data['current_balance']:.2f}\n"
        change_color = "green" if report_data['balance_change'] >= 0 else "red"
        text += f"- 余额变化: <font color=\"{change_color}\">{report_data['balance_change']:+.2f} ({report_data['balance_change_percent']:+.1f}%)</font>\n\n"
        
        # 添加各币种表现
        if 'symbol_stats' in report_data:
            text += "### 各币种表现\n"
            for symbol, stats in report_data['symbol_stats'].items():
                text += f"**{symbol}**:\n"
                text += f"  - 交易: {stats['trades']}笔\n"
                text += f"  - 胜率: {stats['win_rate']:.1f}%\n"
                text += f"  - 盈亏: {stats['profit']:+.2f}\n"
        
        self.send_markdown(title, text, at_all=True)
    
    def send_error_notification(self, error_info: Dict[str, Any]):
        """发送错误通知"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        title = "⚠️ 系统错误"
        
        text = f"## ⚠️ 系统错误\n\n"
        text += f"**时间**: {timestamp}\n\n"
        text += f"**错误类型**: {error_info.get('type', '未知')}\n\n"
        text += f"**错误信息**: {error_info.get('message', '无')}\n\n"
        text += f"**影响品种**: {error_info.get('symbol', '全部')}\n\n"
        text += f"**建议操作**: {error_info.get('suggestion', '请检查系统状态')}\n"
        
        self.send_markdown(title, text, at_all=True)
    
    def send_optimization_report(self, opt_info: Dict[str, Any]):
        """发送参数优化报告"""
        title = "参数优化完成"
        
        text = f"## 🔧 参数优化报告\n\n"
        text += f"**策略**: {opt_info['strategy']}\n\n"
        text += f"**品种**: {opt_info['symbol']}\n\n"
        text += f"**测试组合**: {opt_info['test_combinations']}个\n\n"
        
        text += "### 最佳参数\n"
        for param, value in opt_info['best_params'].items():
            text += f"- {param}: {value}\n"
        
        text += f"\n### 预期表现\n"
        text += f"- 胜率: {opt_info['expected_win_rate']:.1f}%\n"
        text += f"- 盈亏比: {opt_info['expected_profit_factor']:.2f}\n"
        
        if opt_info.get('applied', False):
            text += f"\n✅ 新参数已应用"
        else:
            text += f"\n❌ 参数未应用（保持原设置）"
        
        self.send_markdown(title, text)
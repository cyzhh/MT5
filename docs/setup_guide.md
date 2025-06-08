# MT5智能交易系统 - 快速设置指南

## 📁 第一步：创建项目结构

1. 创建主项目文件夹：
```bash
mkdir MT5_Trading_System
cd MT5_Trading_System
```

2. 创建所有必要的子目录：
```bash
mkdir config strategies trading analysis monitoring ui
```

3. 在每个子目录中创建空的 `__init__.py` 文件：
```bash
# Windows
echo. > config\__init__.py
echo. > strategies\__init__.py
echo. > trading\__init__.py
echo. > analysis\__init__.py
echo. > monitoring\__init__.py
echo. > ui\__init__.py

# Linux/Mac
touch config/__init__.py strategies/__init__.py trading/__init__.py analysis/__init__.py monitoring/__init__.py ui/__init__.py
```

## 📄 第二步：复制文件到对应目录

将提供的文件复制到相应的目录：

### config/目录
- `settings.py`
- `logging_config.py`

### strategies/目录
- `base.py`
- `ma_strategy.py`
- `dkll_strategy.py`
- `rsi_strategy.py`
- `manager.py`

### trading/目录
- `mt5_connector.py`
- `order_manager.py`
- `position_manager.py`

### analysis/目录
- `performance_tracker.py`
- `optimizer.py`

### monitoring/目录
- `monitor.py`
- `auto_trader.py`

### ui/目录
- `menu.py`
- `diagnosis.py`

### 根目录
- `main.py`
- `requirements.txt`
- `README.md`

## ⚙️ 第三步：配置交易账户

编辑 `config/settings.py`，修改以下内容：

```python
# MT5账户配置
MT5_ACCOUNT = 你的账号  # 替换为您的MT5账号
MT5_PASSWORD = "你的密码"  # 替换为您的密码
MT5_SERVER = "你的服务器"  # 替换为您的服务器名称

# 交易品种
SYMBOL = "BTCUSD"  # 可以改为您要交易的品种
```

## 🔧 第四步：安装依赖

1. 创建虚拟环境（推荐）：
```bash
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

2. 安装依赖包：
```bash
pip install -r requirements.txt
```

## 🖥️ 第五步：准备MT5终端

1. 打开MetaTrader 5终端
2. 登录您的交易账户
3. 启用算法交易：
   - 工具 → 选项 → EA交易
   - 勾选"允许算法交易"
   - 勾选"允许DLL导入"
4. 确保要交易的品种在市场观察窗口中

## 🚀 第六步：运行程序

```bash
python main.py
```

## ✅ 验证安装

程序启动后，选择选项10（系统诊断）来验证所有组件是否正常工作。

## 🔍 常见问题

### 1. ModuleNotFoundError
确保所有`__init__.py`文件都已创建，并且您在项目根目录运行程序。

### 2. MT5连接失败
- 检查MT5终端是否已打开并登录
- 确认账户信息正确
- 检查防火墙设置

### 3. 无法获取品种信息
- 确认品种名称拼写正确（区分大小写）
- 在MT5市场观察中添加该品种
- 某些服务器的品种名称可能不同（如"BTCUSD"可能是"BTCUSD.c"）

## 📝 建议

1. **先用模拟账户测试**：在使用真实账户前，请充分测试所有功能
2. **从小交易量开始**：使用最小允许交易量（通常是0.01手）
3. **监控日志**：定期查看`trading_logs`目录中的日志文件
4. **定期备份**：备份您的配置和日志文件

祝您交易顺利！ 🎯
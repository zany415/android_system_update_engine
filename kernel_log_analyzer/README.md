# Kernel Log Analyzer - Android内核日志分析工具

一个基于PySide6的Android内核日志分析工具，专注于内核崩溃问题分析，特别是DDR位翻转故障检测。

## 功能特点

### 🔍 日志分析
- 解析Android内核日志（dmesg、kmsg等）
- 自动检测内核崩溃和panic
- 语法高亮显示关键信息
- 快速导航至崩溃位置

### 🎯 DDR故障检测
- 识别DDR位翻转相关的崩溃
- 检测ECC错误（单比特/多比特）
- 分析内存损坏模式
- 计算故障置信度评分

### 📚 知识库管理
- 本地SQLite数据库存储
- 故障模式知识积累
- 支持导入/导出JSON格式
- 多电脑知识库合并功能

### 🤖 机器学习支持
- 特征向量自动提取
- 训练数据集导出（JSON/CSV/NumPy）
- 训练/测试集自动划分
- 支持自定义标签

## 项目结构

```
kernel_log_analyzer/
├── main.py                     # 主入口
├── requirements.txt            # 依赖
├── README.md                   # 说明文档
│
├── config/                     # 配置层
│   ├── __init__.py
│   └── settings.py             # 配置和DDR检测模式
│
├── core/                       # 核心分析层
│   ├── __init__.py
│   ├── log_parser.py           # 日志解析器
│   ├── pattern_matcher.py      # 模式匹配器
│   ├── ddr_detector.py         # DDR位翻转检测器
│   └── crash_analyzer.py       # 崩溃综合分析器
│
├── database/                   # 数据库层
│   ├── __init__.py
│   ├── models.py               # 数据库模型
│   ├── db_manager.py           # 数据库管理器
│   └── knowledge_base.py       # 知识库管理
│
├── ml/                         # 机器学习层
│   ├── __init__.py
│   ├── feature_extractor.py    # 特征提取器
│   └── data_exporter.py        # ML数据导出器
│
├── ui/                         # UI层
│   ├── __init__.py
│   ├── main_window.py          # 主窗口
│   ├── log_view.py             # 日志视图
│   ├── analysis_view.py        # 分析视图
│   ├── knowledge_view.py       # 知识库视图
│   └── widgets/
│       ├── __init__.py
│       └── custom_widgets.py   # 自定义控件
│
└── utils/                      # 工具层
    ├── __init__.py
    ├── file_utils.py           # 文件工具
    └── export_utils.py         # 导出工具
```

## 技术栈分层

| 层级 | 职责 | 主要技术 |
|------|------|----------|
| **UI层** | 用户界面 | PySide6, Qt |
| **核心层** | 日志分析、模式匹配 | Python正则表达式 |
| **数据库层** | 数据持久化 | SQLAlchemy, SQLite |
| **ML层** | 特征提取、数据导出 | NumPy, Pandas |
| **工具层** | 通用工具函数 | Python标准库 |
| **配置层** | 配置管理 | dataclass |

## 安装

### 环境要求

- Python 3.9+
- PySide6 6.5+

### 安装步骤

```bash
# 克隆或进入项目目录
cd kernel_log_analyzer

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

### 启动程序

```bash
python main.py
```

### 基本工作流程

1. **打开日志文件**
   - 点击"打开日志文件"或使用 `Ctrl+O`
   - 支持 .log, .txt, .dmesg, .kmsg 格式

2. **查看和浏览日志**
   - 左侧显示检测到的崩溃列表
   - 点击崩溃项快速跳转
   - 使用搜索功能查找特定内容

3. **分析崩溃**
   - 切换到"崩溃分析"标签页
   - 点击"开始分析"
   - 查看分析结果和DDR相关性

4. **管理知识库**
   - 切换到"知识库"标签页
   - 保存有价值的故障模式
   - 导入/导出知识库文件

5. **导出ML数据**
   - 在知识库标签页选择"机器学习数据"
   - 配置导出选项
   - 导出训练数据集

## DDR位翻转检测模式

工具内置了多种DDR故障检测模式：

### ECC错误
- EDAC CE/UE 错误
- 单比特/多比特 ECC 错误
- 内存控制器错误

### 位翻转特征
- Single Event Upset (SEU)
- Multi-Bit Upset (MBU)
- 内存数据损坏

### 内存错误
- SLUB/SLAB 损坏
- Bad page state
- NULL指针解引用（可能由位翻转导致）

## 知识库导入导出

### 导出格式

```json
{
  "version": "1.0",
  "export_time": "2024-01-01T12:00:00",
  "source_machine": "hostname_abc123",
  "knowledge_entries": [
    {
      "title": "ECC单比特错误",
      "category": "DDR",
      "signature_pattern": "EDAC.*CE.*error",
      "description": "...",
      "ml_label": "ddr_related"
    }
  ]
}
```

### 合并多个知识库

支持从不同电脑合并知识库：

1. 在各电脑上导出知识库JSON文件
2. 将文件集中到一台电脑
3. 使用"合并多个知识库"功能
4. 导入合并后的知识库

## ML训练数据格式

### JSON格式
```json
{
  "samples": [
    {
      "id": "crash_1",
      "text": "原始日志文本",
      "label": "ddr_related",
      "features": {
        "numeric_vector": [1.0, 0.0, 0.85, ...]
      }
    }
  ]
}
```

### CSV格式
包含数值特征向量，可直接用于scikit-learn等框架。

### NumPy格式
- `features.npy` - 特征矩阵
- `labels.npy` - 标签数组

## 配置文件

配置位于 `config/settings.py`：

```python
# 窗口设置
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# 数据库设置
DB_NAME = "kernel_knowledge.db"

# DDR检测模式
BIT_FLIP_PATTERNS = [
    r"EDAC.*CE.*error",
    r"ECC.*single.*bit.*error",
    ...
]
```

## 数据存储位置

默认数据目录：`~/.kernel_log_analyzer/`

- 数据库：`kernel_knowledge.db`
- 导出文件：`exports/`

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开日志文件 |
| Ctrl+E | 导出报告 |
| Ctrl+Shift+A | 开始分析 |
| Ctrl+Q | 退出程序 |

## 开发扩展

### 添加新的检测模式

在 `config/settings.py` 中添加：

```python
BIT_FLIP_PATTERNS.append(r"your_new_pattern")
```

### 添加新的故障类型

在 `core/ddr_detector.py` 中扩展 `DDRFaultType` 枚举。

### 自定义特征提取

在 `ml/feature_extractor.py` 中修改 `FeatureVector` 类。

## 许可证

Apache License 2.0

## 贡献

欢迎提交Issue和Pull Request！

"""
自定义控件 - 提供自定义的UI组件
"""
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QSyntaxHighlighter, QTextCharFormat, QColor, 
    QFont, QTextDocument
)
import re


class LogHighlighter(QSyntaxHighlighter):
    """日志语法高亮器"""
    
    def __init__(self, parent: QTextDocument = None):
        super().__init__(parent)
        self._init_formats()
        self._init_rules()
    
    def _init_formats(self):
        """初始化文本格式"""
        # 时间戳格式
        self.timestamp_format = QTextCharFormat()
        self.timestamp_format.setForeground(QColor("#6c757d"))
        
        # 错误格式
        self.error_format = QTextCharFormat()
        self.error_format.setForeground(QColor("#dc3545"))
        self.error_format.setFontWeight(QFont.Weight.Bold)
        
        # 警告格式
        self.warning_format = QTextCharFormat()
        self.warning_format.setForeground(QColor("#ffc107"))
        
        # DDR相关格式
        self.ddr_format = QTextCharFormat()
        self.ddr_format.setBackground(QColor("#fff3cd"))
        self.ddr_format.setForeground(QColor("#856404"))
        
        # 地址格式
        self.address_format = QTextCharFormat()
        self.address_format.setForeground(QColor("#007bff"))
        
        # 函数名格式
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#28a745"))
        
        # 崩溃关键字格式
        self.crash_format = QTextCharFormat()
        self.crash_format.setBackground(QColor("#f8d7da"))
        self.crash_format.setForeground(QColor("#721c24"))
        self.crash_format.setFontWeight(QFont.Weight.Bold)
    
    def _init_rules(self):
        """初始化高亮规则"""
        self.rules = []
        
        # 时间戳
        self.rules.append((
            re.compile(r'\[\s*\d+\.\d+\]'),
            self.timestamp_format
        ))
        
        # 错误关键字
        self.rules.append((
            re.compile(r'\b(error|fail|failed|fault|invalid)\b', re.IGNORECASE),
            self.error_format
        ))
        
        # 警告关键字
        self.rules.append((
            re.compile(r'\b(warning|warn)\b', re.IGNORECASE),
            self.warning_format
        ))
        
        # DDR/内存相关
        self.rules.append((
            re.compile(r'\b(ECC|EDAC|DDR|DRAM|bit\s*flip|memory\s*error|corruption)\b', re.IGNORECASE),
            self.ddr_format
        ))
        
        # 地址
        self.rules.append((
            re.compile(r'\b0x[0-9a-fA-F]+\b'),
            self.address_format
        ))
        
        # 函数名（调用栈中的）
        self.rules.append((
            re.compile(r'\[<[0-9a-fA-F]+>\]\s*(\w+)'),
            self.function_format
        ))
        
        # 崩溃关键字
        self.rules.append((
            re.compile(r'\b(panic|oops|BUG|Call\s+[Tt]race|Unable\s+to\s+handle)\b'),
            self.crash_format
        ))
    
    def highlightBlock(self, text: str):
        """高亮一行文本"""
        for pattern, format in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class ClickableLabel(QLabel):
    """可点击的标签"""
    clicked = Signal()
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class StatCard(QFrame):
    """统计卡片控件"""
    
    def __init__(
        self, 
        title: str, 
        value: str = "0", 
        color: str = "#007bff",
        parent=None
    ):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            StatCard {{
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                border-left: 4px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # 标题
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(self.title_label)
        
        # 值
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {color};
        """)
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str):
        """设置值"""
        self.value_label.setText(value)
    
    def set_title(self, title: str):
        """设置标题"""
        self.title_label.setText(title)


class ConfidenceBar(QWidget):
    """置信度条控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标签
        self.label = QLabel("置信度:")
        self.label.setFixedWidth(60)
        layout.addWidget(self.label)
        
        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v%")
        layout.addWidget(self.progress)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setFixedWidth(80)
        layout.addWidget(self.status_label)
        
        self._update_style(0)
    
    def set_value(self, confidence: float):
        """设置置信度值（0-1）"""
        value = int(confidence * 100)
        self.progress.setValue(value)
        self._update_style(value)
    
    def _update_style(self, value: int):
        """更新样式"""
        if value >= 80:
            color = "#dc3545"  # 红色
            status = "高置信度"
        elif value >= 50:
            color = "#ffc107"  # 黄色
            status = "中置信度"
        else:
            color = "#28a745"  # 绿色
            status = "低置信度"
        
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")


class SearchBar(QWidget):
    """搜索栏控件"""
    searchRequested = Signal(str)
    filterChanged = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日志内容...")
        self.search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_input)
        
        # 搜索按钮
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        layout.addWidget(self.search_btn)
        
        # 清除按钮
        self.clear_btn = QPushButton("清除")
        self.clear_btn.clicked.connect(self._on_clear)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        layout.addWidget(self.clear_btn)
    
    def _on_search(self):
        """搜索事件"""
        text = self.search_input.text().strip()
        if text:
            self.searchRequested.emit(text)
    
    def _on_clear(self):
        """清除事件"""
        self.search_input.clear()
        self.searchRequested.emit("")
    
    def get_text(self) -> str:
        """获取搜索文本"""
        return self.search_input.text().strip()

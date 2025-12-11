"""
日志视图 - 显示和浏览日志内容
"""
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QLabel, QPushButton, QFileDialog, QSplitter,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor

from .widgets.custom_widgets import LogHighlighter, SearchBar
from core.log_parser import LogParser, LogEntry
from utils.file_utils import FileUtils


class LogView(QWidget):
    """日志视图组件"""
    
    # 信号
    fileLoaded = Signal(str)  # 文件加载完成
    crashSelected = Signal(int)  # 选中崩溃行
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_parser = LogParser()
        self.current_file: Optional[Path] = None
        self.crash_lines: List[int] = []
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 搜索栏
        self.search_bar = SearchBar()
        self.search_bar.searchRequested.connect(self._on_search)
        layout.addWidget(self.search_bar)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：崩溃列表
        crash_panel = self._create_crash_panel()
        splitter.addWidget(crash_panel)
        
        # 右侧：日志内容
        log_panel = self._create_log_panel()
        splitter.addWidget(log_panel)
        
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #6c757d; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 打开文件按钮
        self.open_btn = QPushButton("📂 打开日志文件")
        self.open_btn.clicked.connect(self._on_open_file)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        layout.addWidget(self.open_btn)
        
        # 文件信息
        self.file_label = QLabel("未加载文件")
        self.file_label.setStyleSheet("color: #6c757d; margin-left: 10px;")
        layout.addWidget(self.file_label)
        
        layout.addStretch()
        
        # 跳转到下一个崩溃
        self.next_crash_btn = QPushButton("下一个崩溃 ▼")
        self.next_crash_btn.clicked.connect(self._goto_next_crash)
        self.next_crash_btn.setEnabled(False)
        layout.addWidget(self.next_crash_btn)
        
        # 跳转到上一个崩溃
        self.prev_crash_btn = QPushButton("▲ 上一个崩溃")
        self.prev_crash_btn.clicked.connect(self._goto_prev_crash)
        self.prev_crash_btn.setEnabled(False)
        layout.addWidget(self.prev_crash_btn)
        
        return toolbar
    
    def _create_crash_panel(self) -> QWidget:
        """创建崩溃列表面板"""
        panel = QGroupBox("检测到的崩溃")
        layout = QVBoxLayout(panel)
        
        self.crash_list = QListWidget()
        self.crash_list.itemClicked.connect(self._on_crash_item_clicked)
        self.crash_list.setStyleSheet("""
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.crash_list)
        
        # 统计信息
        self.crash_stats_label = QLabel("共 0 个崩溃")
        self.crash_stats_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.crash_stats_label)
        
        return panel
    
    def _create_log_panel(self) -> QWidget:
        """创建日志内容面板"""
        panel = QGroupBox("日志内容")
        layout = QVBoxLayout(panel)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        # 添加语法高亮
        self.highlighter = LogHighlighter(self.log_text.document())
        
        layout.addWidget(self.log_text)
        
        # 行号信息
        self.line_info_label = QLabel("行: 0 / 0")
        self.line_info_label.setStyleSheet("color: #6c757d;")
        layout.addWidget(self.line_info_label)
        
        return panel
    
    def _on_open_file(self):
        """打开文件对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开日志文件",
            "",
            "日志文件 (*.log *.txt *.dmesg *.kmsg);;所有文件 (*.*)"
        )
        
        if file_path:
            self.load_file(Path(file_path))
    
    def load_file(self, file_path: Path):
        """加载日志文件"""
        try:
            self.current_file = file_path
            
            # 读取文件
            content, encoding = FileUtils.read_file_with_fallback(file_path)
            
            # 显示内容
            self.log_text.setPlainText(content)
            
            # 解析日志
            self.log_parser.parse_text(content)
            
            # 更新文件信息
            file_info = FileUtils.get_file_info(file_path)
            self.file_label.setText(
                f"📄 {file_info['name']} ({file_info['size_human']}) - {encoding}"
            )
            
            # 查找崩溃
            self._find_crashes()
            
            # 更新状态
            self.status_label.setText(f"已加载 {len(self.log_parser)} 行")
            self._update_line_info()
            
            # 发送信号
            self.fileLoaded.emit(str(file_path))
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载文件: {str(e)}")
    
    def _find_crashes(self):
        """查找日志中的崩溃"""
        self.crash_list.clear()
        self.crash_lines = []
        
        from core.pattern_matcher import PatternMatcher
        matcher = PatternMatcher()
        
        for entry in self.log_parser.entries:
            is_crash, patterns = matcher.is_kernel_crash(entry.raw_text)
            if is_crash:
                crash_type = matcher.extract_crash_type(entry.raw_text)
                self.crash_lines.append(entry.line_number)
                
                # 添加到列表
                item = QListWidgetItem(
                    f"[行 {entry.line_number}] {crash_type}"
                )
                item.setData(Qt.ItemDataRole.UserRole, entry.line_number)
                
                # 检查是否DDR相关
                is_ddr, confidence, _ = matcher.is_ddr_related(entry.raw_text)
                if is_ddr:
                    item.setBackground(Qt.GlobalColor.yellow)
                    item.setText(f"⚠️ {item.text()} (DDR: {confidence:.0%})")
                
                self.crash_list.addItem(item)
        
        # 更新统计
        self.crash_stats_label.setText(f"共 {len(self.crash_lines)} 个崩溃")
        
        # 启用/禁用导航按钮
        has_crashes = len(self.crash_lines) > 0
        self.next_crash_btn.setEnabled(has_crashes)
        self.prev_crash_btn.setEnabled(has_crashes)
    
    def _on_crash_item_clicked(self, item: QListWidgetItem):
        """崩溃项点击事件"""
        line_number = item.data(Qt.ItemDataRole.UserRole)
        self._goto_line(line_number)
        self.crashSelected.emit(line_number)
    
    def _goto_line(self, line_number: int):
        """跳转到指定行"""
        cursor = self.log_text.textCursor()
        
        # 移动到指定行
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(line_number - 1):
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        
        # 选中该行
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock, 
            QTextCursor.MoveMode.KeepAnchor
        )
        
        self.log_text.setTextCursor(cursor)
        self.log_text.centerCursor()
        self._update_line_info()
    
    def _goto_next_crash(self):
        """跳转到下一个崩溃"""
        if not self.crash_lines:
            return
        
        current_line = self._get_current_line()
        
        for line in self.crash_lines:
            if line > current_line:
                self._goto_line(line)
                return
        
        # 循环到第一个
        self._goto_line(self.crash_lines[0])
    
    def _goto_prev_crash(self):
        """跳转到上一个崩溃"""
        if not self.crash_lines:
            return
        
        current_line = self._get_current_line()
        
        for line in reversed(self.crash_lines):
            if line < current_line:
                self._goto_line(line)
                return
        
        # 循环到最后一个
        self._goto_line(self.crash_lines[-1])
    
    def _get_current_line(self) -> int:
        """获取当前行号"""
        cursor = self.log_text.textCursor()
        return cursor.blockNumber() + 1
    
    def _update_line_info(self):
        """更新行号信息"""
        current_line = self._get_current_line()
        total_lines = len(self.log_parser) if self.log_parser else 0
        self.line_info_label.setText(f"行: {current_line} / {total_lines}")
    
    def _on_search(self, text: str):
        """搜索事件"""
        if not text:
            return
        
        # 从当前位置开始搜索
        found = self.log_text.find(text)
        
        if not found:
            # 从头开始搜索
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_text.setTextCursor(cursor)
            
            found = self.log_text.find(text)
            
            if not found:
                self.status_label.setText(f"未找到: {text}")
            else:
                self.status_label.setText(f"已找到: {text}")
        else:
            self.status_label.setText(f"已找到: {text}")
        
        self._update_line_info()
    
    def get_log_parser(self) -> LogParser:
        """获取日志解析器"""
        return self.log_parser
    
    def get_current_file(self) -> Optional[Path]:
        """获取当前文件路径"""
        return self.current_file
    
    def get_selected_text(self) -> str:
        """获取选中的文本"""
        return self.log_text.textCursor().selectedText()

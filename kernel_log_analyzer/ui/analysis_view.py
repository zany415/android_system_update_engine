"""
分析视图 - 显示崩溃分析结果
"""
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QPushButton, QGroupBox,
    QTextEdit, QSplitter, QHeaderView, QMessageBox,
    QProgressDialog, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor

from .widgets.custom_widgets import StatCard, ConfidenceBar
from core.crash_analyzer import CrashAnalyzer, CrashAnalysisResult
from core.ddr_detector import DDRFaultType
from database.db_manager import DatabaseManager
from database.knowledge_base import KnowledgeBase
from utils.export_utils import ExportUtils
from config.settings import settings


class AnalysisWorker(QThread):
    """分析工作线程"""
    finished = Signal(list)  # 分析完成信号
    progress = Signal(int)   # 进度信号
    error = Signal(str)      # 错误信号
    
    def __init__(self, text: str):
        super().__init__()
        self.text = text
    
    def run(self):
        try:
            analyzer = CrashAnalyzer()
            results = analyzer.analyze_text(self.text)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class AnalysisView(QWidget):
    """分析视图组件"""
    
    # 信号
    analysisComplete = Signal(list)  # 分析完成
    resultSelected = Signal(object)  # 选中结果
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analyzer = CrashAnalyzer()
        self.results: List[CrashAnalysisResult] = []
        self.db_manager = DatabaseManager()
        self.knowledge_base = KnowledgeBase(self.db_manager)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        
        self.total_card = StatCard("总崩溃数", "0", "#007bff")
        stats_layout.addWidget(self.total_card)
        
        self.ddr_card = StatCard("DDR相关", "0", "#dc3545")
        stats_layout.addWidget(self.ddr_card)
        
        self.non_ddr_card = StatCard("非DDR", "0", "#28a745")
        stats_layout.addWidget(self.non_ddr_card)
        
        self.confidence_card = StatCard("平均置信度", "0%", "#ffc107")
        stats_layout.addWidget(self.confidence_card)
        
        layout.addLayout(stats_layout)
        
        # 工具栏
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 结果表格
        table_panel = self._create_table_panel()
        splitter.addWidget(table_panel)
        
        # 详情面板
        detail_panel = self._create_detail_panel()
        splitter.addWidget(detail_panel)
        
        splitter.setSizes([400, 300])
        layout.addWidget(splitter)
    
    def _create_toolbar(self) -> QWidget:
        """创建工具栏"""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 分析按钮
        self.analyze_btn = QPushButton("🔍 开始分析")
        self.analyze_btn.clicked.connect(self._on_analyze)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        layout.addWidget(self.analyze_btn)
        
        # 过滤器
        layout.addWidget(QLabel("过滤:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "仅DDR相关", "仅非DDR"])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_combo)
        
        layout.addStretch()
        
        # 保存到知识库
        self.save_kb_btn = QPushButton("💾 保存到知识库")
        self.save_kb_btn.clicked.connect(self._save_to_knowledge_base)
        self.save_kb_btn.setEnabled(False)
        layout.addWidget(self.save_kb_btn)
        
        # 导出按钮
        self.export_btn = QPushButton("📤 导出报告")
        self.export_btn.clicked.connect(self._export_report)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        
        return toolbar
    
    def _create_table_panel(self) -> QWidget:
        """创建结果表格面板"""
        panel = QGroupBox("分析结果")
        layout = QVBoxLayout(panel)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(7)
        self.result_table.setHorizontalHeaderLabels([
            "序号", "崩溃类型", "顶层函数", "故障地址", 
            "DDR相关", "置信度", "DDR故障类型"
        ])
        
        # 设置列宽
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        
        self.result_table.setColumnWidth(0, 50)
        self.result_table.setColumnWidth(3, 120)
        self.result_table.setColumnWidth(4, 80)
        self.result_table.setColumnWidth(5, 80)
        
        self.result_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.result_table.setAlternatingRowColors(True)
        self.result_table.cellClicked.connect(self._on_row_selected)
        
        layout.addWidget(self.result_table)
        
        return panel
    
    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        panel = QGroupBox("详细信息")
        layout = QVBoxLayout(panel)
        
        # 置信度条
        self.confidence_bar = ConfidenceBar()
        layout.addWidget(self.confidence_bar)
        
        # 详情文本
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.detail_text)
        
        return panel
    
    def _on_analyze(self):
        """开始分析"""
        # 获取日志内容（需要从主窗口获取）
        parent = self.parent()
        while parent and not hasattr(parent, 'log_view'):
            parent = parent.parent()
        
        if not parent or not hasattr(parent, 'log_view'):
            QMessageBox.warning(self, "警告", "请先加载日志文件")
            return
        
        log_parser = parent.log_view.get_log_parser()
        if not log_parser.entries:
            QMessageBox.warning(self, "警告", "请先加载日志文件")
            return
        
        # 获取日志文本
        text = "\n".join(e.raw_text for e in log_parser.entries)
        
        # 显示进度对话框
        progress = QProgressDialog("正在分析...", "取消", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # 在工作线程中分析
        self.worker = AnalysisWorker(text)
        self.worker.finished.connect(lambda r: self._on_analysis_complete(r, progress))
        self.worker.error.connect(lambda e: self._on_analysis_error(e, progress))
        self.worker.start()
    
    def _on_analysis_complete(self, results: List[CrashAnalysisResult], progress):
        """分析完成回调"""
        progress.close()
        self.results = results
        self._display_results()
        self._update_stats()
        
        # 启用按钮
        self.export_btn.setEnabled(len(results) > 0)
        self.save_kb_btn.setEnabled(len(results) > 0)
        
        # 发送信号
        self.analysisComplete.emit(results)
        
        QMessageBox.information(
            self, "分析完成", 
            f"共发现 {len(results)} 个崩溃，其中 "
            f"{sum(1 for r in results if r.is_ddr_related)} 个与DDR相关"
        )
    
    def _on_analysis_error(self, error: str, progress):
        """分析错误回调"""
        progress.close()
        QMessageBox.critical(self, "错误", f"分析失败: {error}")
    
    def _display_results(self):
        """显示分析结果"""
        self.result_table.setRowCount(len(self.results))
        
        for row, result in enumerate(self.results):
            # 序号
            self.result_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # 崩溃类型
            self.result_table.setItem(row, 1, QTableWidgetItem(result.crash_type))
            
            # 顶层函数
            self.result_table.setItem(
                row, 2, 
                QTableWidgetItem(result.top_function or "N/A")
            )
            
            # 故障地址
            addr = f"0x{result.fault_address}" if result.fault_address else "N/A"
            self.result_table.setItem(row, 3, QTableWidgetItem(addr))
            
            # DDR相关
            ddr_item = QTableWidgetItem("是" if result.is_ddr_related else "否")
            if result.is_ddr_related:
                ddr_item.setBackground(QColor("#fff3cd"))
            self.result_table.setItem(row, 4, ddr_item)
            
            # 置信度
            confidence_item = QTableWidgetItem(f"{result.ddr_confidence:.0%}")
            if result.ddr_confidence >= 0.8:
                confidence_item.setBackground(QColor("#f8d7da"))
            elif result.ddr_confidence >= 0.5:
                confidence_item.setBackground(QColor("#fff3cd"))
            self.result_table.setItem(row, 5, confidence_item)
            
            # DDR故障类型
            fault_type = result.ddr_result.fault_type.value if result.ddr_result else "N/A"
            self.result_table.setItem(row, 6, QTableWidgetItem(fault_type))
    
    def _update_stats(self):
        """更新统计信息"""
        total = len(self.results)
        ddr_count = sum(1 for r in self.results if r.is_ddr_related)
        non_ddr = total - ddr_count
        
        self.total_card.set_value(str(total))
        self.ddr_card.set_value(str(ddr_count))
        self.non_ddr_card.set_value(str(non_ddr))
        
        if ddr_count > 0:
            avg_confidence = sum(
                r.ddr_confidence for r in self.results if r.is_ddr_related
            ) / ddr_count
            self.confidence_card.set_value(f"{avg_confidence:.0%}")
        else:
            self.confidence_card.set_value("N/A")
    
    def _on_row_selected(self, row: int, col: int):
        """行选中事件"""
        if row < len(self.results):
            result = self.results[row]
            self._show_detail(result)
            self.resultSelected.emit(result)
    
    def _show_detail(self, result: CrashAnalysisResult):
        """显示详细信息"""
        # 更新置信度条
        self.confidence_bar.set_value(result.ddr_confidence)
        
        # 构建详情文本
        lines = [
            f"=== 崩溃分析详情 ===",
            f"",
            f"崩溃类型: {result.crash_type}",
            f"崩溃签名: {result.crash_signature}",
            f"时间戳: {result.timestamp}",
            f"",
            f"--- 地址信息 ---",
            f"故障地址: {result.fault_address or 'N/A'}",
            f"PC: {result.pc_address or 'N/A'}",
            f"LR: {result.lr_address or 'N/A'}",
            f"",
            f"--- 调用栈 ---",
        ]
        
        for i, func in enumerate(result.call_trace[:10], 1):
            lines.append(f"  {i}. {func}")
        
        if len(result.call_trace) > 10:
            lines.append(f"  ... 还有 {len(result.call_trace) - 10} 个")
        
        lines.extend([
            f"",
            f"--- DDR分析 ---",
            f"DDR相关: {'是' if result.is_ddr_related else '否'}",
            f"置信度: {result.ddr_confidence:.1%}",
        ])
        
        if result.ddr_result:
            lines.extend([
                f"故障类型: {result.ddr_result.fault_type.value}",
                f"内存区域: {result.ddr_result.memory_region or 'N/A'}",
                f"可纠正: {result.ddr_result.is_correctable}",
            ])
            
            if result.ddr_result.bit_positions:
                lines.append(f"翻转位: {result.ddr_result.bit_positions}")
        
        lines.extend([
            f"",
            f"--- 分析说明 ---",
        ])
        for note in result.analysis_notes:
            lines.append(f"• {note}")
        
        lines.extend([
            f"",
            f"--- 匹配模式 ---",
        ])
        for pattern in result.matched_patterns[:10]:
            lines.append(f"• {pattern}")
        
        self.detail_text.setPlainText("\n".join(lines))
    
    def _apply_filter(self, index: int):
        """应用过滤"""
        for row in range(self.result_table.rowCount()):
            show = True
            if index == 1:  # 仅DDR相关
                show = self.results[row].is_ddr_related
            elif index == 2:  # 仅非DDR
                show = not self.results[row].is_ddr_related
            
            self.result_table.setRowHidden(row, not show)
    
    def _save_to_knowledge_base(self):
        """保存到知识库"""
        if not self.results:
            return
        
        saved_count = 0
        for result in self.results:
            if result.is_ddr_related:
                # 保存崩溃记录
                parent = self.parent()
                while parent and not hasattr(parent, 'log_view'):
                    parent = parent.parent()
                
                file_path = ""
                if parent and hasattr(parent, 'log_view'):
                    current_file = parent.log_view.get_current_file()
                    if current_file:
                        file_path = str(current_file)
                
                crash_record = result.to_crash_record(file_path)
                saved_record = self.db_manager.add_crash_record(crash_record)
                
                # 添加DDR故障记录
                if result.ddr_result:
                    ddr_record = result.to_ddr_fault_record()
                    if ddr_record and saved_record:
                        self.db_manager.add_ddr_fault_record(
                            saved_record.id, ddr_record
                        )
                
                # 添加到知识库
                self.knowledge_base.add_from_crash_analysis(
                    crash_record,
                    category="DDR",
                    auto_confirm=result.ddr_confidence >= 0.8
                )
                
                saved_count += 1
        
        QMessageBox.information(
            self, "保存成功", 
            f"已保存 {saved_count} 条DDR相关记录到知识库"
        )
    
    def _export_report(self):
        """导出报告"""
        if not self.results:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出报告",
            str(settings.export_dir / "crash_report.html"),
            "HTML文件 (*.html);;JSON文件 (*.json);;CSV文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            data = self.analyzer.export_results()
            
            if file_path.endswith('.html'):
                ExportUtils.export_to_html(
                    data, 
                    file_path,
                    title="内核崩溃分析报告",
                    headers=["crash_type", "top_function", "is_ddr_related", 
                            "ddr_confidence", "fault_address"]
                )
            elif file_path.endswith('.json'):
                ExportUtils.export_to_json(data, file_path)
            else:
                ExportUtils.export_to_csv(data, file_path)
            
            QMessageBox.information(self, "导出成功", f"报告已导出到: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
    
    def analyze_text(self, text: str) -> List[CrashAnalysisResult]:
        """直接分析文本"""
        self.results = self.analyzer.analyze_text(text)
        self._display_results()
        self._update_stats()
        return self.results

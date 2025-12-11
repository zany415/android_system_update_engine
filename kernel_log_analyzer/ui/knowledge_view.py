"""
知识库视图 - 管理DDR故障知识库
"""
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QLabel, QPushButton, QGroupBox,
    QTextEdit, QSplitter, QHeaderView, QMessageBox,
    QFileDialog, QLineEdit, QComboBox, QCheckBox,
    QDialog, QFormLayout, QDialogButtonBox, QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from .widgets.custom_widgets import StatCard, SearchBar
from database.db_manager import DatabaseManager
from database.knowledge_base import KnowledgeBase
from database.models import KnowledgeEntry
from ml.data_exporter import MLDataExporter
from config.settings import settings


class KnowledgeEntryDialog(QDialog):
    """知识条目编辑对话框"""
    
    def __init__(self, entry: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.entry = entry or {}
        self.setWindowTitle("编辑知识条目" if entry else "新建知识条目")
        self.setMinimumWidth(500)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # 标题
        self.title_edit = QLineEdit(self.entry.get('title', ''))
        form.addRow("标题:", self.title_edit)
        
        # 分类
        self.category_combo = QComboBox()
        self.category_combo.addItems(["DDR", "内核", "驱动", "内存", "其他"])
        self.category_combo.setCurrentText(self.entry.get('category', 'DDR'))
        form.addRow("分类:", self.category_combo)
        
        # 签名模式
        self.signature_edit = QLineEdit(self.entry.get('signature_pattern', ''))
        form.addRow("签名模式:", self.signature_edit)
        
        # 描述
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(self.entry.get('description', ''))
        self.desc_edit.setMaximumHeight(100)
        form.addRow("描述:", self.desc_edit)
        
        # 根本原因
        self.cause_edit = QTextEdit()
        self.cause_edit.setPlainText(self.entry.get('root_cause', ''))
        self.cause_edit.setMaximumHeight(100)
        form.addRow("根本原因:", self.cause_edit)
        
        # 解决方案
        self.solution_edit = QTextEdit()
        self.solution_edit.setPlainText(self.entry.get('solution', ''))
        self.solution_edit.setMaximumHeight(100)
        form.addRow("解决方案:", self.solution_edit)
        
        # ML标签
        self.ml_label_combo = QComboBox()
        self.ml_label_combo.addItems(["ddr_related", "non_ddr", "uncertain"])
        self.ml_label_combo.setCurrentText(self.entry.get('ml_label', 'ddr_related'))
        form.addRow("ML标签:", self.ml_label_combo)
        
        # 已确认
        self.confirmed_check = QCheckBox()
        self.confirmed_check.setChecked(self.entry.get('confirmed', False))
        form.addRow("已确认:", self.confirmed_check)
        
        layout.addLayout(form)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_data(self) -> dict:
        """获取表单数据"""
        return {
            'title': self.title_edit.text(),
            'category': self.category_combo.currentText(),
            'signature_pattern': self.signature_edit.text(),
            'description': self.desc_edit.toPlainText(),
            'root_cause': self.cause_edit.toPlainText(),
            'solution': self.solution_edit.toPlainText(),
            'ml_label': self.ml_label_combo.currentText(),
            'confirmed': self.confirmed_check.isChecked(),
        }


class KnowledgeView(QWidget):
    """知识库视图组件"""
    
    # 信号
    entrySelected = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.knowledge_base = KnowledgeBase(self.db_manager)
        self.ml_exporter = MLDataExporter(self.db_manager)
        self.entries: List[dict] = []
        
        self._init_ui()
        self._load_entries()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        
        self.total_card = StatCard("总条目数", "0", "#007bff")
        stats_layout.addWidget(self.total_card)
        
        self.confirmed_card = StatCard("已确认", "0", "#28a745")
        stats_layout.addWidget(self.confirmed_card)
        
        self.ddr_card = StatCard("DDR分类", "0", "#dc3545")
        stats_layout.addWidget(self.ddr_card)
        
        self.occurrence_card = StatCard("总出现次数", "0", "#ffc107")
        stats_layout.addWidget(self.occurrence_card)
        
        layout.addLayout(stats_layout)
        
        # 标签页
        tabs = QTabWidget()
        
        # 知识库管理标签页
        kb_tab = self._create_kb_tab()
        tabs.addTab(kb_tab, "📚 知识库管理")
        
        # 导入导出标签页
        io_tab = self._create_io_tab()
        tabs.addTab(io_tab, "📤 导入/导出")
        
        # ML数据标签页
        ml_tab = self._create_ml_tab()
        tabs.addTab(ml_tab, "🤖 机器学习数据")
        
        layout.addWidget(tabs)
    
    def _create_kb_tab(self) -> QWidget:
        """创建知识库管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 搜索
        self.search_bar = SearchBar()
        self.search_bar.searchRequested.connect(self._on_search)
        toolbar.addWidget(self.search_bar)
        
        # 过滤
        toolbar.addWidget(QLabel("分类:"))
        self.category_filter = QComboBox()
        self.category_filter.addItems(["全部", "DDR", "内核", "驱动", "内存", "其他"])
        self.category_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.category_filter)
        
        # 仅显示已确认
        self.confirmed_filter = QCheckBox("仅已确认")
        self.confirmed_filter.stateChanged.connect(self._apply_filter)
        toolbar.addWidget(self.confirmed_filter)
        
        toolbar.addStretch()
        
        # 新建按钮
        self.new_btn = QPushButton("➕ 新建")
        self.new_btn.clicked.connect(self._on_new_entry)
        toolbar.addWidget(self.new_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._load_entries)
        toolbar.addWidget(self.refresh_btn)
        
        layout.addLayout(toolbar)
        
        # 分割器
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 条目表格
        table_panel = self._create_table_panel()
        splitter.addWidget(table_panel)
        
        # 详情面板
        detail_panel = self._create_detail_panel()
        splitter.addWidget(detail_panel)
        
        splitter.setSizes([400, 200])
        layout.addWidget(splitter)
        
        return widget
    
    def _create_table_panel(self) -> QWidget:
        """创建条目表格面板"""
        panel = QGroupBox("知识库条目")
        layout = QVBoxLayout(panel)
        
        self.entry_table = QTableWidget()
        self.entry_table.setColumnCount(7)
        self.entry_table.setHorizontalHeaderLabels([
            "ID", "标题", "分类", "签名模式", "出现次数", "已确认", "ML标签"
        ])
        
        header = self.entry_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.entry_table.setColumnWidth(0, 50)
        self.entry_table.setColumnWidth(2, 80)
        self.entry_table.setColumnWidth(4, 80)
        self.entry_table.setColumnWidth(5, 70)
        self.entry_table.setColumnWidth(6, 100)
        
        self.entry_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entry_table.setAlternatingRowColors(True)
        self.entry_table.cellClicked.connect(self._on_entry_selected)
        self.entry_table.cellDoubleClicked.connect(self._on_entry_edit)
        
        layout.addWidget(self.entry_table)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("✏️ 编辑")
        self.edit_btn.clicked.connect(self._on_edit_entry)
        self.edit_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_btn)
        
        self.confirm_btn = QPushButton("✅ 确认")
        self.confirm_btn.clicked.connect(self._on_confirm_entry)
        self.confirm_btn.setEnabled(False)
        btn_layout.addWidget(self.confirm_btn)
        
        self.delete_btn = QPushButton("🗑️ 删除")
        self.delete_btn.clicked.connect(self._on_delete_entry)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return panel
    
    def _create_detail_panel(self) -> QWidget:
        """创建详情面板"""
        panel = QGroupBox("条目详情")
        layout = QVBoxLayout(panel)
        
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        layout.addWidget(self.detail_text)
        
        return panel
    
    def _create_io_tab(self) -> QWidget:
        """创建导入导出标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 导出部分
        export_group = QGroupBox("导出知识库")
        export_layout = QVBoxLayout(export_group)
        
        export_btn_layout = QHBoxLayout()
        
        self.export_json_btn = QPushButton("📄 导出为JSON")
        self.export_json_btn.clicked.connect(lambda: self._export_kb("json"))
        export_btn_layout.addWidget(self.export_json_btn)
        
        self.export_full_btn = QPushButton("📦 导出完整备份")
        self.export_full_btn.clicked.connect(lambda: self._export_kb("full"))
        export_btn_layout.addWidget(self.export_full_btn)
        
        export_btn_layout.addStretch()
        export_layout.addLayout(export_btn_layout)
        
        layout.addWidget(export_group)
        
        # 导入部分
        import_group = QGroupBox("导入知识库")
        import_layout = QVBoxLayout(import_group)
        
        import_btn_layout = QHBoxLayout()
        
        self.import_btn = QPushButton("📥 导入JSON文件")
        self.import_btn.clicked.connect(self._import_kb)
        import_btn_layout.addWidget(self.import_btn)
        
        import_btn_layout.addWidget(QLabel("合并策略:"))
        self.merge_strategy = QComboBox()
        self.merge_strategy.addItems(["update (更新已有)", "skip (跳过已有)", "duplicate (允许重复)"])
        import_btn_layout.addWidget(self.merge_strategy)
        
        import_btn_layout.addStretch()
        import_layout.addLayout(import_btn_layout)
        
        layout.addWidget(import_group)
        
        # 合并部分
        merge_group = QGroupBox("合并多个知识库")
        merge_layout = QVBoxLayout(merge_group)
        
        merge_desc = QLabel(
            "选择多个知识库JSON文件进行合并，用于汇总不同电脑的故障知识。"
        )
        merge_desc.setWordWrap(True)
        merge_desc.setStyleSheet("color: #6c757d;")
        merge_layout.addWidget(merge_desc)
        
        self.merge_btn = QPushButton("🔀 选择文件并合并")
        self.merge_btn.clicked.connect(self._merge_kbs)
        merge_layout.addWidget(self.merge_btn)
        
        layout.addWidget(merge_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_ml_tab(self) -> QWidget:
        """创建机器学习数据标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 说明
        desc = QLabel(
            "导出用于机器学习训练的数据集。包含特征向量和标签，"
            "可用于训练DDR故障检测模型。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6c757d; padding: 10px;")
        layout.addWidget(desc)
        
        # 导出选项
        options_group = QGroupBox("导出选项")
        options_layout = QFormLayout(options_group)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["all (全部格式)", "json", "csv", "numpy"])
        options_layout.addRow("导出格式:", self.format_combo)
        
        self.include_raw = QCheckBox()
        options_layout.addRow("包含原始文本:", self.include_raw)
        
        self.split_check = QCheckBox()
        self.split_check.setChecked(True)
        options_layout.addRow("划分训练/测试集:", self.split_check)
        
        self.test_ratio_edit = QLineEdit("0.2")
        self.test_ratio_edit.setMaximumWidth(100)
        options_layout.addRow("测试集比例:", self.test_ratio_edit)
        
        layout.addWidget(options_group)
        
        # 导出按钮
        btn_layout = QHBoxLayout()
        
        self.export_ml_btn = QPushButton("🤖 导出ML训练数据")
        self.export_ml_btn.clicked.connect(self._export_ml_data)
        self.export_ml_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        btn_layout.addWidget(self.export_ml_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return widget
    
    def _load_entries(self):
        """加载知识库条目"""
        category = None
        if self.category_filter.currentIndex() > 0:
            category = self.category_filter.currentText()
        
        confirmed_only = self.confirmed_filter.isChecked()
        
        self.entries = self.db_manager.get_knowledge_entries(
            category=category,
            confirmed_only=confirmed_only
        )
        
        self._display_entries()
        self._update_stats()
    
    def _display_entries(self):
        """显示条目列表"""
        self.entry_table.setRowCount(len(self.entries))
        
        for row, entry in enumerate(self.entries):
            self.entry_table.setItem(row, 0, QTableWidgetItem(str(entry['id'])))
            self.entry_table.setItem(row, 1, QTableWidgetItem(entry.get('title', '')))
            self.entry_table.setItem(row, 2, QTableWidgetItem(entry.get('category', '')))
            self.entry_table.setItem(row, 3, QTableWidgetItem(entry.get('signature_pattern', '')[:50]))
            self.entry_table.setItem(row, 4, QTableWidgetItem(str(entry.get('occurrence_count', 0))))
            
            # 已确认状态
            confirmed_item = QTableWidgetItem("✅" if entry.get('confirmed') else "❌")
            confirmed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entry_table.setItem(row, 5, confirmed_item)
            
            self.entry_table.setItem(row, 6, QTableWidgetItem(entry.get('ml_label', '')))
    
    def _update_stats(self):
        """更新统计信息"""
        stats = self.knowledge_base.get_statistics()
        
        self.total_card.set_value(str(stats.get('knowledge_entries', 0)))
        self.confirmed_card.set_value(str(stats.get('confirmed_entries', 0)))
        
        category_stats = stats.get('category_stats', {})
        ddr_count = category_stats.get('DDR', {}).get('total', 0)
        self.ddr_card.set_value(str(ddr_count))
        
        total_occurrences = sum(e.get('occurrence_count', 0) for e in self.entries)
        self.occurrence_card.set_value(str(total_occurrences))
    
    def _on_entry_selected(self, row: int, col: int):
        """条目选中事件"""
        if row < len(self.entries):
            entry = self.entries[row]
            self._show_entry_detail(entry)
            
            self.edit_btn.setEnabled(True)
            self.confirm_btn.setEnabled(not entry.get('confirmed'))
            self.delete_btn.setEnabled(True)
            
            self.entrySelected.emit(entry)
    
    def _on_entry_edit(self, row: int, col: int):
        """条目双击编辑"""
        self._on_edit_entry()
    
    def _show_entry_detail(self, entry: dict):
        """显示条目详情"""
        lines = [
            f"=== {entry.get('title', 'N/A')} ===",
            f"",
            f"ID: {entry.get('id')}",
            f"分类: {entry.get('category', 'N/A')} / {entry.get('subcategory', 'N/A')}",
            f"签名模式: {entry.get('signature_pattern', 'N/A')}",
            f"",
            f"--- 描述 ---",
            entry.get('description', 'N/A'),
            f"",
            f"--- 根本原因 ---",
            entry.get('root_cause', 'N/A'),
            f"",
            f"--- 解决方案 ---",
            entry.get('solution', 'N/A'),
            f"",
            f"--- 统计信息 ---",
            f"出现次数: {entry.get('occurrence_count', 0)}",
            f"已确认: {'是' if entry.get('confirmed') else '否'}",
            f"ML标签: {entry.get('ml_label', 'N/A')}",
            f"来源: {entry.get('source', 'N/A')}",
            f"来源机器: {entry.get('source_machine', 'N/A')}",
            f"创建时间: {entry.get('created_at', 'N/A')}",
            f"更新时间: {entry.get('updated_at', 'N/A')}",
        ]
        
        self.detail_text.setPlainText("\n".join(lines))
    
    def _on_new_entry(self):
        """新建条目"""
        dialog = KnowledgeEntryDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            entry = KnowledgeEntry.from_dict(data)
            self.db_manager.add_knowledge_entry(entry)
            self._load_entries()
            QMessageBox.information(self, "成功", "知识条目已创建")
    
    def _on_edit_entry(self):
        """编辑条目"""
        row = self.entry_table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        
        entry = self.entries[row]
        dialog = KnowledgeEntryDialog(entry, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            self.db_manager.update_knowledge_entry(entry['id'], **data)
            self._load_entries()
            QMessageBox.information(self, "成功", "知识条目已更新")
    
    def _on_confirm_entry(self):
        """确认条目"""
        row = self.entry_table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        
        entry = self.entries[row]
        self.knowledge_base.confirm_entry(entry['id'])
        self._load_entries()
    
    def _on_delete_entry(self):
        """删除条目"""
        row = self.entry_table.currentRow()
        if row < 0 or row >= len(self.entries):
            return
        
        entry = self.entries[row]
        
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除条目 '{entry.get('title')}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.db_manager.delete_by_id(KnowledgeEntry, entry['id'])
            self._load_entries()
    
    def _on_search(self, text: str):
        """搜索条目"""
        if text:
            self.entries = self.db_manager.search_knowledge_entries(text)
        else:
            self._load_entries()
            return
        self._display_entries()
    
    def _apply_filter(self):
        """应用过滤"""
        self._load_entries()
    
    def _export_kb(self, mode: str):
        """导出知识库"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出知识库",
            str(settings.export_dir / "knowledge_export.json"),
            "JSON文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            include_crash = (mode == "full")
            output = self.knowledge_base.export_knowledge_base(
                output_path=Path(file_path),
                include_crash_records=include_crash
            )
            QMessageBox.information(self, "导出成功", f"知识库已导出到: {output}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
    
    def _import_kb(self):
        """导入知识库"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "导入知识库",
            "",
            "JSON文件 (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            strategy = self.merge_strategy.currentText().split()[0]
            stats = self.knowledge_base.import_knowledge_base(
                Path(file_path),
                merge_strategy=strategy
            )
            
            self._load_entries()
            
            QMessageBox.information(
                self, "导入完成",
                f"导入统计:\n"
                f"总数: {stats['total']}\n"
                f"新增: {stats['added']}\n"
                f"更新: {stats['updated']}\n"
                f"跳过: {stats['skipped']}\n"
                f"错误: {stats['errors']}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))
    
    def _merge_kbs(self):
        """合并多个知识库"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要合并的知识库文件",
            "",
            "JSON文件 (*.json)"
        )
        
        if len(file_paths) < 2:
            QMessageBox.warning(self, "警告", "请至少选择2个文件进行合并")
            return
        
        try:
            output_path, stats = self.knowledge_base.merge_knowledge_bases(
                [Path(p) for p in file_paths]
            )
            
            QMessageBox.information(
                self, "合并完成",
                f"合并统计:\n"
                f"文件数: {stats['total_files']}\n"
                f"总条目: {stats['total_entries']}\n"
                f"唯一条目: {stats['unique_entries']}\n"
                f"合并条目: {stats['merged_entries']}\n\n"
                f"输出文件: {output_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "合并失败", str(e))
    
    def _export_ml_data(self):
        """导出机器学习数据"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择导出目录",
            str(settings.export_dir)
        )
        
        if not dir_path:
            return
        
        try:
            format_str = self.format_combo.currentText().split()[0]
            
            if self.split_check.isChecked():
                test_ratio = float(self.test_ratio_edit.text())
                files = self.ml_exporter.export_split_datasets(
                    output_dir=Path(dir_path),
                    test_ratio=test_ratio,
                    format=format_str
                )
            else:
                files = self.ml_exporter.export_training_data(
                    output_dir=Path(dir_path),
                    format=format_str,
                    include_raw_text=self.include_raw.isChecked()
                )
            
            file_list = "\n".join(f"- {k}: {v}" for k, v in files.items() if not isinstance(v, dict))
            QMessageBox.information(
                self, "导出成功",
                f"机器学习数据已导出:\n\n{file_list}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

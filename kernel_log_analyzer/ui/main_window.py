"""
主窗口 - 应用程序主界面
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenuBar, QMenu, QToolBar,
    QFileDialog, QMessageBox, QLabel, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence

from .log_view import LogView
from .analysis_view import AnalysisView
from .knowledge_view import KnowledgeView
from config.settings import settings
from database.db_manager import DatabaseManager


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        
        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"{settings.APP_NAME} v{settings.APP_VERSION}")
        self.setMinimumSize(settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        
        # 日志视图
        self.log_view = LogView()
        self.tab_widget.addTab(self.log_view, "📄 日志查看")
        
        # 分析视图
        self.analysis_view = AnalysisView()
        self.tab_widget.addTab(self.analysis_view, "🔍 崩溃分析")
        
        # 知识库视图
        self.knowledge_view = KnowledgeView()
        self.tab_widget.addTab(self.knowledge_view, "📚 知识库")
        
        layout.addWidget(self.tab_widget)
        
        # 设置样式
        self._set_style()
    
    def _set_style(self):
        """设置全局样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                background-color: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                border: 1px solid #ddd;
                border-bottom: none;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #dee2e6;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTableWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                gridline-color: #eee;
            }
            QTableWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #dee2e6;
                font-weight: bold;
            }
            QPushButton {
                padding: 5px 15px;
                border-radius: 4px;
            }
            QLineEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #007bff;
            }
            QComboBox {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
    
    def _create_menus(self):
        """创建菜单"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        
        open_action = QAction("打开日志文件(&O)", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("导出报告(&E)", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 分析菜单
        analyze_menu = menubar.addMenu("分析(&A)")
        
        analyze_action = QAction("开始分析(&A)", self)
        analyze_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        analyze_action.triggered.connect(self._start_analysis)
        analyze_menu.addAction(analyze_action)
        
        analyze_menu.addSeparator()
        
        filter_ddr_action = QAction("仅显示DDR相关(&D)", self)
        filter_ddr_action.setCheckable(True)
        filter_ddr_action.triggered.connect(self._toggle_ddr_filter)
        analyze_menu.addAction(filter_ddr_action)
        
        # 知识库菜单
        kb_menu = menubar.addMenu("知识库(&K)")
        
        import_kb_action = QAction("导入知识库(&I)", self)
        import_kb_action.triggered.connect(self._import_knowledge_base)
        kb_menu.addAction(import_kb_action)
        
        export_kb_action = QAction("导出知识库(&E)", self)
        export_kb_action.triggered.connect(self._export_knowledge_base)
        kb_menu.addAction(export_kb_action)
        
        kb_menu.addSeparator()
        
        export_ml_action = QAction("导出ML训练数据(&M)", self)
        export_ml_action.triggered.connect(self._export_ml_data)
        kb_menu.addAction(export_ml_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        stats_action = QAction("统计信息(&S)", self)
        stats_action.triggered.connect(self._show_statistics)
        help_menu.addAction(stats_action)
    
    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # 打开文件
        open_action = QAction("📂 打开", self)
        open_action.setToolTip("打开日志文件 (Ctrl+O)")
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)
        
        # 分析
        analyze_action = QAction("🔍 分析", self)
        analyze_action.setToolTip("开始分析 (Ctrl+Shift+A)")
        analyze_action.triggered.connect(self._start_analysis)
        toolbar.addAction(analyze_action)
        
        toolbar.addSeparator()
        
        # 导出
        export_action = QAction("📤 导出", self)
        export_action.setToolTip("导出报告 (Ctrl+E)")
        export_action.triggered.connect(self._export_report)
        toolbar.addAction(export_action)
        
        # 知识库
        kb_action = QAction("📚 知识库", self)
        kb_action.setToolTip("打开知识库")
        kb_action.triggered.connect(lambda: self.tab_widget.setCurrentIndex(2))
        toolbar.addAction(kb_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        
        # 数据库状态
        self.db_status_label = QLabel(f"📁 数据库: {settings.db_path.name}")
        self.status_bar.addPermanentWidget(self.db_status_label)
    
    def _connect_signals(self):
        """连接信号"""
        # 日志视图信号
        self.log_view.fileLoaded.connect(self._on_file_loaded)
        self.log_view.crashSelected.connect(self._on_crash_selected)
        
        # 分析视图信号
        self.analysis_view.analysisComplete.connect(self._on_analysis_complete)
    
    def _open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开日志文件",
            "",
            "日志文件 (*.log *.txt *.dmesg *.kmsg);;所有文件 (*.*)"
        )
        
        if file_path:
            self.log_view.load_file(Path(file_path))
            self.tab_widget.setCurrentIndex(0)
    
    def _on_file_loaded(self, file_path: str):
        """文件加载完成回调"""
        self.status_label.setText(f"已加载: {Path(file_path).name}")
        self.setWindowTitle(
            f"{settings.APP_NAME} - {Path(file_path).name}"
        )
    
    def _on_crash_selected(self, line_number: int):
        """崩溃选中回调"""
        self.status_label.setText(f"已选中崩溃 @ 行 {line_number}")
    
    def _start_analysis(self):
        """开始分析"""
        self.tab_widget.setCurrentIndex(1)
        self.analysis_view._on_analyze()
    
    def _on_analysis_complete(self, results):
        """分析完成回调"""
        count = len(results)
        ddr_count = sum(1 for r in results if r.is_ddr_related)
        self.status_label.setText(
            f"分析完成: {count} 个崩溃, {ddr_count} 个DDR相关"
        )
    
    def _toggle_ddr_filter(self, checked: bool):
        """切换DDR过滤"""
        self.analysis_view.filter_combo.setCurrentIndex(1 if checked else 0)
    
    def _export_report(self):
        """导出报告"""
        self.analysis_view._export_report()
    
    def _import_knowledge_base(self):
        """导入知识库"""
        self.tab_widget.setCurrentIndex(2)
        self.knowledge_view._import_kb()
    
    def _export_knowledge_base(self):
        """导出知识库"""
        self.tab_widget.setCurrentIndex(2)
        self.knowledge_view._export_kb("json")
    
    def _export_ml_data(self):
        """导出ML数据"""
        self.tab_widget.setCurrentIndex(2)
        self.knowledge_view._export_ml_data()
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            f"关于 {settings.APP_NAME}",
            f"""
            <h3>{settings.APP_NAME}</h3>
            <p>版本: {settings.APP_VERSION}</p>
            <p>
            Android内核日志分析工具，专注于：
            <ul>
                <li>内核崩溃问题分析</li>
                <li>DDR位翻转故障检测</li>
                <li>故障知识库管理</li>
                <li>机器学习训练数据导出</li>
            </ul>
            </p>
            <p>
            数据库位置: {settings.db_path}
            </p>
            """
        )
    
    def _show_statistics(self):
        """显示统计信息"""
        stats = self.db_manager.get_statistics()
        
        msg = f"""
        <h3>数据库统计</h3>
        <table>
            <tr><td>总崩溃记录:</td><td><b>{stats.get('total_crashes', 0)}</b></td></tr>
            <tr><td>DDR相关崩溃:</td><td><b>{stats.get('ddr_crashes', 0)}</b></td></tr>
            <tr><td>非DDR崩溃:</td><td><b>{stats.get('non_ddr_crashes', 0)}</b></td></tr>
            <tr><td>知识库条目:</td><td><b>{stats.get('knowledge_entries', 0)}</b></td></tr>
            <tr><td>已确认条目:</td><td><b>{stats.get('confirmed_entries', 0)}</b></td></tr>
        </table>
        
        <h4>崩溃类型分布</h4>
        """
        
        crash_types = stats.get('crash_type_stats', {})
        for crash_type, count in crash_types.items():
            msg += f"<br>• {crash_type}: {count}"
        
        QMessageBox.information(self, "统计信息", msg)
    
    def closeEvent(self, event):
        """关闭事件"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出程序吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


def run_app():
    """运行应用程序"""
    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setApplicationVersion(settings.APP_VERSION)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

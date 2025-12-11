#!/usr/bin/env python3
"""
Kernel Log Analyzer - Android内核日志分析工具

主入口文件
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import run_app


def main():
    """主函数"""
    print("=" * 50)
    print("  Kernel Log Analyzer - Android内核日志分析工具")
    print("=" * 50)
    print()
    print("正在启动GUI界面...")
    print()
    
    run_app()


if __name__ == "__main__":
    main()

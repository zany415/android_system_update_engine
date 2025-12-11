"""
配置模块 - 存储应用程序配置和DDR位翻转检测模式
"""
import os
from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path


@dataclass
class DDRPatterns:
    """DDR位翻转相关的检测模式"""
    
    # 常见的DDR位翻转错误模式
    BIT_FLIP_PATTERNS: List[str] = field(default_factory=lambda: [
        # ECC错误
        r"EDAC.*CE.*error",
        r"EDAC.*UE.*error", 
        r"ECC.*single.*bit.*error",
        r"ECC.*multi.*bit.*error",
        r"memory.*ECC.*error",
        
        # 内存控制器错误
        r"MC\d+.*error",
        r"memory.*controller.*error",
        r"DDR.*error",
        r"DRAM.*error",
        
        # 位翻转特征
        r"bit.*flip",
        r"single.*bit.*upset",
        r"SEU",  # Single Event Upset
        r"MBU",  # Multi-Bit Upset
        
        # 内存损坏
        r"memory.*corruption",
        r"data.*corruption.*memory",
        r"unexpected.*value.*at.*address",
        
        # ARM特定的内存错误
        r"Unhandled.*fault.*at.*0x[0-9a-fA-F]+",
        r"Unable.*to.*handle.*kernel.*paging.*request",
        r"BUG:.*Bad.*page.*state",
        r"Bad.*page.*map",
        
        # 指针异常（可能由位翻转导致）
        r"NULL.*pointer.*dereference",
        r"invalid.*opcode",
        r"kernel.*BUG.*at",
        
        # 内存分配器错误
        r"SLUB.*corruption",
        r"slab.*corruption",
        r"Object.*already.*free",
        r"Redzone.*overwritten",
    ])
    
    # 内核崩溃模式
    KERNEL_CRASH_PATTERNS: List[str] = field(default_factory=lambda: [
        r"Kernel.*panic",
        r"kernel.*panic",
        r"Unable.*to.*handle.*kernel",
        r"Oops",
        r"BUG:",
        r"Call.*[Tt]race",
        r"PC.*is.*at",
        r"LR.*is.*at",
        r"Internal.*error",
        r"Unhandled.*fault",
        r"die.*notifier",
        r"Fatal.*exception",
        r"watchdog.*bite",
        r"SError.*Interrupt",
    ])
    
    # 地址相关模式（用于提取故障地址）
    ADDRESS_PATTERNS: List[str] = field(default_factory=lambda: [
        r"at.*virtual.*address.*0x([0-9a-fA-F]+)",
        r"at.*address.*0x([0-9a-fA-F]+)",
        r"PC.*:.*0x([0-9a-fA-F]+)",
        r"pc.*:.*\[<([0-9a-fA-F]+)>\]",
        r"lr.*:.*\[<([0-9a-fA-F]+)>\]",
    ])
    
    # 函数调用栈模式
    STACK_TRACE_PATTERNS: List[str] = field(default_factory=lambda: [
        r"\[<[0-9a-fA-F]+>\]\s+(\S+)\+0x[0-9a-fA-F]+/0x[0-9a-fA-F]+",
        r"\[<[0-9a-fA-F]+>\]\s+(\S+)\s+\+",
        r"(\w+)\+0x[0-9a-fA-F]+/0x[0-9a-fA-F]+",
    ])


@dataclass  
class Settings:
    """应用程序设置"""
    
    # 应用信息
    APP_NAME: str = "Kernel Log Analyzer"
    APP_VERSION: str = "1.0.0"
    
    # 数据库设置
    DB_NAME: str = "kernel_knowledge.db"
    
    # 窗口设置
    WINDOW_WIDTH: int = 1400
    WINDOW_HEIGHT: int = 900
    
    # 日志解析设置
    MAX_LOG_SIZE_MB: int = 100
    LOG_ENCODINGS: List[str] = field(default_factory=lambda: [
        'utf-8', 'latin-1', 'gbk', 'gb2312'
    ])
    
    # 时间戳模式
    TIMESTAMP_PATTERNS: List[str] = field(default_factory=lambda: [
        r"^\[?\s*(\d+\.\d+)\]",  # [  123.456789]
        r"^<\d+>\[?\s*(\d+\.\d+)\]",  # <6>[  123.456789]
        r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",  # 2024-01-01 12:00:00
    ])
    
    # DDR检测模式
    ddr_patterns: DDRPatterns = field(default_factory=DDRPatterns)
    
    @property
    def db_path(self) -> Path:
        """获取数据库完整路径"""
        return self.data_dir / self.DB_NAME
    
    @property
    def data_dir(self) -> Path:
        """获取数据存储目录"""
        data_dir = Path.home() / ".kernel_log_analyzer"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    @property
    def export_dir(self) -> Path:
        """获取导出目录"""
        export_dir = self.data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir


# 全局设置实例
settings = Settings()
ddr_patterns = DDRPatterns()

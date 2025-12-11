"""
日志解析器 - 解析Android内核日志
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Iterator, Tuple
from pathlib import Path
from enum import Enum

from config.settings import settings


class LogLevel(Enum):
    """日志级别"""
    EMERGENCY = 0
    ALERT = 1
    CRITICAL = 2
    ERROR = 3
    WARNING = 4
    NOTICE = 5
    INFO = 6
    DEBUG = 7
    UNKNOWN = -1


@dataclass
class LogEntry:
    """日志条目"""
    line_number: int
    raw_text: str
    timestamp: Optional[float] = None
    level: LogLevel = LogLevel.UNKNOWN
    tag: Optional[str] = None
    message: str = ""
    
    # 分析标记
    is_crash_related: bool = False
    is_ddr_related: bool = False
    matched_patterns: List[str] = field(default_factory=list)


class LogParser:
    """内核日志解析器"""
    
    # 日志级别映射
    LEVEL_MAP = {
        '0': LogLevel.EMERGENCY,
        '1': LogLevel.ALERT,
        '2': LogLevel.CRITICAL,
        '3': LogLevel.ERROR,
        '4': LogLevel.WARNING,
        '5': LogLevel.NOTICE,
        '6': LogLevel.INFO,
        '7': LogLevel.DEBUG,
    }
    
    # 解析模式
    TIMESTAMP_PATTERN = re.compile(r'^\[?\s*(\d+\.\d+)\]?\s*')
    LEVEL_PATTERN = re.compile(r'^<(\d)>')
    DMESG_PATTERN = re.compile(
        r'^(?:<(\d)>)?'  # 可选的日志级别
        r'\[?\s*(\d+\.\d+)\]?\s*'  # 时间戳
        r'(?:(\w+):\s*)?'  # 可选的标签
        r'(.*)$'  # 消息内容
    )
    
    def __init__(self):
        self.entries: List[LogEntry] = []
        self.file_path: Optional[Path] = None
        self.parse_errors: List[Tuple[int, str]] = []
    
    def parse_file(self, file_path: Path, encoding: str = None) -> List[LogEntry]:
        """
        解析日志文件
        
        Args:
            file_path: 日志文件路径
            encoding: 文件编码，默认自动检测
            
        Returns:
            解析后的日志条目列表
        """
        self.file_path = Path(file_path)
        self.entries = []
        self.parse_errors = []
        
        # 尝试不同编码
        encodings = [encoding] if encoding else settings.LOG_ENCODINGS
        
        content = None
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            raise ValueError(f"无法解码文件: {file_path}")
        
        # 解析每一行
        for line_num, line in enumerate(content.splitlines(), 1):
            entry = self._parse_line(line_num, line)
            self.entries.append(entry)
        
        return self.entries
    
    def parse_text(self, text: str) -> List[LogEntry]:
        """
        解析日志文本
        
        Args:
            text: 日志文本内容
            
        Returns:
            解析后的日志条目列表
        """
        self.entries = []
        self.parse_errors = []
        
        for line_num, line in enumerate(text.splitlines(), 1):
            entry = self._parse_line(line_num, line)
            self.entries.append(entry)
        
        return self.entries
    
    def _parse_line(self, line_num: int, line: str) -> LogEntry:
        """解析单行日志"""
        entry = LogEntry(
            line_number=line_num,
            raw_text=line,
            message=line
        )
        
        if not line.strip():
            return entry
        
        try:
            # 尝试匹配完整的dmesg格式
            match = self.DMESG_PATTERN.match(line)
            if match:
                level_str, timestamp_str, tag, message = match.groups()
                
                if level_str:
                    entry.level = self.LEVEL_MAP.get(level_str, LogLevel.UNKNOWN)
                
                if timestamp_str:
                    entry.timestamp = float(timestamp_str)
                
                entry.tag = tag
                entry.message = message or line
            else:
                # 尝试单独匹配时间戳
                ts_match = self.TIMESTAMP_PATTERN.match(line)
                if ts_match:
                    entry.timestamp = float(ts_match.group(1))
                    entry.message = line[ts_match.end():]
                
                # 尝试匹配日志级别
                level_match = self.LEVEL_PATTERN.match(line)
                if level_match:
                    entry.level = self.LEVEL_MAP.get(
                        level_match.group(1), 
                        LogLevel.UNKNOWN
                    )
                    
        except Exception as e:
            self.parse_errors.append((line_num, str(e)))
        
        return entry
    
    def get_entries_in_range(
        self, 
        start_timestamp: float, 
        end_timestamp: float
    ) -> List[LogEntry]:
        """获取指定时间范围内的日志条目"""
        return [
            entry for entry in self.entries
            if entry.timestamp is not None 
            and start_timestamp <= entry.timestamp <= end_timestamp
        ]
    
    def get_entries_by_level(self, level: LogLevel) -> List[LogEntry]:
        """获取指定级别的日志条目"""
        return [entry for entry in self.entries if entry.level == level]
    
    def get_error_entries(self) -> List[LogEntry]:
        """获取所有错误级别的日志条目"""
        error_levels = {
            LogLevel.EMERGENCY, 
            LogLevel.ALERT, 
            LogLevel.CRITICAL, 
            LogLevel.ERROR
        }
        return [entry for entry in self.entries if entry.level in error_levels]
    
    def find_entries_by_pattern(self, pattern: str) -> List[LogEntry]:
        """根据正则表达式查找日志条目"""
        regex = re.compile(pattern, re.IGNORECASE)
        return [
            entry for entry in self.entries
            if regex.search(entry.raw_text)
        ]
    
    def get_context(
        self, 
        line_number: int, 
        before: int = 10, 
        after: int = 10
    ) -> List[LogEntry]:
        """获取指定行号周围的上下文日志"""
        start = max(0, line_number - before - 1)
        end = min(len(self.entries), line_number + after)
        return self.entries[start:end]
    
    def extract_crash_block(
        self, 
        start_line: int,
        max_lines: int = 100
    ) -> List[LogEntry]:
        """
        提取崩溃日志块
        从起始行开始，直到遇到新的正常日志或达到最大行数
        """
        crash_block = []
        crash_patterns = [
            r'Call [Tt]race',
            r'Stack:',
            r'\[<[0-9a-fA-F]+>\]',
            r'pc\s*:',
            r'lr\s*:',
            r'sp\s*:',
            r'x\d+\s*:',  # ARM64寄存器
            r'r\d+\s*:',  # ARM32寄存器
        ]
        combined_pattern = re.compile('|'.join(crash_patterns), re.IGNORECASE)
        
        in_trace = False
        for i in range(start_line - 1, min(start_line - 1 + max_lines, len(self.entries))):
            entry = self.entries[i]
            
            # 检查是否是崩溃相关行
            if combined_pattern.search(entry.raw_text):
                in_trace = True
            
            if in_trace or i == start_line - 1:
                crash_block.append(entry)
                
                # 检查是否到达崩溃块结尾
                if in_trace and len(crash_block) > 5:
                    # 如果连续3行没有崩溃模式，认为结束
                    recent = crash_block[-3:]
                    if not any(combined_pattern.search(e.raw_text) for e in recent):
                        break
        
        return crash_block
    
    def iter_entries(self) -> Iterator[LogEntry]:
        """迭代日志条目"""
        return iter(self.entries)
    
    def __len__(self) -> int:
        return len(self.entries)
    
    def __getitem__(self, index: int) -> LogEntry:
        return self.entries[index]

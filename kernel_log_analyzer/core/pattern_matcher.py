"""
模式匹配器 - 用于匹配日志中的各种错误模式
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum

from config.settings import ddr_patterns, DDRPatterns


class PatternCategory(Enum):
    """模式分类"""
    DDR_BIT_FLIP = "ddr_bit_flip"
    KERNEL_CRASH = "kernel_crash"
    MEMORY_ERROR = "memory_error"
    HARDWARE_ERROR = "hardware_error"
    SOFTWARE_BUG = "software_bug"
    UNKNOWN = "unknown"


@dataclass
class MatchResult:
    """匹配结果"""
    pattern: str
    category: PatternCategory
    matched_text: str
    line_number: int
    confidence: float = 1.0
    groups: Tuple = field(default_factory=tuple)
    metadata: Dict = field(default_factory=dict)


class PatternMatcher:
    """模式匹配器 - 匹配DDR位翻转和内核崩溃模式"""
    
    def __init__(self, custom_patterns: Optional[DDRPatterns] = None):
        """
        初始化模式匹配器
        
        Args:
            custom_patterns: 自定义模式配置
        """
        self.patterns = custom_patterns or ddr_patterns
        self._compiled_patterns: Dict[PatternCategory, List[Tuple[re.Pattern, str]]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译所有正则表达式"""
        # DDR位翻转模式
        self._compiled_patterns[PatternCategory.DDR_BIT_FLIP] = [
            (re.compile(p, re.IGNORECASE), p) 
            for p in self.patterns.BIT_FLIP_PATTERNS
        ]
        
        # 内核崩溃模式
        self._compiled_patterns[PatternCategory.KERNEL_CRASH] = [
            (re.compile(p, re.IGNORECASE), p)
            for p in self.patterns.KERNEL_CRASH_PATTERNS
        ]
        
        # 地址模式
        self._address_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.patterns.ADDRESS_PATTERNS
        ]
        
        # 调用栈模式
        self._stack_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in self.patterns.STACK_TRACE_PATTERNS
        ]
    
    def match_line(self, text: str, line_number: int = 0) -> List[MatchResult]:
        """
        匹配单行文本
        
        Args:
            text: 要匹配的文本
            line_number: 行号
            
        Returns:
            匹配结果列表
        """
        results = []
        
        for category, patterns in self._compiled_patterns.items():
            for regex, pattern_str in patterns:
                match = regex.search(text)
                if match:
                    result = MatchResult(
                        pattern=pattern_str,
                        category=category,
                        matched_text=match.group(0),
                        line_number=line_number,
                        groups=match.groups()
                    )
                    results.append(result)
        
        return results
    
    def match_text(self, text: str) -> List[MatchResult]:
        """
        匹配多行文本
        
        Args:
            text: 多行文本
            
        Returns:
            所有匹配结果列表
        """
        all_results = []
        for line_num, line in enumerate(text.splitlines(), 1):
            results = self.match_line(line, line_num)
            all_results.extend(results)
        return all_results
    
    def is_ddr_related(self, text: str) -> Tuple[bool, float, List[str]]:
        """
        判断文本是否与DDR相关
        
        Args:
            text: 要检查的文本
            
        Returns:
            (是否DDR相关, 置信度, 匹配的模式列表)
        """
        matched_patterns = []
        
        for regex, pattern_str in self._compiled_patterns[PatternCategory.DDR_BIT_FLIP]:
            if regex.search(text):
                matched_patterns.append(pattern_str)
        
        if not matched_patterns:
            return False, 0.0, []
        
        # 计算置信度
        # 基础置信度 + 每个额外匹配增加的置信度
        base_confidence = 0.5
        pattern_bonus = 0.1
        max_confidence = 0.95
        
        confidence = min(
            base_confidence + len(matched_patterns) * pattern_bonus,
            max_confidence
        )
        
        # 根据特定高置信度模式调整
        high_confidence_patterns = [
            r"EDAC.*UE.*error",
            r"ECC.*multi.*bit.*error",
            r"bit.*flip",
            r"SEU",
            r"MBU",
        ]
        for pattern in high_confidence_patterns:
            if any(pattern.lower() in mp.lower() for mp in matched_patterns):
                confidence = min(confidence + 0.15, max_confidence)
        
        return True, confidence, matched_patterns
    
    def is_kernel_crash(self, text: str) -> Tuple[bool, List[str]]:
        """
        判断文本是否包含内核崩溃
        
        Args:
            text: 要检查的文本
            
        Returns:
            (是否崩溃, 匹配的模式列表)
        """
        matched_patterns = []
        
        for regex, pattern_str in self._compiled_patterns[PatternCategory.KERNEL_CRASH]:
            if regex.search(text):
                matched_patterns.append(pattern_str)
        
        return len(matched_patterns) > 0, matched_patterns
    
    def extract_addresses(self, text: str) -> Dict[str, str]:
        """
        从文本中提取地址信息
        
        Args:
            text: 要解析的文本
            
        Returns:
            地址字典 {类型: 地址}
        """
        addresses = {}
        
        # PC地址
        pc_match = re.search(r'(?:PC|pc)\s*(?:is at|:)\s*(?:\[<)?([0-9a-fA-F]+)', text)
        if pc_match:
            addresses['pc'] = pc_match.group(1)
        
        # LR地址
        lr_match = re.search(r'(?:LR|lr)\s*(?:is at|:)\s*(?:\[<)?([0-9a-fA-F]+)', text)
        if lr_match:
            addresses['lr'] = lr_match.group(1)
        
        # 故障地址
        fault_patterns = [
            r'at\s+(?:virtual\s+)?address\s+(?:0x)?([0-9a-fA-F]+)',
            r'fault\s+at\s+(?:0x)?([0-9a-fA-F]+)',
        ]
        for pattern in fault_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                addresses['fault'] = match.group(1)
                break
        
        return addresses
    
    def extract_call_trace(self, text: str) -> List[str]:
        """
        从文本中提取调用栈
        
        Args:
            text: 要解析的文本
            
        Returns:
            函数名列表
        """
        functions = []
        
        for pattern in self._stack_patterns:
            matches = pattern.findall(text)
            for match in matches:
                func_name = match if isinstance(match, str) else match[0]
                # 清理函数名
                func_name = func_name.strip()
                if func_name and func_name not in functions:
                    functions.append(func_name)
        
        return functions
    
    def extract_crash_type(self, text: str) -> str:
        """
        提取崩溃类型
        
        Args:
            text: 崩溃日志文本
            
        Returns:
            崩溃类型字符串
        """
        crash_types = {
            r'Kernel\s+panic': 'Kernel Panic',
            r'Unable\s+to\s+handle\s+kernel\s+paging\s+request': 'Page Fault',
            r'Unable\s+to\s+handle\s+kernel\s+NULL\s+pointer': 'NULL Pointer Dereference',
            r'Oops': 'Kernel Oops',
            r'BUG:\s+Bad\s+page': 'Bad Page State',
            r'SLUB\s+corruption': 'SLUB Corruption',
            r'slab\s+corruption': 'Slab Corruption',
            r'watchdog\s+bite': 'Watchdog Timeout',
            r'SError\s+Interrupt': 'SError Exception',
            r'Internal\s+error': 'Internal Error',
            r'Unhandled\s+fault': 'Unhandled Fault',
        }
        
        for pattern, crash_type in crash_types.items():
            if re.search(pattern, text, re.IGNORECASE):
                return crash_type
        
        return 'Unknown Crash'
    
    def generate_signature(self, crash_type: str, top_function: str, fault_address: str = None) -> str:
        """
        生成崩溃签名（用于去重和匹配）
        
        Args:
            crash_type: 崩溃类型
            top_function: 顶层函数名
            fault_address: 故障地址（可选）
            
        Returns:
            崩溃签名字符串
        """
        parts = [crash_type, top_function or "unknown"]
        
        # 对地址进行脱敏处理（保留高位，去除低位）
        if fault_address:
            try:
                addr_int = int(fault_address, 16)
                # 只保留地址的高24位作为签名的一部分
                masked_addr = format(addr_int & 0xFFFFFF000000, 'x')
                parts.append(f"addr_{masked_addr}")
            except ValueError:
                pass
        
        return "::".join(parts)
    
    def add_custom_pattern(
        self, 
        pattern: str, 
        category: PatternCategory
    ) -> bool:
        """
        添加自定义模式
        
        Args:
            pattern: 正则表达式模式
            category: 模式分类
            
        Returns:
            是否添加成功
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            if category not in self._compiled_patterns:
                self._compiled_patterns[category] = []
            self._compiled_patterns[category].append((compiled, pattern))
            return True
        except re.error:
            return False
    
    def get_pattern_stats(self) -> Dict[str, int]:
        """获取模式统计信息"""
        return {
            category.value: len(patterns)
            for category, patterns in self._compiled_patterns.items()
        }

"""
DDR位翻转检测器 - 专门用于检测和分析DDR相关故障
"""
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum

from .log_parser import LogEntry
from .pattern_matcher import PatternMatcher, PatternCategory


class DDRFaultType(Enum):
    """DDR故障类型"""
    ECC_SINGLE_BIT = "ECC Single Bit Error"
    ECC_MULTI_BIT = "ECC Multi Bit Error"
    BIT_FLIP = "Bit Flip"
    MEMORY_CORRUPTION = "Memory Corruption"
    PAGE_FAULT = "Page Fault"
    SLAB_CORRUPTION = "Slab Corruption"
    UNKNOWN = "Unknown DDR Error"


@dataclass
class DDRDetectionResult:
    """DDR检测结果"""
    is_ddr_related: bool
    fault_type: DDRFaultType
    confidence: float
    matched_patterns: List[str]
    
    # 详细信息
    memory_address: Optional[str] = None
    memory_region: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    bit_positions: List[int] = field(default_factory=list)
    
    # ECC信息
    ecc_syndrome: Optional[str] = None
    is_correctable: Optional[bool] = None
    
    # 分析信息
    analysis_notes: List[str] = field(default_factory=list)
    related_entries: List[LogEntry] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'is_ddr_related': self.is_ddr_related,
            'fault_type': self.fault_type.value,
            'confidence': self.confidence,
            'matched_patterns': self.matched_patterns,
            'memory_address': self.memory_address,
            'memory_region': self.memory_region,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'bit_positions': self.bit_positions,
            'ecc_syndrome': self.ecc_syndrome,
            'is_correctable': self.is_correctable,
            'analysis_notes': self.analysis_notes,
        }


class DDRDetector:
    """DDR位翻转检测器"""
    
    # 内存区域模式
    MEMORY_REGION_PATTERNS = {
        'kernel_text': (r'0x[fF]{8,}[89a-fA-F]', '内核代码段'),
        'kernel_data': (r'0x[fF]{8,}[0-7]', '内核数据段'),
        'user_space': (r'0x[0-7][0-9a-fA-F]+', '用户空间'),
        'io_region': (r'0x[fF]{4}[0-9a-fA-F]+0{4,}', 'I/O映射区域'),
        'vmalloc': (r'0x[fF]{4}[fF]{4}[cC]', 'vmalloc区域'),
    }
    
    # 已知的高可信度DDR故障特征
    HIGH_CONFIDENCE_INDICATORS = [
        r'EDAC.*(?:CE|UE).*error',
        r'Hardware\s+Error',
        r'Machine\s+check\s+exception',
        r'memory.*error.*detected',
        r'ECC.*(?:single|multi|double).*bit',
        r'DRAM.*error',
        r'MC\d+.*Bank\d+',
    ]
    
    def __init__(self, pattern_matcher: Optional[PatternMatcher] = None):
        """
        初始化DDR检测器
        
        Args:
            pattern_matcher: 模式匹配器实例
        """
        self.matcher = pattern_matcher or PatternMatcher()
        self._high_confidence_patterns = [
            re.compile(p, re.IGNORECASE) 
            for p in self.HIGH_CONFIDENCE_INDICATORS
        ]
    
    def detect(self, log_entries: List[LogEntry]) -> DDRDetectionResult:
        """
        检测日志条目中是否存在DDR相关故障
        
        Args:
            log_entries: 日志条目列表
            
        Returns:
            DDR检测结果
        """
        # 合并所有日志文本
        full_text = "\n".join(entry.raw_text for entry in log_entries)
        
        # 基础DDR检测
        is_ddr, confidence, matched_patterns = self.matcher.is_ddr_related(full_text)
        
        result = DDRDetectionResult(
            is_ddr_related=is_ddr,
            fault_type=DDRFaultType.UNKNOWN,
            confidence=confidence,
            matched_patterns=matched_patterns,
            related_entries=log_entries
        )
        
        if not is_ddr:
            # 进行二次分析，检查是否可能是隐蔽的DDR故障
            result = self._secondary_analysis(log_entries, result)
        
        if result.is_ddr_related:
            # 确定故障类型
            result.fault_type = self._determine_fault_type(full_text, matched_patterns)
            
            # 提取详细信息
            self._extract_details(full_text, result)
            
            # 分析可能的位翻转位置
            self._analyze_bit_flip(result)
            
            # 添加分析说明
            self._add_analysis_notes(result)
        
        return result
    
    def detect_from_text(self, text: str) -> DDRDetectionResult:
        """
        从文本检测DDR故障
        
        Args:
            text: 日志文本
            
        Returns:
            DDR检测结果
        """
        # 创建临时日志条目
        entries = [
            LogEntry(line_number=i+1, raw_text=line, message=line)
            for i, line in enumerate(text.splitlines())
        ]
        return self.detect(entries)
    
    def _secondary_analysis(
        self, 
        entries: List[LogEntry], 
        result: DDRDetectionResult
    ) -> DDRDetectionResult:
        """
        二次分析 - 检测可能被遗漏的DDR故障
        """
        full_text = "\n".join(entry.raw_text for entry in entries)
        
        # 检查高置信度指标
        for pattern in self._high_confidence_patterns:
            if pattern.search(full_text):
                result.is_ddr_related = True
                result.confidence = 0.85
                result.matched_patterns.append(pattern.pattern)
        
        # 检查特殊的内存损坏模式
        corruption_indicators = self._check_corruption_patterns(full_text)
        if corruption_indicators:
            if not result.is_ddr_related:
                result.is_ddr_related = True
                result.confidence = 0.6
            result.matched_patterns.extend(corruption_indicators)
            result.analysis_notes.append("检测到内存损坏模式")
        
        # 检查是否有异常的地址访问
        if self._check_abnormal_address(full_text):
            if not result.is_ddr_related:
                result.confidence = max(result.confidence, 0.4)
            result.analysis_notes.append("检测到异常地址访问模式")
        
        return result
    
    def _check_corruption_patterns(self, text: str) -> List[str]:
        """检查内存损坏模式"""
        indicators = []
        
        patterns = [
            (r'Object\s+already\s+free', 'Double free detected'),
            (r'Redzone\s+overwritten', 'Redzone corruption'),
            (r'Poison\s+overwritten', 'Poison value corruption'),
            (r'invalid\s+opcode', 'Invalid opcode (possible code corruption)'),
            (r'undefined\s+instruction', 'Undefined instruction'),
            (r'Bad.*page.*state', 'Bad page state'),
        ]
        
        for pattern, desc in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                indicators.append(desc)
        
        return indicators
    
    def _check_abnormal_address(self, text: str) -> bool:
        """检查异常地址"""
        addresses = self.matcher.extract_addresses(text)
        
        for addr_type, addr in addresses.items():
            try:
                addr_int = int(addr, 16)
                
                # 检查是否是典型的位翻转模式
                # 例如：只有单个或少数几个位不同
                if self._is_potential_bit_flip_address(addr_int):
                    return True
                
            except ValueError:
                continue
        
        return False
    
    def _is_potential_bit_flip_address(self, address: int) -> bool:
        """
        判断地址是否可能是由位翻转导致的
        """
        # 检查是否是单比特或少数比特翻转的特征
        # 例如：0x0000000000000001, 0x8000000000000000 等
        
        # 计算设置的位数
        bit_count = bin(address).count('1')
        
        # 如果只有1-2位被设置，可能是NULL指针位翻转
        if bit_count <= 2 and address < 0x10000:
            return True
        
        # 检查是否是接近有效内核地址但有少量位翻转
        # 典型的ARM64内核地址以0xFFFF开头
        if address > 0xFFFF000000000000:
            # 检查低位是否异常
            low_bits = address & 0xFFF
            if low_bits in [0, 0xFFF]:  # 页对齐异常
                return True
        
        return False
    
    def _determine_fault_type(
        self, 
        text: str, 
        matched_patterns: List[str]
    ) -> DDRFaultType:
        """确定DDR故障类型"""
        text_lower = text.lower()
        patterns_str = " ".join(matched_patterns).lower()
        
        # ECC错误
        if 'single' in patterns_str and ('bit' in patterns_str or 'ecc' in patterns_str):
            return DDRFaultType.ECC_SINGLE_BIT
        if ('multi' in patterns_str or 'double' in patterns_str or 'ue' in patterns_str):
            if 'bit' in patterns_str or 'ecc' in patterns_str:
                return DDRFaultType.ECC_MULTI_BIT
        
        # 位翻转
        if 'bit flip' in text_lower or 'seu' in text_lower or 'mbu' in text_lower:
            return DDRFaultType.BIT_FLIP
        
        # SLAB/SLUB损坏
        if 'slab' in text_lower or 'slub' in text_lower:
            return DDRFaultType.SLAB_CORRUPTION
        
        # 内存损坏
        if 'corruption' in text_lower or 'corrupted' in text_lower:
            return DDRFaultType.MEMORY_CORRUPTION
        
        # 页面错误
        if 'page fault' in text_lower or 'paging request' in text_lower:
            return DDRFaultType.PAGE_FAULT
        
        return DDRFaultType.UNKNOWN
    
    def _extract_details(self, text: str, result: DDRDetectionResult):
        """提取详细信息"""
        # 提取地址
        addresses = self.matcher.extract_addresses(text)
        if 'fault' in addresses:
            result.memory_address = addresses['fault']
        
        # 确定内存区域
        if result.memory_address:
            result.memory_region = self._identify_memory_region(result.memory_address)
        
        # 提取ECC信息
        ecc_match = re.search(
            r'syndrome[:\s]+(?:0x)?([0-9a-fA-F]+)', 
            text, 
            re.IGNORECASE
        )
        if ecc_match:
            result.ecc_syndrome = ecc_match.group(1)
        
        # 检查是否可纠正
        if 'correctable' in text.lower() or 'ce' in text.lower():
            result.is_correctable = True
        elif 'uncorrectable' in text.lower() or 'ue' in text.lower():
            result.is_correctable = False
        
        # 提取期望值和实际值
        value_match = re.search(
            r'expected[:\s]+(?:0x)?([0-9a-fA-F]+).*actual[:\s]+(?:0x)?([0-9a-fA-F]+)',
            text,
            re.IGNORECASE
        )
        if value_match:
            result.expected_value = value_match.group(1)
            result.actual_value = value_match.group(2)
    
    def _identify_memory_region(self, address: str) -> str:
        """识别内存区域"""
        full_addr = f"0x{address}"
        
        for region_name, (pattern, description) in self.MEMORY_REGION_PATTERNS.items():
            if re.match(pattern, full_addr, re.IGNORECASE):
                return description
        
        return "未知区域"
    
    def _analyze_bit_flip(self, result: DDRDetectionResult):
        """分析位翻转位置"""
        if result.expected_value and result.actual_value:
            try:
                expected = int(result.expected_value, 16)
                actual = int(result.actual_value, 16)
                
                # XOR找出不同的位
                diff = expected ^ actual
                
                # 找出翻转的位位置
                bit_positions = []
                for i in range(64):  # 假设最多64位
                    if diff & (1 << i):
                        bit_positions.append(i)
                
                result.bit_positions = bit_positions
                
                if len(bit_positions) == 1:
                    result.analysis_notes.append(
                        f"检测到单比特翻转，位置: bit {bit_positions[0]}"
                    )
                elif len(bit_positions) > 1:
                    result.analysis_notes.append(
                        f"检测到多比特翻转，位置: bits {bit_positions}"
                    )
                    
            except ValueError:
                pass
    
    def _add_analysis_notes(self, result: DDRDetectionResult):
        """添加分析说明"""
        # 根据故障类型添加说明
        if result.fault_type == DDRFaultType.ECC_SINGLE_BIT:
            result.analysis_notes.append(
                "ECC单比特错误通常可以被硬件自动纠正，但频繁出现可能表示内存老化或环境问题"
            )
        elif result.fault_type == DDRFaultType.ECC_MULTI_BIT:
            result.analysis_notes.append(
                "ECC多比特错误是严重问题，无法被硬件纠正，通常会导致系统崩溃"
            )
        elif result.fault_type == DDRFaultType.BIT_FLIP:
            result.analysis_notes.append(
                "位翻转可能由宇宙射线、电压波动或内存质量问题导致"
            )
        elif result.fault_type == DDRFaultType.SLAB_CORRUPTION:
            result.analysis_notes.append(
                "SLAB/SLUB损坏可能是软件bug导致，也可能是底层内存故障的表现"
            )
        
        # 根据置信度添加说明
        if result.confidence < 0.5:
            result.analysis_notes.append(
                "置信度较低，建议结合其他日志信息进一步分析"
            )
        elif result.confidence >= 0.8:
            result.analysis_notes.append(
                "高置信度DDR故障，建议检查硬件状态"
            )
    
    def get_detection_summary(self, result: DDRDetectionResult) -> str:
        """获取检测结果摘要"""
        if not result.is_ddr_related:
            return "未检测到DDR相关故障"
        
        summary_parts = [
            f"故障类型: {result.fault_type.value}",
            f"置信度: {result.confidence:.1%}",
        ]
        
        if result.memory_address:
            summary_parts.append(f"故障地址: 0x{result.memory_address}")
        
        if result.memory_region:
            summary_parts.append(f"内存区域: {result.memory_region}")
        
        if result.is_correctable is not None:
            summary_parts.append(f"可纠正: {'是' if result.is_correctable else '否'}")
        
        if result.bit_positions:
            summary_parts.append(f"翻转位: {result.bit_positions}")
        
        return "\n".join(summary_parts)

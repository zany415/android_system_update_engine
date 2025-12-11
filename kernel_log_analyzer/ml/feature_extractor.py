"""
特征提取器 - 从崩溃日志中提取用于机器学习的特征
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

from core.crash_analyzer import CrashAnalysisResult
from core.log_parser import LogEntry


@dataclass
class FeatureVector:
    """特征向量"""
    # 基础特征
    crash_type_id: int = 0
    fault_type_id: int = 0
    
    # 数值特征
    call_trace_depth: int = 0
    pattern_match_count: int = 0
    ddr_confidence: float = 0.0
    
    # 布尔特征
    has_ecc_error: bool = False
    has_bit_flip: bool = False
    has_memory_corruption: bool = False
    has_null_pointer: bool = False
    has_page_fault: bool = False
    is_correctable: Optional[bool] = None
    
    # 地址特征
    has_fault_address: bool = False
    fault_address_region: int = 0  # 0=unknown, 1=kernel, 2=user, 3=io
    
    # 模式频率特征
    ecc_pattern_count: int = 0
    memory_pattern_count: int = 0
    hardware_pattern_count: int = 0
    
    # 文本特征（用于TF-IDF等）
    top_functions: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # 标签
    label: Optional[str] = None
    
    def to_numeric_vector(self) -> List[float]:
        """转换为数值向量（用于传统ML算法）"""
        return [
            float(self.crash_type_id),
            float(self.fault_type_id),
            float(self.call_trace_depth),
            float(self.pattern_match_count),
            self.ddr_confidence,
            float(self.has_ecc_error),
            float(self.has_bit_flip),
            float(self.has_memory_corruption),
            float(self.has_null_pointer),
            float(self.has_page_fault),
            float(self.is_correctable) if self.is_correctable is not None else 0.5,
            float(self.has_fault_address),
            float(self.fault_address_region),
            float(self.ecc_pattern_count),
            float(self.memory_pattern_count),
            float(self.hardware_pattern_count),
        ]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'crash_type_id': self.crash_type_id,
            'fault_type_id': self.fault_type_id,
            'call_trace_depth': self.call_trace_depth,
            'pattern_match_count': self.pattern_match_count,
            'ddr_confidence': self.ddr_confidence,
            'has_ecc_error': self.has_ecc_error,
            'has_bit_flip': self.has_bit_flip,
            'has_memory_corruption': self.has_memory_corruption,
            'has_null_pointer': self.has_null_pointer,
            'has_page_fault': self.has_page_fault,
            'is_correctable': self.is_correctable,
            'has_fault_address': self.has_fault_address,
            'fault_address_region': self.fault_address_region,
            'ecc_pattern_count': self.ecc_pattern_count,
            'memory_pattern_count': self.memory_pattern_count,
            'hardware_pattern_count': self.hardware_pattern_count,
            'top_functions': self.top_functions,
            'keywords': self.keywords,
            'label': self.label,
            'numeric_vector': self.to_numeric_vector(),
        }


class FeatureExtractor:
    """特征提取器"""
    
    # 崩溃类型映射
    CRASH_TYPE_MAP = {
        'Unknown Crash': 0,
        'Kernel Panic': 1,
        'Kernel Oops': 2,
        'Page Fault': 3,
        'NULL Pointer Dereference': 4,
        'Bad Page State': 5,
        'SLUB Corruption': 6,
        'Slab Corruption': 7,
        'Watchdog Timeout': 8,
        'SError Exception': 9,
        'Internal Error': 10,
        'Unhandled Fault': 11,
    }
    
    # DDR故障类型映射
    FAULT_TYPE_MAP = {
        'Unknown DDR Error': 0,
        'ECC Single Bit Error': 1,
        'ECC Multi Bit Error': 2,
        'Bit Flip': 3,
        'Memory Corruption': 4,
        'Page Fault': 5,
        'Slab Corruption': 6,
    }
    
    # 关键词分类
    ECC_KEYWORDS = ['ecc', 'edac', 'ce', 'ue', 'single bit', 'multi bit', 'double bit']
    MEMORY_KEYWORDS = ['memory', 'dram', 'ddr', 'ram', 'slub', 'slab', 'page', 'alloc']
    HARDWARE_KEYWORDS = ['hardware', 'mc', 'controller', 'bus', 'parity', 'syndrome']
    
    def __init__(self):
        """初始化特征提取器"""
        self._keyword_patterns = {
            'ecc': re.compile('|'.join(self.ECC_KEYWORDS), re.IGNORECASE),
            'memory': re.compile('|'.join(self.MEMORY_KEYWORDS), re.IGNORECASE),
            'hardware': re.compile('|'.join(self.HARDWARE_KEYWORDS), re.IGNORECASE),
        }
    
    def extract(self, result: CrashAnalysisResult) -> FeatureVector:
        """
        从崩溃分析结果中提取特征
        
        Args:
            result: 崩溃分析结果
            
        Returns:
            特征向量
        """
        features = FeatureVector()
        
        # 基础特征
        features.crash_type_id = self.CRASH_TYPE_MAP.get(result.crash_type, 0)
        features.call_trace_depth = len(result.call_trace)
        features.pattern_match_count = len(result.matched_patterns)
        features.ddr_confidence = result.ddr_confidence
        
        # DDR故障类型
        if result.ddr_result:
            features.fault_type_id = self.FAULT_TYPE_MAP.get(
                result.ddr_result.fault_type.value, 0
            )
            features.is_correctable = result.ddr_result.is_correctable
        
        # 从匹配模式提取布尔特征
        patterns_text = " ".join(result.matched_patterns).lower()
        features.has_ecc_error = bool(self._keyword_patterns['ecc'].search(patterns_text))
        features.has_bit_flip = 'bit' in patterns_text and 'flip' in patterns_text
        features.has_memory_corruption = 'corrupt' in patterns_text
        features.has_null_pointer = 'null' in patterns_text.lower()
        features.has_page_fault = 'page' in patterns_text and 'fault' in patterns_text
        
        # 地址特征
        features.has_fault_address = result.fault_address is not None
        if result.fault_address:
            features.fault_address_region = self._classify_address(result.fault_address)
        
        # 模式频率特征
        features.ecc_pattern_count = len(
            self._keyword_patterns['ecc'].findall(patterns_text)
        )
        features.memory_pattern_count = len(
            self._keyword_patterns['memory'].findall(patterns_text)
        )
        features.hardware_pattern_count = len(
            self._keyword_patterns['hardware'].findall(patterns_text)
        )
        
        # 文本特征
        features.top_functions = result.call_trace[:5] if result.call_trace else []
        features.keywords = self._extract_keywords(result)
        
        # 标签
        features.label = 'ddr_related' if result.is_ddr_related else 'non_ddr'
        
        return features
    
    def extract_from_text(self, text: str, label: Optional[str] = None) -> FeatureVector:
        """
        直接从文本提取特征
        
        Args:
            text: 日志文本
            label: 可选的标签
            
        Returns:
            特征向量
        """
        features = FeatureVector()
        text_lower = text.lower()
        
        # 检测崩溃类型
        for crash_type, type_id in self.CRASH_TYPE_MAP.items():
            if crash_type.lower().replace(' ', '') in text_lower.replace(' ', ''):
                features.crash_type_id = type_id
                break
        
        # 布尔特征
        features.has_ecc_error = bool(self._keyword_patterns['ecc'].search(text_lower))
        features.has_bit_flip = 'bit' in text_lower and 'flip' in text_lower
        features.has_memory_corruption = 'corrupt' in text_lower
        features.has_null_pointer = 'null' in text_lower and 'pointer' in text_lower
        features.has_page_fault = 'page' in text_lower and 'fault' in text_lower
        
        # 模式频率
        features.ecc_pattern_count = len(self._keyword_patterns['ecc'].findall(text_lower))
        features.memory_pattern_count = len(self._keyword_patterns['memory'].findall(text_lower))
        features.hardware_pattern_count = len(self._keyword_patterns['hardware'].findall(text_lower))
        
        # 计算DDR置信度
        confidence_factors = [
            features.has_ecc_error * 0.3,
            features.has_bit_flip * 0.25,
            features.has_memory_corruption * 0.15,
            min(features.ecc_pattern_count * 0.05, 0.15),
            min(features.memory_pattern_count * 0.03, 0.1),
            min(features.hardware_pattern_count * 0.03, 0.1),
        ]
        features.ddr_confidence = min(sum(confidence_factors), 0.95)
        
        # 标签
        if label:
            features.label = label
        elif features.ddr_confidence > 0.5:
            features.label = 'ddr_related'
        else:
            features.label = 'non_ddr'
        
        return features
    
    def _classify_address(self, address: str) -> int:
        """
        分类内存地址区域
        
        Returns:
            0=unknown, 1=kernel, 2=user, 3=io
        """
        try:
            addr_int = int(address, 16)
            
            # ARM64地址空间
            if addr_int >= 0xFFFF000000000000:
                return 1  # kernel
            elif addr_int < 0x0001000000000000:
                return 2  # user
            else:
                return 3  # io/other
        except ValueError:
            return 0
    
    def _extract_keywords(self, result: CrashAnalysisResult) -> List[str]:
        """提取关键词"""
        keywords = set()
        
        # 从崩溃类型
        keywords.add(result.crash_type.lower().replace(' ', '_'))
        
        # 从顶层函数
        if result.top_function:
            keywords.add(result.top_function)
        
        # 从匹配模式
        for pattern in result.matched_patterns[:10]:
            # 提取模式中的关键词
            words = re.findall(r'\w+', pattern)
            keywords.update(w.lower() for w in words if len(w) > 2)
        
        return list(keywords)[:20]  # 限制数量
    
    def batch_extract(
        self, 
        results: List[CrashAnalysisResult]
    ) -> List[FeatureVector]:
        """批量提取特征"""
        return [self.extract(r) for r in results]
    
    def get_feature_names(self) -> List[str]:
        """获取特征名称列表"""
        return [
            'crash_type_id',
            'fault_type_id',
            'call_trace_depth',
            'pattern_match_count',
            'ddr_confidence',
            'has_ecc_error',
            'has_bit_flip',
            'has_memory_corruption',
            'has_null_pointer',
            'has_page_fault',
            'is_correctable',
            'has_fault_address',
            'fault_address_region',
            'ecc_pattern_count',
            'memory_pattern_count',
            'hardware_pattern_count',
        ]

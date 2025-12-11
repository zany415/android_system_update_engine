"""
崩溃分析器 - 综合分析内核崩溃日志
"""
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .log_parser import LogParser, LogEntry
from .pattern_matcher import PatternMatcher
from .ddr_detector import DDRDetector, DDRDetectionResult, DDRFaultType
from database.models import CrashRecord, DDRFaultRecord


@dataclass
class CrashAnalysisResult:
    """崩溃分析结果"""
    # 基本信息
    crash_type: str
    crash_signature: str
    
    # 地址信息
    fault_address: Optional[str] = None
    pc_address: Optional[str] = None
    lr_address: Optional[str] = None
    
    # 调用栈
    call_trace: List[str] = field(default_factory=list)
    top_function: Optional[str] = None
    
    # 时间信息
    timestamp: Optional[float] = None
    
    # DDR相关
    ddr_result: Optional[DDRDetectionResult] = None
    is_ddr_related: bool = False
    ddr_confidence: float = 0.0
    
    # 原始日志
    crash_entries: List[LogEntry] = field(default_factory=list)
    raw_log_snippet: str = ""
    
    # 分析元数据
    matched_patterns: List[str] = field(default_factory=list)
    analysis_notes: List[str] = field(default_factory=list)
    
    def to_crash_record(self, log_file: str) -> CrashRecord:
        """转换为CrashRecord数据库模型"""
        return CrashRecord(
            log_file=log_file,
            crash_type=self.crash_type,
            crash_signature=self.crash_signature,
            timestamp=self.timestamp,
            fault_address=self.fault_address,
            pc_address=self.pc_address,
            lr_address=self.lr_address,
            call_trace="\n".join(self.call_trace),
            top_function=self.top_function,
            raw_log_snippet=self.raw_log_snippet[:2000],  # 限制长度
            is_ddr_related=self.is_ddr_related,
            ddr_confidence=self.ddr_confidence,
            analysis_result={
                'matched_patterns': self.matched_patterns,
                'analysis_notes': self.analysis_notes,
                'ddr_result': self.ddr_result.to_dict() if self.ddr_result else None
            }
        )
    
    def to_ddr_fault_record(self) -> Optional[DDRFaultRecord]:
        """转换为DDRFaultRecord数据库模型"""
        if not self.ddr_result or not self.is_ddr_related:
            return None
        
        return DDRFaultRecord(
            fault_type=self.ddr_result.fault_type.value,
            error_pattern=", ".join(self.ddr_result.matched_patterns[:5]),
            memory_address=self.ddr_result.memory_address,
            memory_region=self.ddr_result.memory_region,
            expected_value=self.ddr_result.expected_value,
            actual_value=self.ddr_result.actual_value,
            bit_positions=",".join(map(str, self.ddr_result.bit_positions)),
            ecc_syndrome=self.ddr_result.ecc_syndrome,
            is_correctable=self.ddr_result.is_correctable,
            confidence_score=self.ddr_confidence,
            matched_patterns=self.ddr_result.matched_patterns,
            feature_vector=self._extract_features()
        )
    
    def _extract_features(self) -> dict:
        """提取用于机器学习的特征"""
        features = {
            'crash_type': self.crash_type,
            'has_ecc_error': any('ecc' in p.lower() for p in self.matched_patterns),
            'has_bit_flip': any('bit' in p.lower() and 'flip' in p.lower() 
                               for p in self.matched_patterns),
            'has_memory_corruption': any('corrupt' in p.lower() 
                                        for p in self.matched_patterns),
            'call_trace_depth': len(self.call_trace),
            'pattern_count': len(self.matched_patterns),
            'confidence': self.ddr_confidence,
        }
        
        if self.ddr_result:
            features.update({
                'fault_type': self.ddr_result.fault_type.value,
                'bit_flip_count': len(self.ddr_result.bit_positions),
                'is_correctable': self.ddr_result.is_correctable,
                'memory_region': self.ddr_result.memory_region,
            })
        
        return features


class CrashAnalyzer:
    """内核崩溃综合分析器"""
    
    def __init__(self):
        """初始化崩溃分析器"""
        self.log_parser = LogParser()
        self.pattern_matcher = PatternMatcher()
        self.ddr_detector = DDRDetector(self.pattern_matcher)
        
        # 分析结果缓存
        self.results: List[CrashAnalysisResult] = []
    
    def analyze_file(self, file_path: Path) -> List[CrashAnalysisResult]:
        """
        分析日志文件
        
        Args:
            file_path: 日志文件路径
            
        Returns:
            崩溃分析结果列表
        """
        # 解析日志
        entries = self.log_parser.parse_file(file_path)
        
        # 查找所有崩溃点
        crash_points = self._find_crash_points(entries)
        
        # 分析每个崩溃
        self.results = []
        for start_line, crash_type in crash_points:
            result = self._analyze_crash(entries, start_line, crash_type)
            self.results.append(result)
        
        return self.results
    
    def analyze_text(self, text: str) -> List[CrashAnalysisResult]:
        """
        分析日志文本
        
        Args:
            text: 日志文本内容
            
        Returns:
            崩溃分析结果列表
        """
        entries = self.log_parser.parse_text(text)
        crash_points = self._find_crash_points(entries)
        
        self.results = []
        for start_line, crash_type in crash_points:
            result = self._analyze_crash(entries, start_line, crash_type)
            self.results.append(result)
        
        return self.results
    
    def _find_crash_points(self, entries: List[LogEntry]) -> List[Tuple[int, str]]:
        """
        查找日志中的所有崩溃起始点
        
        Returns:
            [(行号, 崩溃类型), ...]
        """
        crash_points = []
        
        for entry in entries:
            is_crash, patterns = self.pattern_matcher.is_kernel_crash(entry.raw_text)
            if is_crash:
                crash_type = self.pattern_matcher.extract_crash_type(entry.raw_text)
                crash_points.append((entry.line_number, crash_type))
                entry.is_crash_related = True
        
        # 去重：如果两个崩溃点距离太近，只保留第一个
        filtered_points = []
        last_line = -100
        for line, crash_type in crash_points:
            if line - last_line > 10:  # 至少间隔10行
                filtered_points.append((line, crash_type))
                last_line = line
        
        return filtered_points
    
    def _analyze_crash(
        self, 
        entries: List[LogEntry], 
        start_line: int, 
        crash_type: str
    ) -> CrashAnalysisResult:
        """分析单个崩溃"""
        # 提取崩溃块
        crash_entries = self.log_parser.extract_crash_block(start_line)
        
        # 合并崩溃日志文本
        crash_text = "\n".join(e.raw_text for e in crash_entries)
        
        # 提取地址信息
        addresses = self.pattern_matcher.extract_addresses(crash_text)
        
        # 提取调用栈
        call_trace = self.pattern_matcher.extract_call_trace(crash_text)
        top_function = call_trace[0] if call_trace else None
        
        # 生成签名
        signature = self.pattern_matcher.generate_signature(
            crash_type,
            top_function,
            addresses.get('fault')
        )
        
        # DDR检测
        ddr_result = self.ddr_detector.detect(crash_entries)
        
        # 获取时间戳
        timestamp = None
        for entry in crash_entries:
            if entry.timestamp is not None:
                timestamp = entry.timestamp
                break
        
        # 收集所有匹配的模式
        all_patterns = []
        for entry in crash_entries:
            results = self.pattern_matcher.match_line(entry.raw_text)
            all_patterns.extend(r.pattern for r in results)
        
        # 创建结果
        result = CrashAnalysisResult(
            crash_type=crash_type,
            crash_signature=signature,
            fault_address=addresses.get('fault'),
            pc_address=addresses.get('pc'),
            lr_address=addresses.get('lr'),
            call_trace=call_trace,
            top_function=top_function,
            timestamp=timestamp,
            ddr_result=ddr_result,
            is_ddr_related=ddr_result.is_ddr_related,
            ddr_confidence=ddr_result.confidence,
            crash_entries=crash_entries,
            raw_log_snippet=crash_text,
            matched_patterns=list(set(all_patterns)),
        )
        
        # 添加分析说明
        self._add_analysis_notes(result)
        
        return result
    
    def _add_analysis_notes(self, result: CrashAnalysisResult):
        """添加分析说明"""
        notes = []
        
        # 崩溃类型说明
        if result.crash_type == "NULL Pointer Dereference":
            notes.append("空指针解引用：可能是软件bug，也可能是内存数据被破坏导致指针被清零")
        elif result.crash_type == "Page Fault":
            notes.append("页面错误：尝试访问无效或未映射的内存地址")
        elif result.crash_type == "Kernel Panic":
            notes.append("内核恐慌：系统检测到无法恢复的错误")
        
        # DDR相关说明
        if result.is_ddr_related:
            notes.append(f"DDR故障置信度: {result.ddr_confidence:.1%}")
            if result.ddr_result:
                notes.extend(result.ddr_result.analysis_notes)
        else:
            if result.ddr_confidence > 0.3:
                notes.append(f"可能存在DDR相关问题 (置信度: {result.ddr_confidence:.1%})")
        
        # 调用栈分析
        if result.call_trace:
            # 检查是否有已知的驱动问题
            driver_patterns = ['_probe', '_remove', '_suspend', '_resume']
            for func in result.call_trace[:5]:
                for pattern in driver_patterns:
                    if pattern in func:
                        notes.append(f"可能与驱动程序 '{func}' 相关")
                        break
        
        result.analysis_notes = notes
    
    def get_summary(self) -> Dict:
        """获取分析摘要"""
        if not self.results:
            return {"total_crashes": 0}
        
        ddr_crashes = [r for r in self.results if r.is_ddr_related]
        
        summary = {
            "total_crashes": len(self.results),
            "ddr_related_crashes": len(ddr_crashes),
            "non_ddr_crashes": len(self.results) - len(ddr_crashes),
            "crash_types": {},
            "ddr_fault_types": {},
            "avg_ddr_confidence": 0.0,
        }
        
        # 按崩溃类型统计
        for result in self.results:
            crash_type = result.crash_type
            summary["crash_types"][crash_type] = summary["crash_types"].get(crash_type, 0) + 1
        
        # DDR故障类型统计
        if ddr_crashes:
            for result in ddr_crashes:
                if result.ddr_result:
                    fault_type = result.ddr_result.fault_type.value
                    summary["ddr_fault_types"][fault_type] = \
                        summary["ddr_fault_types"].get(fault_type, 0) + 1
            
            summary["avg_ddr_confidence"] = \
                sum(r.ddr_confidence for r in ddr_crashes) / len(ddr_crashes)
        
        return summary
    
    def get_ddr_crashes(self, min_confidence: float = 0.5) -> List[CrashAnalysisResult]:
        """获取DDR相关的崩溃"""
        return [
            r for r in self.results 
            if r.is_ddr_related and r.ddr_confidence >= min_confidence
        ]
    
    def export_results(self) -> List[dict]:
        """导出分析结果"""
        return [
            {
                "crash_type": r.crash_type,
                "crash_signature": r.crash_signature,
                "timestamp": r.timestamp,
                "fault_address": r.fault_address,
                "top_function": r.top_function,
                "call_trace": r.call_trace,
                "is_ddr_related": r.is_ddr_related,
                "ddr_confidence": r.ddr_confidence,
                "matched_patterns": r.matched_patterns,
                "analysis_notes": r.analysis_notes,
            }
            for r in self.results
        ]

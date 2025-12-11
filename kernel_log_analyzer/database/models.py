"""
数据库模型层 - 定义所有数据库表结构
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    Float, ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""
    pass


class CrashRecord(Base):
    """内核崩溃记录表"""
    __tablename__ = 'crash_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 基本信息
    log_file = Column(String(512), nullable=False, comment="日志文件路径")
    crash_type = Column(String(100), nullable=False, comment="崩溃类型")
    crash_signature = Column(String(256), nullable=True, comment="崩溃签名(用于去重)")
    
    # 时间信息
    timestamp = Column(Float, nullable=True, comment="内核时间戳")
    created_at = Column(DateTime, default=datetime.now, comment="记录创建时间")
    
    # 崩溃详情
    fault_address = Column(String(32), nullable=True, comment="故障地址")
    pc_address = Column(String(32), nullable=True, comment="PC寄存器地址")
    lr_address = Column(String(32), nullable=True, comment="LR寄存器地址")
    
    # 调用栈
    call_trace = Column(Text, nullable=True, comment="调用栈信息")
    top_function = Column(String(256), nullable=True, comment="顶层函数名")
    
    # 原始日志片段
    raw_log_snippet = Column(Text, nullable=True, comment="原始日志片段")
    
    # DDR相关
    is_ddr_related = Column(Boolean, default=False, comment="是否DDR相关")
    ddr_confidence = Column(Float, default=0.0, comment="DDR故障置信度")
    
    # 分析结果
    analysis_result = Column(JSON, nullable=True, comment="详细分析结果(JSON)")
    
    # 关系
    ddr_fault = relationship("DDRFaultRecord", back_populates="crash_record", uselist=False)
    
    # 索引
    __table_args__ = (
        Index('idx_crash_type', 'crash_type'),
        Index('idx_is_ddr_related', 'is_ddr_related'),
        Index('idx_crash_signature', 'crash_signature'),
        Index('idx_created_at', 'created_at'),
    )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'log_file': self.log_file,
            'crash_type': self.crash_type,
            'crash_signature': self.crash_signature,
            'timestamp': self.timestamp,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'fault_address': self.fault_address,
            'pc_address': self.pc_address,
            'lr_address': self.lr_address,
            'call_trace': self.call_trace,
            'top_function': self.top_function,
            'is_ddr_related': self.is_ddr_related,
            'ddr_confidence': self.ddr_confidence,
            'analysis_result': self.analysis_result,
        }


class DDRFaultRecord(Base):
    """DDR位翻转故障记录表"""
    __tablename__ = 'ddr_fault_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    crash_record_id = Column(Integer, ForeignKey('crash_records.id'), nullable=False)
    
    # DDR故障详情
    fault_type = Column(String(100), nullable=False, comment="故障类型(ECC/位翻转/内存损坏等)")
    error_pattern = Column(String(256), nullable=True, comment="匹配的错误模式")
    
    # 内存信息
    memory_address = Column(String(32), nullable=True, comment="内存地址")
    memory_region = Column(String(100), nullable=True, comment="内存区域")
    expected_value = Column(String(32), nullable=True, comment="期望值")
    actual_value = Column(String(32), nullable=True, comment="实际值")
    bit_positions = Column(String(128), nullable=True, comment="翻转的位位置")
    
    # ECC信息
    ecc_syndrome = Column(String(64), nullable=True, comment="ECC校验码")
    is_correctable = Column(Boolean, nullable=True, comment="是否可纠正")
    
    # 置信度和特征
    confidence_score = Column(Float, default=0.0, comment="故障置信度评分")
    matched_patterns = Column(JSON, nullable=True, comment="匹配的所有模式")
    feature_vector = Column(JSON, nullable=True, comment="特征向量(用于ML)")
    
    # 时间信息
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    crash_record = relationship("CrashRecord", back_populates="ddr_fault")
    
    # 索引
    __table_args__ = (
        Index('idx_fault_type', 'fault_type'),
        Index('idx_confidence_score', 'confidence_score'),
    )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'crash_record_id': self.crash_record_id,
            'fault_type': self.fault_type,
            'error_pattern': self.error_pattern,
            'memory_address': self.memory_address,
            'memory_region': self.memory_region,
            'expected_value': self.expected_value,
            'actual_value': self.actual_value,
            'bit_positions': self.bit_positions,
            'ecc_syndrome': self.ecc_syndrome,
            'is_correctable': self.is_correctable,
            'confidence_score': self.confidence_score,
            'matched_patterns': self.matched_patterns,
            'feature_vector': self.feature_vector,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeEntry(Base):
    """知识库条目表 - 用于存储已确认的故障模式"""
    __tablename__ = 'knowledge_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 知识条目信息
    title = Column(String(256), nullable=False, comment="条目标题")
    category = Column(String(100), nullable=False, comment="分类(DDR/内核/驱动等)")
    subcategory = Column(String(100), nullable=True, comment="子分类")
    
    # 模式信息
    signature_pattern = Column(String(512), nullable=False, comment="故障签名模式")
    regex_pattern = Column(Text, nullable=True, comment="正则表达式模式")
    keywords = Column(JSON, nullable=True, comment="关键词列表")
    
    # 描述和解决方案
    description = Column(Text, nullable=True, comment="详细描述")
    root_cause = Column(Text, nullable=True, comment="根本原因")
    solution = Column(Text, nullable=True, comment="解决方案")
    
    # 来源信息
    source = Column(String(256), nullable=True, comment="来源(设备/项目等)")
    source_machine = Column(String(128), nullable=True, comment="来源机器标识")
    
    # 统计信息
    occurrence_count = Column(Integer, default=1, comment="出现次数")
    confirmed = Column(Boolean, default=False, comment="是否已确认")
    
    # 机器学习相关
    ml_label = Column(String(50), nullable=True, comment="ML标签")
    feature_template = Column(JSON, nullable=True, comment="特征模板")
    
    # 时间信息
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 约束和索引
    __table_args__ = (
        UniqueConstraint('signature_pattern', 'source_machine', name='uq_signature_source'),
        Index('idx_category', 'category'),
        Index('idx_confirmed', 'confirmed'),
        Index('idx_ml_label', 'ml_label'),
    )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'subcategory': self.subcategory,
            'signature_pattern': self.signature_pattern,
            'regex_pattern': self.regex_pattern,
            'keywords': self.keywords,
            'description': self.description,
            'root_cause': self.root_cause,
            'solution': self.solution,
            'source': self.source,
            'source_machine': self.source_machine,
            'occurrence_count': self.occurrence_count,
            'confirmed': self.confirmed,
            'ml_label': self.ml_label,
            'feature_template': self.feature_template,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'KnowledgeEntry':
        """从字典创建实例"""
        # 过滤掉不属于模型的字段
        valid_fields = {
            'title', 'category', 'subcategory', 'signature_pattern',
            'regex_pattern', 'keywords', 'description', 'root_cause',
            'solution', 'source', 'source_machine', 'occurrence_count',
            'confirmed', 'ml_label', 'feature_template'
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

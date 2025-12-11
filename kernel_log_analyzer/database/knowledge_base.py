"""
知识库管理层 - 提供知识库的导入导出和合并功能
"""
import json
import hashlib
import socket
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from .models import KnowledgeEntry, CrashRecord, DDRFaultRecord
from .db_manager import DatabaseManager
from config.settings import settings


class KnowledgeBase:
    """知识库管理器 - 支持知识库的导入、导出和合并"""
    
    EXPORT_VERSION = "1.0"
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化知识库管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db = db_manager or DatabaseManager()
        self.machine_id = self._get_machine_id()
    
    def _get_machine_id(self) -> str:
        """获取机器唯一标识"""
        hostname = socket.gethostname()
        # 生成一个基于主机名的简短ID
        hash_obj = hashlib.md5(hostname.encode())
        return f"{hostname}_{hash_obj.hexdigest()[:8]}"
    
    # ==================== 导出功能 ====================
    
    def export_knowledge_base(
        self,
        output_path: Optional[Path] = None,
        category: Optional[str] = None,
        confirmed_only: bool = False,
        include_crash_records: bool = False
    ) -> Path:
        """
        导出知识库到JSON文件
        
        Args:
            output_path: 输出文件路径
            category: 只导出特定分类
            confirmed_only: 只导出已确认的条目
            include_crash_records: 是否包含相关的崩溃记录
            
        Returns:
            导出文件的路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = settings.export_dir / f"knowledge_export_{timestamp}.json"
        
        # 获取知识条目
        entries = self.db.get_knowledge_entries(
            category=category,
            confirmed_only=confirmed_only,
            limit=10000
        )
        
        export_data = {
            "version": self.EXPORT_VERSION,
            "export_time": datetime.now().isoformat(),
            "source_machine": self.machine_id,
            "entry_count": len(entries),
            "knowledge_entries": entries,
        }
        
        # 可选包含崩溃记录
        if include_crash_records:
            crash_records = self.db.get_crash_records(limit=10000)
            export_data["crash_records"] = crash_records
            export_data["crash_record_count"] = len(crash_records)
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def export_for_ml(self, output_path: Optional[Path] = None) -> Path:
        """
        导出用于机器学习训练的数据
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            导出文件的路径
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = settings.export_dir / f"ml_training_data_{timestamp}.json"
        
        with self.db.get_session() as session:
            # 获取所有已确认的知识条目
            entries = session.query(KnowledgeEntry).filter(
                KnowledgeEntry.confirmed == True,
                KnowledgeEntry.ml_label.isnot(None)
            ).all()
            
            # 获取所有DDR相关的崩溃记录
            ddr_crashes = session.query(CrashRecord).filter(
                CrashRecord.is_ddr_related == True
            ).all()
            
            # 构建训练数据
            training_samples = []
            
            # 从知识条目生成样本
            for entry in entries:
                sample = {
                    "id": f"kb_{entry.id}",
                    "source": "knowledge_base",
                    "text": entry.signature_pattern,
                    "label": entry.ml_label,
                    "category": entry.category,
                    "features": entry.feature_template or {},
                    "keywords": entry.keywords or [],
                    "confirmed": True
                }
                training_samples.append(sample)
            
            # 从崩溃记录生成样本
            for crash in ddr_crashes:
                sample = {
                    "id": f"crash_{crash.id}",
                    "source": "crash_record",
                    "text": crash.raw_log_snippet or "",
                    "label": "ddr_related" if crash.is_ddr_related else "non_ddr",
                    "category": crash.crash_type,
                    "features": crash.analysis_result or {},
                    "confidence": crash.ddr_confidence,
                    "confirmed": crash.ddr_confidence >= 0.8
                }
                training_samples.append(sample)
        
        export_data = {
            "version": self.EXPORT_VERSION,
            "export_time": datetime.now().isoformat(),
            "source_machine": self.machine_id,
            "sample_count": len(training_samples),
            "samples": training_samples,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    # ==================== 导入功能 ====================
    
    def import_knowledge_base(
        self,
        input_path: Path,
        merge_strategy: str = "update"
    ) -> Dict[str, int]:
        """
        从JSON文件导入知识库
        
        Args:
            input_path: 输入文件路径
            merge_strategy: 合并策略
                - "update": 更新已存在的条目
                - "skip": 跳过已存在的条目
                - "duplicate": 允许重复
                
        Returns:
            导入统计信息
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        stats = {
            "total": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        entries = import_data.get("knowledge_entries", [])
        source_machine = import_data.get("source_machine", "unknown")
        
        for entry_data in entries:
            stats["total"] += 1
            try:
                result = self._import_single_entry(
                    entry_data, source_machine, merge_strategy
                )
                stats[result] += 1
            except Exception as e:
                stats["errors"] += 1
                print(f"导入条目失败: {e}")
        
        return stats
    
    def _import_single_entry(
        self,
        entry_data: dict,
        source_machine: str,
        merge_strategy: str
    ) -> str:
        """导入单个知识条目"""
        signature = entry_data.get("signature_pattern", "")
        
        # 检查是否已存在
        existing = self._find_existing_entry(signature)
        
        if existing:
            if merge_strategy == "skip":
                return "skipped"
            elif merge_strategy == "update":
                # 更新现有条目
                self._merge_entry(existing["id"], entry_data)
                return "updated"
        
        # 创建新条目
        entry_data["source_machine"] = source_machine
        entry = KnowledgeEntry.from_dict(entry_data)
        self.db.add_knowledge_entry(entry)
        return "added"
    
    def _find_existing_entry(self, signature: str) -> Optional[dict]:
        """查找已存在的条目"""
        entries = self.db.search_knowledge_entries(signature)
        for entry in entries:
            if entry["signature_pattern"] == signature:
                return entry
        return None
    
    def _merge_entry(self, entry_id: int, new_data: dict):
        """合并更新条目"""
        # 增加出现次数
        with self.db.get_session() as session:
            entry = session.get(KnowledgeEntry, entry_id)
            if entry:
                entry.occurrence_count += new_data.get("occurrence_count", 1)
                # 合并关键词
                if new_data.get("keywords"):
                    existing_keywords = entry.keywords or []
                    new_keywords = new_data.get("keywords", [])
                    entry.keywords = list(set(existing_keywords + new_keywords))
    
    # ==================== 合并功能 ====================
    
    def merge_knowledge_bases(
        self,
        file_paths: List[Path],
        output_path: Optional[Path] = None
    ) -> Tuple[Path, Dict[str, int]]:
        """
        合并多个知识库文件
        
        Args:
            file_paths: 要合并的文件路径列表
            output_path: 输出文件路径
            
        Returns:
            (输出文件路径, 合并统计信息)
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = settings.export_dir / f"merged_knowledge_{timestamp}.json"
        
        merged_entries = {}
        stats = {
            "total_files": len(file_paths),
            "total_entries": 0,
            "unique_entries": 0,
            "merged_entries": 0
        }
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                entries = data.get("knowledge_entries", [])
                source = data.get("source_machine", "unknown")
                
                for entry in entries:
                    stats["total_entries"] += 1
                    signature = entry.get("signature_pattern", "")
                    
                    if signature in merged_entries:
                        # 合并现有条目
                        self._merge_entry_data(merged_entries[signature], entry)
                        stats["merged_entries"] += 1
                    else:
                        entry["source_machines"] = [source]
                        merged_entries[signature] = entry
                        stats["unique_entries"] += 1
                        
            except Exception as e:
                print(f"处理文件 {file_path} 失败: {e}")
        
        # 写入合并后的文件
        export_data = {
            "version": self.EXPORT_VERSION,
            "export_time": datetime.now().isoformat(),
            "merge_stats": stats,
            "entry_count": len(merged_entries),
            "knowledge_entries": list(merged_entries.values()),
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path, stats
    
    def _merge_entry_data(self, existing: dict, new: dict):
        """合并两个条目的数据"""
        # 累加出现次数
        existing["occurrence_count"] = (
            existing.get("occurrence_count", 1) + 
            new.get("occurrence_count", 1)
        )
        
        # 合并关键词
        existing_keywords = set(existing.get("keywords") or [])
        new_keywords = set(new.get("keywords") or [])
        existing["keywords"] = list(existing_keywords | new_keywords)
        
        # 合并来源机器
        if "source_machines" in existing:
            source = new.get("source_machine", "unknown")
            if source not in existing["source_machines"]:
                existing["source_machines"].append(source)
    
    # ==================== 知识库维护 ====================
    
    def add_from_crash_analysis(
        self,
        crash_record: CrashRecord,
        category: str = "DDR",
        auto_confirm: bool = False
    ) -> Optional[KnowledgeEntry]:
        """
        从崩溃分析结果创建知识库条目
        
        Args:
            crash_record: 崩溃记录
            category: 分类
            auto_confirm: 是否自动确认
            
        Returns:
            创建的知识库条目
        """
        if not crash_record.crash_signature:
            return None
        
        # 检查是否已存在
        existing = self._find_existing_entry(crash_record.crash_signature)
        if existing:
            self.db.increment_occurrence_count(crash_record.crash_signature)
            return None
        
        # 创建新条目
        entry = KnowledgeEntry(
            title=f"{crash_record.crash_type} - {crash_record.top_function or 'Unknown'}",
            category=category,
            subcategory=crash_record.crash_type,
            signature_pattern=crash_record.crash_signature,
            description=crash_record.raw_log_snippet[:500] if crash_record.raw_log_snippet else None,
            source=crash_record.log_file,
            source_machine=self.machine_id,
            confirmed=auto_confirm,
            ml_label="ddr_related" if crash_record.is_ddr_related else "non_ddr",
            feature_template=crash_record.analysis_result
        )
        
        return self.db.add_knowledge_entry(entry)
    
    def confirm_entry(self, entry_id: int, root_cause: str = None, solution: str = None):
        """确认知识库条目"""
        update_data = {"confirmed": True}
        if root_cause:
            update_data["root_cause"] = root_cause
        if solution:
            update_data["solution"] = solution
        self.db.update_knowledge_entry(entry_id, **update_data)
    
    def get_statistics(self) -> dict:
        """获取知识库统计信息"""
        base_stats = self.db.get_statistics()
        
        # 添加知识库特定统计
        with self.db.get_session() as session:
            category_stats = {}
            for entry in session.query(KnowledgeEntry).all():
                cat = entry.category
                if cat not in category_stats:
                    category_stats[cat] = {"total": 0, "confirmed": 0}
                category_stats[cat]["total"] += 1
                if entry.confirmed:
                    category_stats[cat]["confirmed"] += 1
        
        base_stats["category_stats"] = category_stats
        return base_stats

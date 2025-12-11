"""
数据库管理层 - 提供数据库连接和基础CRUD操作
"""
from typing import Optional, List, Type, TypeVar
from pathlib import Path
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from .models import Base, CrashRecord, DDRFaultRecord, KnowledgeEntry
from config.settings import settings

T = TypeVar('T', bound=Base)


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，默认使用配置中的路径
        """
        self.db_path = db_path or settings.db_path
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            future=True
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # ==================== 通用CRUD操作 ====================
    
    def add(self, obj: T) -> T:
        """添加记录"""
        with self.get_session() as session:
            session.add(obj)
            session.flush()
            session.refresh(obj)
            # 需要在session关闭前获取所有属性
            obj_dict = obj.to_dict()
        return obj
    
    def add_all(self, objects: List[T]) -> List[T]:
        """批量添加记录"""
        with self.get_session() as session:
            session.add_all(objects)
            session.flush()
            for obj in objects:
                session.refresh(obj)
        return objects
    
    def get_by_id(self, model: Type[T], id: int) -> Optional[T]:
        """根据ID获取记录"""
        with self.get_session() as session:
            return session.get(model, id)
    
    def get_all(self, model: Type[T], limit: int = 1000) -> List[T]:
        """获取所有记录"""
        with self.get_session() as session:
            return list(session.query(model).limit(limit).all())
    
    def delete(self, obj: T) -> bool:
        """删除记录"""
        with self.get_session() as session:
            session.delete(obj)
        return True
    
    def delete_by_id(self, model: Type[T], id: int) -> bool:
        """根据ID删除记录"""
        with self.get_session() as session:
            obj = session.get(model, id)
            if obj:
                session.delete(obj)
                return True
        return False
    
    # ==================== CrashRecord 操作 ====================
    
    def add_crash_record(self, record: CrashRecord) -> CrashRecord:
        """添加崩溃记录"""
        with self.get_session() as session:
            session.add(record)
            session.flush()
            record_id = record.id
        return self.get_crash_record_by_id(record_id)
    
    def get_crash_record_by_id(self, id: int) -> Optional[CrashRecord]:
        """根据ID获取崩溃记录"""
        with self.get_session() as session:
            return session.get(CrashRecord, id)
    
    def get_crash_records(
        self, 
        crash_type: Optional[str] = None,
        is_ddr_related: Optional[bool] = None,
        limit: int = 100
    ) -> List[dict]:
        """获取崩溃记录列表"""
        with self.get_session() as session:
            query = session.query(CrashRecord)
            
            if crash_type:
                query = query.filter(CrashRecord.crash_type == crash_type)
            if is_ddr_related is not None:
                query = query.filter(CrashRecord.is_ddr_related == is_ddr_related)
            
            query = query.order_by(CrashRecord.created_at.desc()).limit(limit)
            return [r.to_dict() for r in query.all()]
    
    def get_ddr_crash_records(self, min_confidence: float = 0.5) -> List[dict]:
        """获取DDR相关的崩溃记录"""
        with self.get_session() as session:
            query = session.query(CrashRecord).filter(
                CrashRecord.is_ddr_related == True,
                CrashRecord.ddr_confidence >= min_confidence
            ).order_by(CrashRecord.ddr_confidence.desc())
            return [r.to_dict() for r in query.all()]
    
    def check_crash_signature_exists(self, signature: str) -> bool:
        """检查崩溃签名是否已存在"""
        with self.get_session() as session:
            count = session.query(CrashRecord).filter(
                CrashRecord.crash_signature == signature
            ).count()
            return count > 0
    
    # ==================== DDRFaultRecord 操作 ====================
    
    def add_ddr_fault_record(
        self, 
        crash_record_id: int, 
        fault_record: DDRFaultRecord
    ) -> DDRFaultRecord:
        """添加DDR故障记录"""
        fault_record.crash_record_id = crash_record_id
        with self.get_session() as session:
            session.add(fault_record)
            session.flush()
            fault_id = fault_record.id
        return self.get_ddr_fault_by_id(fault_id)
    
    def get_ddr_fault_by_id(self, id: int) -> Optional[DDRFaultRecord]:
        """根据ID获取DDR故障记录"""
        with self.get_session() as session:
            return session.get(DDRFaultRecord, id)
    
    def get_ddr_faults_by_type(self, fault_type: str) -> List[dict]:
        """根据故障类型获取DDR故障记录"""
        with self.get_session() as session:
            query = session.query(DDRFaultRecord).filter(
                DDRFaultRecord.fault_type == fault_type
            )
            return [r.to_dict() for r in query.all()]
    
    # ==================== KnowledgeEntry 操作 ====================
    
    def add_knowledge_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """添加知识库条目"""
        with self.get_session() as session:
            session.add(entry)
            session.flush()
            entry_id = entry.id
        return self.get_knowledge_entry_by_id(entry_id)
    
    def get_knowledge_entry_by_id(self, id: int) -> Optional[KnowledgeEntry]:
        """根据ID获取知识库条目"""
        with self.get_session() as session:
            return session.get(KnowledgeEntry, id)
    
    def get_knowledge_entries(
        self,
        category: Optional[str] = None,
        confirmed_only: bool = False,
        limit: int = 1000
    ) -> List[dict]:
        """获取知识库条目列表"""
        with self.get_session() as session:
            query = session.query(KnowledgeEntry)
            
            if category:
                query = query.filter(KnowledgeEntry.category == category)
            if confirmed_only:
                query = query.filter(KnowledgeEntry.confirmed == True)
            
            query = query.order_by(KnowledgeEntry.occurrence_count.desc()).limit(limit)
            return [e.to_dict() for e in query.all()]
    
    def search_knowledge_entries(self, keyword: str) -> List[dict]:
        """搜索知识库条目"""
        with self.get_session() as session:
            query = session.query(KnowledgeEntry).filter(
                (KnowledgeEntry.title.contains(keyword)) |
                (KnowledgeEntry.description.contains(keyword)) |
                (KnowledgeEntry.signature_pattern.contains(keyword))
            )
            return [e.to_dict() for e in query.all()]
    
    def update_knowledge_entry(self, id: int, **kwargs) -> Optional[KnowledgeEntry]:
        """更新知识库条目"""
        with self.get_session() as session:
            entry = session.get(KnowledgeEntry, id)
            if entry:
                for key, value in kwargs.items():
                    if hasattr(entry, key):
                        setattr(entry, key, value)
                session.flush()
        return self.get_knowledge_entry_by_id(id)
    
    def increment_occurrence_count(self, signature: str) -> bool:
        """增加知识条目的出现次数"""
        with self.get_session() as session:
            entry = session.query(KnowledgeEntry).filter(
                KnowledgeEntry.signature_pattern == signature
            ).first()
            if entry:
                entry.occurrence_count += 1
                return True
        return False
    
    # ==================== 统计操作 ====================
    
    def get_statistics(self) -> dict:
        """获取数据库统计信息"""
        with self.get_session() as session:
            total_crashes = session.query(CrashRecord).count()
            ddr_crashes = session.query(CrashRecord).filter(
                CrashRecord.is_ddr_related == True
            ).count()
            knowledge_entries = session.query(KnowledgeEntry).count()
            confirmed_entries = session.query(KnowledgeEntry).filter(
                KnowledgeEntry.confirmed == True
            ).count()
            
            # 按崩溃类型统计
            crash_type_stats = {}
            for row in session.execute(
                text("SELECT crash_type, COUNT(*) as cnt FROM crash_records GROUP BY crash_type")
            ):
                crash_type_stats[row[0]] = row[1]
            
            return {
                'total_crashes': total_crashes,
                'ddr_crashes': ddr_crashes,
                'non_ddr_crashes': total_crashes - ddr_crashes,
                'knowledge_entries': knowledge_entries,
                'confirmed_entries': confirmed_entries,
                'crash_type_stats': crash_type_stats,
            }
    
    def clear_all_data(self):
        """清空所有数据（谨慎使用）"""
        with self.get_session() as session:
            session.query(DDRFaultRecord).delete()
            session.query(CrashRecord).delete()
            session.query(KnowledgeEntry).delete()

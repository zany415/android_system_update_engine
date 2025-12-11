"""
机器学习数据导出器 - 导出用于训练的数据集
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

from config.settings import settings
from database.db_manager import DatabaseManager
from database.knowledge_base import KnowledgeBase
from core.crash_analyzer import CrashAnalysisResult
from .feature_extractor import FeatureExtractor, FeatureVector


class MLDataExporter:
    """机器学习数据导出器"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        初始化数据导出器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db = db_manager or DatabaseManager()
        self.knowledge_base = KnowledgeBase(self.db)
        self.feature_extractor = FeatureExtractor()
    
    def export_training_data(
        self,
        output_dir: Optional[Path] = None,
        format: str = "all",  # "json", "csv", "numpy", "all"
        include_raw_text: bool = False,
        min_confidence: float = 0.0
    ) -> Dict[str, Path]:
        """
        导出训练数据集
        
        Args:
            output_dir: 输出目录
            format: 导出格式
            include_raw_text: 是否包含原始日志文本
            min_confidence: 最小置信度阈值
            
        Returns:
            导出文件路径字典
        """
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = settings.export_dir / f"ml_dataset_{timestamp}"
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 收集数据
        samples = self._collect_samples(min_confidence)
        
        if not samples:
            return {}
        
        exported_files = {}
        
        if format in ("json", "all"):
            json_path = self._export_json(samples, output_dir, include_raw_text)
            exported_files["json"] = json_path
        
        if format in ("csv", "all"):
            csv_path = self._export_csv(samples, output_dir)
            exported_files["csv"] = csv_path
        
        if format in ("numpy", "all"):
            numpy_paths = self._export_numpy(samples, output_dir)
            exported_files.update(numpy_paths)
        
        # 导出元数据
        meta_path = self._export_metadata(samples, output_dir)
        exported_files["metadata"] = meta_path
        
        return exported_files
    
    def _collect_samples(self, min_confidence: float) -> List[Dict]:
        """收集训练样本"""
        samples = []
        
        # 从崩溃记录收集
        crash_records = self.db.get_crash_records(limit=10000)
        for record in crash_records:
            if record.get('ddr_confidence', 0) >= min_confidence or not record.get('is_ddr_related'):
                sample = {
                    'id': f"crash_{record['id']}",
                    'source': 'crash_record',
                    'crash_type': record.get('crash_type', ''),
                    'is_ddr_related': record.get('is_ddr_related', False),
                    'confidence': record.get('ddr_confidence', 0.0),
                    'raw_text': record.get('raw_log_snippet', ''),
                    'analysis_result': record.get('analysis_result', {}),
                    'label': 'ddr_related' if record.get('is_ddr_related') else 'non_ddr'
                }
                
                # 提取特征
                if sample['raw_text']:
                    features = self.feature_extractor.extract_from_text(
                        sample['raw_text'],
                        sample['label']
                    )
                    sample['features'] = features.to_dict()
                
                samples.append(sample)
        
        # 从知识库收集
        knowledge_entries = self.db.get_knowledge_entries(confirmed_only=True, limit=5000)
        for entry in knowledge_entries:
            if entry.get('ml_label'):
                sample = {
                    'id': f"kb_{entry['id']}",
                    'source': 'knowledge_base',
                    'category': entry.get('category', ''),
                    'signature': entry.get('signature_pattern', ''),
                    'keywords': entry.get('keywords', []),
                    'label': entry.get('ml_label', ''),
                    'confirmed': True
                }
                
                # 使用签名模式作为特征输入
                if sample['signature']:
                    features = self.feature_extractor.extract_from_text(
                        sample['signature'],
                        sample['label']
                    )
                    sample['features'] = features.to_dict()
                
                samples.append(sample)
        
        return samples
    
    def _export_json(
        self, 
        samples: List[Dict], 
        output_dir: Path,
        include_raw_text: bool
    ) -> Path:
        """导出JSON格式"""
        output_path = output_dir / "training_data.json"
        
        export_samples = []
        for sample in samples:
            export_sample = sample.copy()
            if not include_raw_text:
                export_sample.pop('raw_text', None)
            export_samples.append(export_sample)
        
        export_data = {
            "version": "1.0",
            "export_time": datetime.now().isoformat(),
            "sample_count": len(export_samples),
            "label_distribution": self._get_label_distribution(samples),
            "samples": export_samples
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def _export_csv(self, samples: List[Dict], output_dir: Path) -> Path:
        """导出CSV格式（只包含数值特征）"""
        output_path = output_dir / "training_features.csv"
        
        # 获取特征名称
        feature_names = self.feature_extractor.get_feature_names()
        headers = ['id', 'source', 'label'] + feature_names
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for sample in samples:
                if 'features' not in sample:
                    continue
                
                features = sample['features']
                row = [
                    sample['id'],
                    sample['source'],
                    sample['label']
                ]
                
                # 添加数值特征
                if 'numeric_vector' in features:
                    row.extend(features['numeric_vector'])
                else:
                    row.extend([0] * len(feature_names))
                
                writer.writerow(row)
        
        return output_path
    
    def _export_numpy(self, samples: List[Dict], output_dir: Path) -> Dict[str, Path]:
        """导出NumPy格式"""
        paths = {}
        
        # 收集特征向量和标签
        feature_vectors = []
        labels = []
        sample_ids = []
        
        for sample in samples:
            if 'features' not in sample:
                continue
            
            features = sample['features']
            if 'numeric_vector' in features:
                feature_vectors.append(features['numeric_vector'])
                labels.append(1 if sample['label'] == 'ddr_related' else 0)
                sample_ids.append(sample['id'])
        
        if feature_vectors:
            # 保存特征矩阵
            X = np.array(feature_vectors, dtype=np.float32)
            features_path = output_dir / "features.npy"
            np.save(features_path, X)
            paths["features_npy"] = features_path
            
            # 保存标签
            y = np.array(labels, dtype=np.int32)
            labels_path = output_dir / "labels.npy"
            np.save(labels_path, y)
            paths["labels_npy"] = labels_path
            
            # 保存样本ID（用于追溯）
            ids_path = output_dir / "sample_ids.json"
            with open(ids_path, 'w') as f:
                json.dump(sample_ids, f)
            paths["sample_ids"] = ids_path
        
        return paths
    
    def _export_metadata(self, samples: List[Dict], output_dir: Path) -> Path:
        """导出元数据"""
        output_path = output_dir / "metadata.json"
        
        metadata = {
            "export_time": datetime.now().isoformat(),
            "total_samples": len(samples),
            "label_distribution": self._get_label_distribution(samples),
            "source_distribution": self._get_source_distribution(samples),
            "feature_names": self.feature_extractor.get_feature_names(),
            "feature_count": len(self.feature_extractor.get_feature_names()),
            "crash_type_map": FeatureExtractor.CRASH_TYPE_MAP,
            "fault_type_map": FeatureExtractor.FAULT_TYPE_MAP,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def _get_label_distribution(self, samples: List[Dict]) -> Dict[str, int]:
        """获取标签分布"""
        distribution = {}
        for sample in samples:
            label = sample.get('label', 'unknown')
            distribution[label] = distribution.get(label, 0) + 1
        return distribution
    
    def _get_source_distribution(self, samples: List[Dict]) -> Dict[str, int]:
        """获取数据来源分布"""
        distribution = {}
        for sample in samples:
            source = sample.get('source', 'unknown')
            distribution[source] = distribution.get(source, 0) + 1
        return distribution
    
    def create_train_test_split(
        self,
        samples: List[Dict],
        test_ratio: float = 0.2,
        random_seed: int = 42
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        创建训练集和测试集划分
        
        Args:
            samples: 样本列表
            test_ratio: 测试集比例
            random_seed: 随机种子
            
        Returns:
            (训练集, 测试集)
        """
        np.random.seed(random_seed)
        
        # 按标签分层采样
        label_groups = {}
        for sample in samples:
            label = sample.get('label', 'unknown')
            if label not in label_groups:
                label_groups[label] = []
            label_groups[label].append(sample)
        
        train_samples = []
        test_samples = []
        
        for label, group in label_groups.items():
            np.random.shuffle(group)
            split_idx = int(len(group) * (1 - test_ratio))
            train_samples.extend(group[:split_idx])
            test_samples.extend(group[split_idx:])
        
        return train_samples, test_samples
    
    def export_split_datasets(
        self,
        output_dir: Optional[Path] = None,
        test_ratio: float = 0.2,
        format: str = "all"
    ) -> Dict[str, Path]:
        """导出划分后的训练集和测试集"""
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = settings.export_dir / f"ml_dataset_split_{timestamp}"
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 收集并划分数据
        samples = self._collect_samples(min_confidence=0.0)
        train_samples, test_samples = self.create_train_test_split(samples, test_ratio)
        
        exported_files = {}
        
        # 导出训练集
        train_dir = output_dir / "train"
        train_dir.mkdir(exist_ok=True)
        train_files = self._export_split(train_samples, train_dir, format)
        exported_files["train"] = train_files
        
        # 导出测试集
        test_dir = output_dir / "test"
        test_dir.mkdir(exist_ok=True)
        test_files = self._export_split(test_samples, test_dir, format)
        exported_files["test"] = test_files
        
        # 导出划分信息
        split_info = {
            "total_samples": len(samples),
            "train_samples": len(train_samples),
            "test_samples": len(test_samples),
            "test_ratio": test_ratio,
            "train_label_distribution": self._get_label_distribution(train_samples),
            "test_label_distribution": self._get_label_distribution(test_samples),
        }
        
        split_info_path = output_dir / "split_info.json"
        with open(split_info_path, 'w') as f:
            json.dump(split_info, f, indent=2)
        exported_files["split_info"] = split_info_path
        
        return exported_files
    
    def _export_split(
        self, 
        samples: List[Dict], 
        output_dir: Path,
        format: str
    ) -> Dict[str, Path]:
        """导出单个数据集划分"""
        files = {}
        
        if format in ("json", "all"):
            json_path = output_dir / "data.json"
            with open(json_path, 'w') as f:
                json.dump(samples, f, ensure_ascii=False, indent=2)
            files["json"] = json_path
        
        if format in ("csv", "all"):
            files["csv"] = self._export_csv(samples, output_dir)
        
        if format in ("numpy", "all"):
            numpy_files = self._export_numpy(samples, output_dir)
            files.update(numpy_files)
        
        return files

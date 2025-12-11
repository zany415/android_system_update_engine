"""
文件工具类 - 提供文件操作的通用功能
"""
import os
import gzip
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple, Generator
from datetime import datetime


class FileUtils:
    """文件工具类"""
    
    # 支持的日志文件扩展名
    SUPPORTED_EXTENSIONS = {'.log', '.txt', '.dmesg', '.kmsg', '.gz'}
    
    # 压缩文件扩展名
    COMPRESSED_EXTENSIONS = {'.gz', '.zip'}
    
    @staticmethod
    def is_log_file(file_path: Path) -> bool:
        """检查是否是支持的日志文件"""
        return file_path.suffix.lower() in FileUtils.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def is_compressed(file_path: Path) -> bool:
        """检查是否是压缩文件"""
        return file_path.suffix.lower() in FileUtils.COMPRESSED_EXTENSIONS
    
    @staticmethod
    def read_file(file_path: Path, encoding: str = 'utf-8') -> str:
        """
        读取文件内容，自动处理压缩文件
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            
        Returns:
            文件内容
        """
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.gz':
            with gzip.open(file_path, 'rt', encoding=encoding) as f:
                return f.read()
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
    
    @staticmethod
    def read_file_with_fallback(file_path: Path) -> Tuple[str, str]:
        """
        使用多种编码尝试读取文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            (文件内容, 使用的编码)
        """
        encodings = ['utf-8', 'latin-1', 'gbk', 'gb2312', 'cp1252']
        
        for encoding in encodings:
            try:
                content = FileUtils.read_file(file_path, encoding)
                return content, encoding
            except UnicodeDecodeError:
                continue
        
        # 最后尝试忽略错误
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(), 'utf-8 (with errors ignored)'
    
    @staticmethod
    def get_file_info(file_path: Path) -> dict:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        file_path = Path(file_path)
        stat = file_path.stat()
        
        return {
            'name': file_path.name,
            'path': str(file_path.absolute()),
            'size': stat.st_size,
            'size_human': FileUtils.format_size(stat.st_size),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'extension': file_path.suffix,
            'is_compressed': FileUtils.is_compressed(file_path),
        }
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def find_log_files(directory: Path, recursive: bool = True) -> List[Path]:
        """
        在目录中查找日志文件
        
        Args:
            directory: 搜索目录
            recursive: 是否递归搜索
            
        Returns:
            日志文件路径列表
        """
        directory = Path(directory)
        log_files = []
        
        if recursive:
            for ext in FileUtils.SUPPORTED_EXTENSIONS:
                log_files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in FileUtils.SUPPORTED_EXTENSIONS:
                log_files.extend(directory.glob(f"*{ext}"))
        
        return sorted(log_files)
    
    @staticmethod
    def iter_file_lines(
        file_path: Path, 
        encoding: str = 'utf-8',
        chunk_size: int = 8192
    ) -> Generator[str, None, None]:
        """
        按行迭代大文件（内存友好）
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            chunk_size: 读取块大小
            
        Yields:
            每行内容
        """
        file_path = Path(file_path)
        
        if file_path.suffix.lower() == '.gz':
            with gzip.open(file_path, 'rt', encoding=encoding) as f:
                for line in f:
                    yield line.rstrip('\n\r')
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                for line in f:
                    yield line.rstrip('\n\r')
    
    @staticmethod
    def extract_zip(zip_path: Path, extract_to: Optional[Path] = None) -> Path:
        """
        解压ZIP文件
        
        Args:
            zip_path: ZIP文件路径
            extract_to: 解压目标目录
            
        Returns:
            解压目录路径
        """
        zip_path = Path(zip_path)
        
        if extract_to is None:
            extract_to = zip_path.parent / zip_path.stem
        
        extract_to = Path(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_to)
        
        return extract_to
    
    @staticmethod
    def create_backup(file_path: Path) -> Path:
        """
        创建文件备份
        
        Args:
            file_path: 要备份的文件路径
            
        Returns:
            备份文件路径
        """
        file_path = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".{timestamp}.bak{file_path.suffix}")
        
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    @staticmethod
    def ensure_dir(dir_path: Path) -> Path:
        """确保目录存在"""
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    @staticmethod
    def get_unique_filename(directory: Path, base_name: str, extension: str) -> Path:
        """
        获取唯一的文件名（避免覆盖）
        
        Args:
            directory: 目录
            base_name: 基础文件名
            extension: 扩展名
            
        Returns:
            唯一的文件路径
        """
        directory = Path(directory)
        
        if not extension.startswith('.'):
            extension = '.' + extension
        
        file_path = directory / f"{base_name}{extension}"
        
        if not file_path.exists():
            return file_path
        
        counter = 1
        while True:
            file_path = directory / f"{base_name}_{counter}{extension}"
            if not file_path.exists():
                return file_path
            counter += 1
    
    @staticmethod
    def count_lines(file_path: Path) -> int:
        """快速统计文件行数"""
        file_path = Path(file_path)
        
        count = 0
        if file_path.suffix.lower() == '.gz':
            with gzip.open(file_path, 'rt') as f:
                for _ in f:
                    count += 1
        else:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    count += chunk.count(b'\n')
        
        return count

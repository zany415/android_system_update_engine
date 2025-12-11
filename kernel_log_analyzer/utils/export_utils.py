"""
导出工具类 - 提供多种格式的导出功能
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any

from config.settings import settings


class ExportUtils:
    """导出工具类"""
    
    @staticmethod
    def export_to_json(
        data: Any,
        output_path: Path,
        indent: int = 2,
        ensure_ascii: bool = False
    ) -> Path:
        """
        导出数据到JSON文件
        
        Args:
            data: 要导出的数据
            output_path: 输出文件路径
            indent: 缩进空格数
            ensure_ascii: 是否转义非ASCII字符
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii, default=str)
        
        return output_path
    
    @staticmethod
    def export_to_csv(
        data: List[Dict],
        output_path: Path,
        headers: Optional[List[str]] = None
    ) -> Path:
        """
        导出数据到CSV文件
        
        Args:
            data: 字典列表
            output_path: 输出文件路径
            headers: 列标题（默认使用字典的键）
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not data:
            return output_path
        
        if headers is None:
            headers = list(data[0].keys())
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        
        return output_path
    
    @staticmethod
    def export_to_html(
        data: List[Dict],
        output_path: Path,
        title: str = "分析报告",
        headers: Optional[List[str]] = None
    ) -> Path:
        """
        导出数据到HTML报告
        
        Args:
            data: 字典列表
            output_path: 输出文件路径
            title: 报告标题
            headers: 列标题
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if headers is None and data:
            headers = list(data[0].keys())
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        .meta {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f1f1f1;
        }}
        .ddr-related {{
            background-color: #fff3cd !important;
        }}
        .high-confidence {{
            background-color: #f8d7da !important;
        }}
        .tag {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            margin: 2px;
        }}
        .tag-ddr {{
            background-color: #dc3545;
            color: white;
        }}
        .tag-non-ddr {{
            background-color: #28a745;
            color: white;
        }}
        pre {{
            background-color: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p>记录数量: {len(data)}</p>
    </div>
"""
        
        if data and headers:
            html_content += "    <table>\n        <thead>\n            <tr>\n"
            for header in headers:
                html_content += f"                <th>{header}</th>\n"
            html_content += "            </tr>\n        </thead>\n        <tbody>\n"
            
            for row in data:
                # 确定行样式
                row_class = ""
                if row.get('is_ddr_related'):
                    row_class = "ddr-related"
                if row.get('ddr_confidence', 0) >= 0.8:
                    row_class = "high-confidence"
                
                html_content += f'            <tr class="{row_class}">\n'
                for header in headers:
                    value = row.get(header, "")
                    # 格式化特殊值
                    if header == 'is_ddr_related':
                        tag_class = "tag-ddr" if value else "tag-non-ddr"
                        tag_text = "DDR相关" if value else "非DDR"
                        value = f'<span class="tag {tag_class}">{tag_text}</span>'
                    elif header == 'ddr_confidence':
                        value = f"{float(value):.1%}" if value else "0%"
                    elif isinstance(value, list):
                        value = ", ".join(str(v) for v in value[:5])
                    elif isinstance(value, dict):
                        value = json.dumps(value, ensure_ascii=False)[:100]
                    
                    html_content += f"                <td>{value}</td>\n"
                html_content += "            </tr>\n"
            
            html_content += "        </tbody>\n    </table>\n"
        
        html_content += "</body>\n</html>"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    @staticmethod
    def export_crash_report(
        crashes: List[Dict],
        output_path: Path,
        include_raw_log: bool = False
    ) -> Path:
        """
        导出崩溃分析报告
        
        Args:
            crashes: 崩溃记录列表
            output_path: 输出文件路径
            include_raw_log: 是否包含原始日志
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        
        # 统计信息
        total = len(crashes)
        ddr_count = sum(1 for c in crashes if c.get('is_ddr_related'))
        
        report = {
            "report_info": {
                "title": "内核崩溃分析报告",
                "generated_at": datetime.now().isoformat(),
                "total_crashes": total,
                "ddr_related_crashes": ddr_count,
                "non_ddr_crashes": total - ddr_count,
            },
            "summary": {
                "crash_types": {},
                "ddr_fault_types": {},
            },
            "crashes": []
        }
        
        # 统计崩溃类型
        for crash in crashes:
            crash_type = crash.get('crash_type', 'Unknown')
            report["summary"]["crash_types"][crash_type] = \
                report["summary"]["crash_types"].get(crash_type, 0) + 1
            
            if crash.get('is_ddr_related'):
                analysis = crash.get('analysis_result', {})
                ddr_result = analysis.get('ddr_result', {})
                fault_type = ddr_result.get('fault_type', 'Unknown')
                report["summary"]["ddr_fault_types"][fault_type] = \
                    report["summary"]["ddr_fault_types"].get(fault_type, 0) + 1
        
        # 添加崩溃详情
        for crash in crashes:
            crash_entry = {
                "id": crash.get('id'),
                "crash_type": crash.get('crash_type'),
                "timestamp": crash.get('timestamp'),
                "is_ddr_related": crash.get('is_ddr_related'),
                "ddr_confidence": crash.get('ddr_confidence'),
                "fault_address": crash.get('fault_address'),
                "top_function": crash.get('top_function'),
                "call_trace": crash.get('call_trace'),
            }
            
            if include_raw_log:
                crash_entry["raw_log_snippet"] = crash.get('raw_log_snippet', '')[:2000]
            
            report["crashes"].append(crash_entry)
        
        return ExportUtils.export_to_json(report, output_path)
    
    @staticmethod
    def generate_report_filename(prefix: str, extension: str = "json") -> str:
        """生成带时间戳的报告文件名"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"
    
    @staticmethod
    def export_to_excel(
        data: List[Dict],
        output_path: Path,
        sheet_name: str = "数据"
    ) -> Path:
        """
        导出数据到Excel文件
        
        Args:
            data: 字典列表
            output_path: 输出文件路径
            sheet_name: 工作表名称
            
        Returns:
            输出文件路径
        """
        try:
            import pandas as pd
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            df = pd.DataFrame(data)
            df.to_excel(output_path, sheet_name=sheet_name, index=False)
            
            return output_path
        except ImportError:
            # 如果没有pandas，使用openpyxl
            from openpyxl import Workbook
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            wb = Workbook()
            ws = wb.active
            ws.title = sheet_name
            
            if data:
                # 写入标题
                headers = list(data[0].keys())
                ws.append(headers)
                
                # 写入数据
                for row in data:
                    values = []
                    for header in headers:
                        value = row.get(header, "")
                        if isinstance(value, (list, dict)):
                            value = json.dumps(value, ensure_ascii=False)
                        values.append(value)
                    ws.append(values)
            
            wb.save(output_path)
            return output_path

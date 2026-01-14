"""
PDF解析模块 - 用于从PDF文件中提取文本内容
"""

import os
import logging
from typing import Optional, Dict, List
from pypdf import PdfReader
from pdfplumber import PDF as PlumberPDF

logger = logging.getLogger("odi_extractor")


class PDFParser:
    """PDF解析器类"""

    def __init__(self, use_pdfplumber: bool = True):
        """
        初始化PDF解析器

        Args:
            use_pdfplumber: 是否使用pdfplumber库（默认True，更精确但稍慢）
        """
        self.use_pdfplumber = use_pdfplumber

    def extract_text(self, file_path: str) -> Optional[str]:
        """
        从PDF文件中提取文本内容

        Args:
            file_path: PDF文件路径

        Returns:
            提取的文本内容，失败返回None
        """
        try:
            if self.use_pdfplumber:
                return self._extract_with_pdfplumber(file_path)
            else:
                return self._extract_with_pypdf(file_path)
        except Exception as e:
            logger.error(f"解析PDF文件失败: {file_path}, 错误: {e}")
            return None

    def _extract_with_pypdf(self, file_path: str) -> str:
        """
        使用PyPDF提取文本

        Args:
            file_path: PDF文件路径

        Returns:
            提取的文本内容
        """
        text = []
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)

            for page_num in range(num_pages):
                page = reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)

        return "\n".join(text)

    def _extract_with_pdfplumber(self, file_path: str) -> str:
        """
        使用pdfplumber提取文本（更精确）

        Args:
            file_path: PDF文件路径

        Returns:
            提取的文本内容
        """
        text = []
        with open(file_path, 'rb') as file:
            pdf = PlumberPDF(file)

            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)

            pdf.close()

        return "\n".join(text)

    def extract_tables(self, file_path: str) -> List[List[List[str]]]:
        """
        从PDF文件中提取表格

        Args:
            file_path: PDF文件路径

        Returns:
            表格列表（每个表格是二维列表）
        """
        try:
            tables = []
            with open(file_path, 'rb') as file:
                pdf = PlumberPDF(file)

                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

                pdf.close()

            return tables
        except Exception as e:
            logger.error(f"提取表格失败: {file_path}, 错误: {e}")
            return []

    def parse_pdf(self, file_path: str) -> Dict[str, str]:
        """
        解析PDF文件，返回结构化信息

        Args:
            file_path: PDF文件路径

        Returns:
            包含文本内容和元信息的字典
        """
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return {}

        result = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "text_content": "",
            "tables": [],
            "num_pages": 0,
            "success": False,
            "error": None
        }

        try:
            # 获取页数
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                result["num_pages"] = len(reader.pages)

            # 提取文本
            text_content = self.extract_text(file_path)
            if text_content:
                result["text_content"] = text_content
                result["success"] = True
            else:
                result["error"] = "未能提取到文本内容"

            # 提取表格
            tables = self.extract_tables(file_path)
            result["tables"] = tables

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"解析PDF失败: {file_path}, 错误: {e}")

        return result

    def batch_parse(self, file_paths: List[str]) -> List[Dict[str, str]]:
        """
        批量解析PDF文件

        Args:
            file_paths: PDF文件路径列表

        Returns:
            解析结果列表
        """
        results = []
        total = len(file_paths)

        for i, file_path in enumerate(file_paths, 1):
            logger.info(f"正在解析 [{i}/{total}]: {os.path.basename(file_path)}")
            result = self.parse_pdf(file_path)
            results.append(result)

        return results


def get_pdf_files(directory: str) -> List[str]:
    """
    获取目录下所有PDF文件路径

    Args:
        directory: 目录路径

    Returns:
        PDF文件路径列表
    """
    pdf_files = []

    if not os.path.exists(directory):
        logger.warning(f"目录不存在: {directory}")
        return pdf_files

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))

    logger.info(f"在目录 {directory} 中找到 {len(pdf_files)} 个PDF文件")
    return pdf_files

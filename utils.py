"""
工具函数模块
"""

import re
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# 配置日志
def setup_logger(log_dir: str = "./logs", log_level: str = "INFO") -> logging.Logger:
    """
    设置日志记录器

    Args:
        log_dir: 日志目录
        log_level: 日志级别

    Returns:
        配置好的日志记录器
    """
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("odi_extractor")
    logger.setLevel(getattr(logging, log_level))

    # 文件处理器
    log_file = os.path.join(log_dir, f"odi_extractor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def parse_filename(filename: str) -> Dict[str, Optional[str]]:
    """
    解析PDF文件名，提取股票代码、公司名、公告日期

    Args:
        filename: PDF文件名

    Returns:
        包含股票代码、公司名、公告日期的字典
    """
    result = {
        "stock_code": None,
        "company_name": None,
        "announce_date": None
    }

    # 提取股票代码（6位数字开头）
    code_match = re.search(r'^(\d{6})', filename)
    if code_match:
        result["stock_code"] = code_match.group(1)

    # 提取公司名（股票代码后面到日期之间的部分）
    if result["stock_code"]:
        # 去掉股票代码，找到日期之前的部分
        remaining = filename.replace(result["stock_code"], "", 1).strip()
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', remaining)
        if date_match:
            result["company_name"] = remaining.split(date_match.group())[0].strip()

    # 提取公告日期
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{4}年\d{2}月\d{2}日)'
    ]

    for pattern in date_patterns:
        date_match = re.search(pattern, filename)
        if date_match:
            date_str = date_match.group(1)
            # 标准化日期格式
            if "年" in date_str:
                date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")
            result["announce_date"] = date_str
            break

    return result


def extract_amount(text: str) -> Optional[str]:
    """
    从文本中提取金额信息

    Args:
        text: 待提取的文本

    Returns:
        提取的金额字符串，如 "7,319万元" 或 "1.25亿美元" 或 "1250万美元"
    """
    # 匹配金额模式：数字 + （可能含逗号）+ 货币单位
    # 支持格式：
    # - 7,319万元
    # - 1.25亿美元
    # - 1250万美元
    # - $1,250,000
    # - €5,000,000
    patterns = [
        # 数字 + 亿美元/欧元/英镑等
        r'[\d,]+\.?[\d]*\s*亿\s*(?:美元|USD|欧元|英镑|EUR|GBP)',
        # 数字 + 万美元
        r'[\d,]+\.?[\d]*\s*万\s*(?:美元|USD)',
        # 数字 + 亿元
        r'[\d,]+\.?[\d]*\s*亿\s*(?:元|人民币)',
        # 数字 + 万元
        r'[\d,]+\.?[\d]*\s*(?:万元|元)',
        # 数字 + 百万/千
        r'[\d,]+\.?[\d]*\s*(?:百万|千)\s*(?:美元|欧元|英镑|港币|日元)',
        # $ + 数字（美元格式）
        r'\$[\d,]+\.?[\d]*',
        # € + 数字（欧元格式）
        r'€[\d,]+\.?[\d]*',
        # £ + 数字（英镑格式）
        r'£[\d,]+\.?[\d]*',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches[0]

    return None
def extract_percentage(text: str) -> Optional[str]:
    """
    从文本中提取百分比

    Args:
        text: 待提取的文本

    Returns:
        提取的百分比字符串，如 "100%"
    """
    patterns = [
        r'\d+(?:\.\d+)?%',
        r'\d+(?:\.\d+)?\s*%',
        r'\d+(?:\.\d+)?\s*[\u4e00-\u9fa5]*股权',  # 如 "100%股权"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()

    return None


def clean_text(text: str) -> str:
    """
    清理文本：去除多余空格、换行等

    Args:
        text: 待清理的文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 去除多余空格
    text = re.sub(r'\s+', ' ', text)
    # 去除首尾空格
    text = text.strip()

    return text


def contains_any_keyword(text: str, keywords: List[str]) -> bool:
    """
    检查文本是否包含任一关键词

    Args:
        text: 待检查的文本
        keywords: 关键词列表

    Returns:
        是否包含任一关键词
    """
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return True
    return False


def extract_sentences_with_keyword(text: str, keyword: str, context_chars: int = 50) -> List[str]:
    """
    提取包含关键词的句子及其上下文

    Args:
        text: 待提取的文本
        keyword: 关键词
        context_chars: 上下文字符数

    Returns:
        包含关键词的句子列表
    """
    results = []
    sentences = re.split(r'[。；；!！?？\n]', text)

    for sentence in sentences:
        if keyword in sentence:
            results.append(sentence.strip())

    return results


def format_amount(amount_str: str) -> str:
    """
    格式化金额字符串

    Args:
        amount_str: 原始金额字符串

    Returns:
        格式化后的金额字符串
    """
    if not amount_str:
        return ""

    # 去除多余空格
    amount_str = amount_str.strip()

    # 检查是否已经包含单位
    if any(unit in amount_str for unit in ["万", "亿", "元", "美元", "欧元", "英镑", "港币", "日元"]):
        return amount_str

    return amount_str


def is_valid_pdf(file_path: str) -> bool:
    """
    检查文件是否为有效的PDF文件

    Args:
        file_path: 文件路径

    Returns:
        是否为有效PDF
    """
    if not os.path.exists(file_path):
        return False

    # 检查文件扩展名
    _, ext = os.path.splitext(file_path)
    return ext.lower() in [".pdf"]


def create_output_directories(output_dir: str) -> None:
    """
    创建输出目录

    Args:
        output_dir: 输出目录路径
    """
    os.makedirs(output_dir, exist_ok=True)


def normalize_company_name(name: str) -> str:
    """
    标准化公司名称

    Args:
        name: 公司名称

    Returns:
        标准化后的公司名称
    """
    if not name:
        return ""

    # 去除后缀
    suffixes = ["股份有限公司", "有限公司", "集团", "公司", "股份"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    return name.strip()


def find_country_in_text(text: str, countries: List[str]) -> Optional[str]:
    """
    在文本中查找国家/地区名称

    Args:
        text: 待查找的文本
        countries: 国家/地区列表

    Returns:
        找到的国家/地区名称
    """
    # 优先匹配较长的国家名（如"印度尼西亚"而不是"印度"）
    # 按长度降序排序，优先匹配完整国家名
    countries_sorted = sorted(countries, key=len, reverse=True)

    for country in countries_sorted:
        if country in text:
            return country

    return None


def extract_transaction_type(text: str, transaction_types: Dict[str, List[str]]) -> str:
    """
    从文本中提取交易类型

    Args:
        text: 待提取的文本
        transaction_types: 交易类型及其关键词的字典

    Returns:
        交易类型
    """
    for trans_type, keywords in transaction_types.items():
        for keyword in keywords:
            if keyword in text:
                return trans_type

    return "其他"

"""
ODI交易信息提取系统 - 主程序
用于从PDF公告文件中提取境外投资交易信息并生成Excel表格
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_parser import PDFParser, get_pdf_files
from odi_classifier import ODIClassifier
from rule_extractor import RuleExtractor
from excel_exporter import ExcelExporter
from utils import setup_logger, create_output_directories
import config

try:
    from llm_extractor import ZhipuGLM4Extractor, HybridExtractor
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


class ODIExtractor:
    """ODI交易信息提取器"""

    def __init__(self, pdf_dir: str = None, output_dir: str = None):
        """
        初始化提取器

        Args:
            pdf_dir: PDF文件目录（默认为配置中的PDF_DIR）
            output_dir: 输出目录（默认为配置中的OUTPUT_DIR）
        """
        # 使用传入的目录或配置中的默认目录
        self.pdf_dir = pdf_dir or config.PDF_DIR
        self.output_dir = output_dir or config.OUTPUT_DIR

        # 创建输出目录
        create_output_directories(self.output_dir)

        # 设置日志
        self.logger = setup_logger(config.LOG_DIR, config.LOG_LEVEL)

        # 初始化各模块
        self.pdf_parser = PDFParser(use_pdfplumber=True)
        self.classifier = ODIClassifier(config)
        self.rule_extractor = RuleExtractor(config)

        # 初始化LLM提取器（如果配置启用且依赖可用）
        self.llm_extractor = None
        self.hybrid_extractor = None
        if LLM_AVAILABLE and config.USE_LLM_EXTRACTION:
            try:
                self.llm_extractor = ZhipuGLM4Extractor(config)
                self.hybrid_extractor = HybridExtractor(
                    config,
                    self.llm_extractor,
                    self.rule_extractor
                )
                self.logger.info("LLM提取器初始化成功")
            except Exception as e:
                self.logger.warning(f"LLM提取器初始化失败，将使用规则提取: {e}")

        # 根据配置选择提取器
        if self.hybrid_extractor:
            self.extractor = self.hybrid_extractor
        else:
            self.extractor = self.rule_extractor
            self.logger.info("使用规则提取模式")

        self.exporter = ExcelExporter(self.output_dir, config.EXCEL_FILE)

    def run(self, pdf_dir: str = None):
        """
        运行提取流程

        Args:
            pdf_dir: PDF文件目录（如果提供则覆盖初始化时的设置）
        """
        start_time = datetime.now()
        self.logger.info("=" * 60)
        self.logger.info("ODI交易信息提取系统启动")
        self.logger.info("=" * 60)

        # 使用传入的目录或默认目录
        pdf_dir = pdf_dir or self.pdf_dir

        # 步骤1: 扫描PDF文件
        self.logger.info(f"步骤1: 扫描PDF文件 - {pdf_dir}")
        pdf_files = get_pdf_files(pdf_dir)

        if not pdf_files:
            self.logger.warning("未找到任何PDF文件")
            return None

        self.logger.info(f"找到 {len(pdf_files)} 个PDF文件")

        # 步骤2: 解析PDF
        self.logger.info("步骤2: 解析PDF文件")
        pdf_data_list = self.pdf_parser.batch_parse(pdf_files)
        self.logger.info(f"成功解析 {sum(1 for d in pdf_data_list if d.get('success'))} 个文件")

        # 步骤3: 分类
        self.logger.info("步骤3: 分类识别境外投资交易")
        classification_results = self.classifier.batch_classify(pdf_data_list)

        # 步骤4: 提取信息
        self.logger.info("步骤4: 提取交易信息")
        odi_results = []
        excluded_results = []

        for pdf_data, classification in zip(pdf_data_list, classification_results):
            if classification.get("is_odi"):
                # 提取境外投资交易信息
                extracted_info = self.extractor.extract(pdf_data, classification)
                # 将分类信息也添加到结果中
                extracted_info["风险点"] = {}
                odi_results.append(extracted_info)
            else:
                # 记录排除的文件
                excluded_results.append({
                    "file_name": pdf_data.get("file_name", ""),
                    "reason": classification.get("reason", ""),
                    "exclusion_reason": classification.get("exclusion_reason", ""),
                })

        self.logger.info(f"提取完成：境外投资 {len(odi_results)} 个，排除 {len(excluded_results)} 个")

        # 输出LLM统计信息（如果使用LLM）
        if self.hybrid_extractor:
            stats = self.hybrid_extractor.get_stats()
            self.logger.info(f"LLM提取统计: {stats}")

        # 步骤5: 导出Excel
        self.logger.info("步骤5: 导出Excel表格")
        excel_path = self.exporter.export(odi_results, excluded_results)
        self.logger.info(f"Excel文件已生成: {excel_path}")

        # 汇总统计
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.logger.info("=" * 60)
        self.logger.info("处理完成")
        self.logger.info(f"总耗时: {duration:.2f} 秒")
        self.logger.info(f"境外投资交易数: {len(odi_results)}")
        self.logger.info(f"排除文件数: {len(excluded_results)}")
        self.logger.info(f"输出文件: {excel_path}")
        self.logger.info("=" * 60)

        return {
            "odi_count": len(odi_results),
            "excluded_count": len(excluded_results),
            "excel_path": excel_path,
            "duration": duration
        }


def main():
    """主函数 - 命令行入口"""
    parser = argparse.ArgumentParser(
        description="ODI交易信息提取系统 - 从PDF公告文件中提取境外投资交易信息"
    )

    parser.add_argument(
        "-d", "--pdf-dir",
        type=str,
        default=None,
        help=f"PDF文件目录（默认: {config.PDF_DIR}）"
    )

    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help=f"输出目录（默认: {config.OUTPUT_DIR}）"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        config.LOG_LEVEL = "DEBUG"

    # 创建提取器并运行
    extractor = ODIExtractor(
        pdf_dir=args.pdf_dir,
        output_dir=args.output_dir
    )

    result = extractor.run()

    if result:
        print(f"\n处理完成！")
        print(f"境外投资交易数: {result['odi_count']}")
        print(f"排除文件数: {result['excluded_count']}")
        print(f"输出文件: {result['excel_path']}")
        print(f"总耗时: {result['duration']:.2f} 秒")


if __name__ == "__main__":
    main()

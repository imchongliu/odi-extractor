"""
Excel导出模块 - 将提取结果导出为Excel表格
"""

import pandas as pd
import os
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger("odi_extractor")


class ExcelExporter:
    """Excel导出器"""

    def __init__(self, output_dir: str, filename: str = "ODI交易信息汇总.xlsx"):
        """
        初始化导出器

        Args:
            output_dir: 输出目录
            filename: Excel文件名
        """
        self.output_dir = output_dir
        self.filename = filename

    def export(self, odi_results: List[Dict], excluded_results: List[Dict]) -> str:
        """
        导出Excel表格

        Args:
            odi_results: 境外投资交易结果列表
            excluded_results: 被排除的结果列表

        Returns:
            导出的Excel文件路径
        """
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, self.filename)

        logger.info(f"开始导出Excel文件: {output_path}")

        # 使用ExcelWriter
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: 全部交易
            self._write_all_transactions(writer, odi_results)

            # Sheet 2: 基本信息
            self._write_basic_info(writer, odi_results)

            # Sheet 3: 交易结构
            self._write_structure(writer, odi_results)

            # Sheet 4: 合规审批
            self._write_approvals(writer, odi_results)

            # Sheet 5: 风险点
            self._write_risks(writer, odi_results)

            # Sheet 6: 排除文件
            self._write_excluded(writer, excluded_results)

            # Sheet 7: 统计摘要
            self._write_summary(writer, odi_results, excluded_results)

        logger.info(f"Excel文件导出完成: {output_path}")
        return output_path

    def _write_all_transactions(self, writer, odi_results: List[Dict]):
        """写入全部交易Sheet"""
        rows = []

        for result in odi_results:
            basic_info = result.get("基本信息", {})
            structure = result.get("交易结构", {})
            approvals = result.get("合规审批", {})

            row = {
                "文件名称": basic_info.get("文件名称", ""),
                "公告日期": basic_info.get("公告日期", ""),
                "境内公告主体": f"{basic_info.get('股票代码', '')} {basic_info.get('公司名称', '')}".strip(),
                "标的公司/项目名称": basic_info.get("标的公司/项目名称", ""),
                "标的公司注册地": basic_info.get("标的公司注册地", ""),
                "业务范围": basic_info.get("业务范围", ""),
                "交易金额/投资额": basic_info.get("交易金额/投资额", ""),
                "交易类型": basic_info.get("交易类型", ""),
                "股权比例": basic_info.get("股权比例", ""),
                "交易对手方": basic_info.get("交易对手方", ""),
                "当前进展阶段": basic_info.get("当前进展阶段", ""),
                "投资主体": structure.get("投资主体", ""),
                "资金来源": structure.get("资金来源", ""),
                "支付方式": structure.get("支付方式", ""),
                "境内审批事项": approvals.get("境内审批事项", ""),
                "境外审批事项": approvals.get("境外审批事项", ""),
                "审批进度": approvals.get("审批进度", ""),
                "特殊许可": approvals.get("特殊许可", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="全部交易", index=False)

        # 设置列宽
        worksheet = writer.sheets["全部交易"]
        self._set_column_widths(worksheet, df)

    def _write_basic_info(self, writer, odi_results: List[Dict]):
        """写入基本信息Sheet"""
        rows = []

        for result in odi_results:
            basic_info = result.get("基本信息", {})
            row = {
                "股票代码": basic_info.get("股票代码", ""),
                "公司名称": basic_info.get("公司名称", ""),
                "公告日期": basic_info.get("公告日期", ""),
                "文件名称": basic_info.get("文件名称", ""),
                "标的公司/项目名称": basic_info.get("标的公司/项目名称", ""),
                "标的公司注册地": basic_info.get("标的公司注册地", ""),
                "业务范围": basic_info.get("业务范围", ""),
                "交易金额/投资额": basic_info.get("交易金额/投资额", ""),
                "交易类型": basic_info.get("交易类型", ""),
                "股权比例": basic_info.get("股权比例", ""),
                "交易对手方": basic_info.get("交易对手方", ""),
                "当前进展阶段": basic_info.get("当前进展阶段", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="基本信息", index=False)

        worksheet = writer.sheets["基本信息"]
        self._set_column_widths(worksheet, df)

    def _write_structure(self, writer, odi_results: List[Dict]):
        """写入交易结构Sheet"""
        rows = []

        for result in odi_results:
            basic_info = result.get("基本信息", {})
            structure = result.get("交易结构", {})

            row = {
                "文件名称": basic_info.get("文件名称", ""),
                "境内公告主体": f"{basic_info.get('股票代码', '')} {basic_info.get('公司名称', '')}".strip(),
                "标的公司/项目名称": basic_info.get("标的公司/项目名称", ""),
                "投资主体": structure.get("投资主体", ""),
                "SPV结构": structure.get("SPV结构", ""),
                "资金来源": structure.get("资金来源", ""),
                "支付方式": structure.get("支付方式", ""),
                "对赌/业绩承诺": structure.get("对赌/业绩承诺", ""),
                "交易架构": structure.get("交易架构", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="交易结构", index=False)

        worksheet = writer.sheets["交易结构"]
        self._set_column_widths(worksheet, df)

    def _write_approvals(self, writer, odi_results: List[Dict]):
        """写入合规审批Sheet"""
        rows = []

        for result in odi_results:
            basic_info = result.get("基本信息", {})
            approvals = result.get("合规审批", {})

            row = {
                "文件名称": basic_info.get("文件名称", ""),
                "境内公告主体": f"{basic_info.get('股票代码', '')} {basic_info.get('公司名称', '')}".strip(),
                "标的公司/项目名称": basic_info.get("标的公司/项目名称", ""),
                "境内审批事项": approvals.get("境内审批事项", ""),
                "境外审批事项": approvals.get("境外审批事项", ""),
                "审批进度": approvals.get("审批进度", ""),
                "审批条件": approvals.get("审批条件", ""),
                "交割条件": approvals.get("交割条件", ""),
                "特殊许可": approvals.get("特殊许可", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="合规审批", index=False)

        worksheet = writer.sheets["合规审批"]
        self._set_column_widths(worksheet, df)

    def _write_risks(self, writer, odi_results: List[Dict]):
        """写入风险点Sheet（暂时为空，可用于后续LLM分析）"""
        rows = []

        for result in odi_results:
            basic_info = result.get("基本信息", {})
            risks = result.get("风险点", {})

            row = {
                "文件名称": basic_info.get("文件名称", ""),
                "境内公告主体": f"{basic_info.get('股票代码', '')} {basic_info.get('公司名称', '')}".strip(),
                "标的公司/项目名称": basic_info.get("标的公司/项目名称", ""),
                "法律风险": risks.get("法律风险", "待分析"),
                "政策风险": risks.get("政策风险", "待分析"),
                "财务风险": risks.get("财务风险", "待分析"),
                "经营风险": risks.get("经营风险", "待分析"),
                "尽调问题": risks.get("尽调问题", "待分析"),
                "其他风险": risks.get("其他风险", "待分析"),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="风险点", index=False)

        worksheet = writer.sheets["风险点"]
        self._set_column_widths(worksheet, df)

    def _write_excluded(self, writer, excluded_results: List[Dict]):
        """写入排除文件Sheet"""
        rows = []

        for result in excluded_results:
            row = {
                "文件名称": result.get("file_name", ""),
                "排除原因": result.get("exclusion_reason", ""),
                "备注": result.get("reason", ""),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="排除文件", index=False)

        worksheet = writer.sheets["排除文件"]
        self._set_column_widths(worksheet, df)

    def _write_summary(self, writer, odi_results: List[Dict], excluded_results: List[Dict]):
        """写入统计摘要Sheet"""
        summary_data = []

        # 总体统计
        total_files = len(odi_results) + len(excluded_results)
        odi_count = len(odi_results)
        excluded_count = len(excluded_results)
        domestic_count = sum(1 for r in excluded_results if "境内" in r.get("reason", ""))

        summary_data.extend([
            ["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["总体统计", ""],
            ["处理文件总数", total_files],
            ["境外投资交易数", odi_count],
            ["排除文件数", excluded_count],
            ["其中：境内交易", domestic_count],
            ["", ""],
        ])

        # 交易类型统计
        transaction_types = {}
        for result in odi_results:
            basic_info = result.get("基本信息", {})
            trans_type = basic_info.get("交易类型", "其他")
            transaction_types[trans_type] = transaction_types.get(trans_type, 0) + 1

        summary_data.append(["交易类型统计", ""])
        for trans_type, count in transaction_types.items():
            summary_data.append([trans_type, count])

        summary_data.extend([
            ["", ""],
            ["国家/地区统计", ""],
        ])

        # 国家/地区统计
        countries = {}
        for result in odi_results:
            basic_info = result.get("基本信息", {})
            country = basic_info.get("标的公司注册地", "未明确")
            countries[country] = countries.get(country, 0) + 1

        for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True):
            summary_data.append([country, count])

        df = pd.DataFrame(summary_data, columns=["项目", "数量/说明"])
        df.to_excel(writer, sheet_name="统计摘要", index=False)

        worksheet = writer.sheets["统计摘要"]
        self._set_column_widths(worksheet, df)

    def _set_column_widths(self, worksheet, df):
        """设置列宽"""
        for idx, col in enumerate(df.columns, 1):
            # 计算该列最大宽度
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            )
            # 设置列宽（最小10，最大50）
            adjusted_width = min(max(10, max_length + 2), 50)
            worksheet.column_dimensions[chr(64 + idx)].width = adjusted_width

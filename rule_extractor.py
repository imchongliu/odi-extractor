"""
规则提取模块 - 使用规则和正则表达式提取交易信息
"""

import re
import logging
from typing import Dict, Optional, List
from utils import (
    parse_filename, extract_amount, extract_percentage,
    clean_text, extract_transaction_type, extract_sentences_with_keyword
)

logger = logging.getLogger("odi_extractor")


class RuleExtractor:
    """规则提取器"""

    def __init__(self, config):
        """
        初始化提取器

        Args:
            config: 配置对象
        """
        self.transaction_types = config.TRANSACTION_TYPES
        self.approval_keywords = config.APPROVAL_KEYWORDS

    def extract(self, pdf_data: Dict, classification: Dict) -> Dict:
        """
        从PDF数据中提取交易信息

        Args:
            pdf_data: PDF解析数据
            classification: 分类结果

        Returns:
            提取的交易信息字典
        """
        result = {
            "基本信息": {},
            "交易结构": {},
            "合规审批": {},
        }

        text = pdf_data.get("text_content", "")
        file_name = pdf_data.get("file_name", "")

        # 提取基本信息
        result["基本信息"] = self._extract_basic_info(text, file_name, classification)

        # 提取交易结构
        result["交易结构"] = self._extract_structure(text, classification)

        # 提取合规审批
        result["合规审批"] = self._extract_approvals(text)

        return result

    def _extract_basic_info(self, text: str, file_name: str, classification: Dict) -> Dict:
        """
        提取基本信息

        Args:
            text: 文本内容
            file_name: 文件名
            classification: 分类结果

        Returns:
            基本信息字典
        """
        info = {}

        # 从文件名解析
        filename_info = parse_filename(file_name)
        info["股票代码"] = filename_info.get("stock_code", "")
        info["公司名称"] = filename_info.get("company_name", "")
        info["公告日期"] = filename_info.get("announce_date", "")

        # 文件名
        info["文件名称"] = file_name

        # 目标国家/地区
        info["标的公司注册地"] = classification.get("target_country", "")

        # 标的公司名称
        info["标的公司/项目名称"] = self._extract_target_company(text, classification)

        # 交易类型
        info["交易类型"] = self._extract_transaction_type(text)

        # 交易金额
        info["交易金额/投资额"] = self._extract_amount(text)

        # 股权比例
        info["股权比例"] = self._extract_equity_ratio(text)

        # 交易对手方
        info["交易对手方"] = self._extract_counterparty(text)

        # 当前进展
        info["当前进展阶段"] = self._extract_progress(text)

        # 业务范围
        info["业务范围"] = self._extract_business_scope(text)

        return info

    def _extract_target_company(self, text: str, classification: Dict) -> str:
        """
        提取标的公司名称

        Args:
            text: 文本内容
            classification: 分类结果

        Returns:
            标的公司名称
        """
        target_country = classification.get("target_country", "")
        if not target_country:
            return ""

        # 查找包含目标国家/地区的公司名模式
        patterns = [
            rf'[^。\n，]*{target_country}[^。\n，]*(?:公司|有限公司|股份|Corp|Inc|Ltd|GmbH)',
            rf'(?:收购|投资|设立|成立).{0,30}([^\s]{2,30}(?:公司|有限公司|股份|Corp|Inc|Ltd|GmbH))',
            rf'标的公司[:：\s]*([^\s]{2,50})',
            rf'目标公司[:：\s]*([^\s]{2,50})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 返回第一个匹配项
                return clean_text(matches[0])

        # 如果没有找到，尝试从关键词周围提取
        keywords = ["收购", "投资", "设立", "成立", "并购"]
        for keyword in keywords:
            sentences = extract_sentences_with_keyword(text, keyword, context_chars=100)
            for sentence in sentences:
                if target_country in sentence:
                    # 提取公司名
                    company_match = re.search(r'([^\s]{2,30}(?:公司|有限公司|股份))', sentence)
                    if company_match:
                        return clean_text(company_match.group(1))

        return ""

    def _extract_transaction_type(self, text: str) -> str:
        """
        提取交易类型

        Args:
            text: 文本内容

        Returns:
            交易类型
        """
        return extract_transaction_type(text, self.transaction_types)

    def _extract_amount(self, text: str) -> str:
        """
        提取交易金额

        Args:
            text: 文本内容

        Returns:
            交易金额字符串
        """
        amount = extract_amount(text)
        return amount if amount else ""

    def _extract_equity_ratio(self, text: str) -> str:
        """
        提取股权比例

        Args:
            text: 文本内容

        Returns:
            股权比例字符串
        """
        # 查找股权比例相关的句子
        keywords = ["股权", "股份", "持股"]
        ratios = []

        for keyword in keywords:
            sentences = extract_sentences_with_keyword(text, keyword, context_chars=50)
            for sentence in sentences:
                # 提取百分比
                percentage = extract_percentage(sentence)
                if percentage:
                    ratios.append(f"{percentage} - {sentence[:50]}")

        return "; ".join(ratios[:3]) if ratios else ""

    def _extract_counterparty(self, text: str) -> str:
        """
        提取交易对手方

        Args:
            text: 文本内容

        Returns:
            交易对手方名称
        """
        # 查找交易对手方相关模式
        patterns = [
            r'交易对手[:：\s]*([^\s]{2,50})',
            r'交易对方[:：\s]*([^\s]{2,50})',
            r'出售方[:：\s]*([^\s]{2,50})',
            r'转让方[:：\s]*([^\s]{2,50})',
            r'合作方[:：\s]*([^\s]{2,50})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return clean_text(match.group(1))

        # 尝试从"与...签署协议"中提取
        sign_pattern = r'与\s*([^\s]{2,30})\s*(?:签署|签订|签订)'
        match = re.search(sign_pattern, text)
        if match:
            return clean_text(match.group(1))

        return ""

    def _extract_progress(self, text: str) -> str:
        """
        提取当前进展阶段

        Args:
            text: 文本内容

        Returns:
            进展阶段描述
        """
        # 进展关键词
        progress_patterns = [
            r'(?:交易|项目|收购|投资).*?(?:已完成|已交割|已实施|已完成交割)',
            r'(?:交易|项目|收购|投资).*?(?:已签署|已签订).*?(?:协议|合同)',
            r'(?:交易|项目|收购|投资).*?(?:正在进行|进行中)',
            r'(?:交易|项目|收购|投资).*?(?:拟|计划|筹划|准备)',
            r'(?:交易|项目|收购|投资).*?(?:已获.*?批准|已通过.*?审议)',
        ]

        for pattern in progress_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 提取相关句子
                for match in matches[:2]:
                    context = extract_sentences_with_keyword(text, match, context_chars=50)
                    if context:
                        return clean_text(context[0])

        # 默认状态判断
        if "拟" in text or "计划" in text:
            return "拟进行/计划中"
        elif "已完成" in text or "已交割" in text:
            return "已完成/已交割"
        elif "已签署" in text or "已签订" in text:
            return "已签署协议"
        elif "批准" in text:
            return "已获得批准"
        else:
            return "未明确"

    def _extract_business_scope(self, text: str) -> str:
        """
        提取业务范围（目标公司的业务范围，排除投资方"我司"的业务）

        Args:
            text: 文本内容

        Returns:
            业务范围描述
        """
        # 查找业务范围相关模式 - 优先使用标的公司相关的描述
        patterns = [
            r'(?:标的公司|目标公司|该标的公司).*?(?:主要从事|主要业务|业务范围)[:：\s]*([^\n]{10,200}?)(?:\.|。|；)',
            r'(?:标的公司|目标公司|被收购方).*?(?:主营业务|经营范围)[:：\s]*([^\n]{10,200}?)(?:\.|。|；)',
            r'(?:主要)?(?:业务范围|经营范围|主营业务)[:：\s]*([^\n]{10,200}?)(?:\.|。|；)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # 检查是否包含"我司"、"本公司"等投资方描述，避免提取投资方的业务范围
                scope_text = clean_text(match.group(1))
                if not any(exclude_word in scope_text for exclude_word in ["我司", "本公司", "公司是", "从事贸易类", "凭证结算"]):
                    return scope_text

        # 从关键词周围提取 - 排除包含"我司"、"本公司"的句子
        keywords = ["业务", "经营", "主营"]
        for keyword in keywords:
            sentences = extract_sentences_with_keyword(text, keyword, context_chars=80)
            for sentence in sentences:
                if len(sentence) > 20:
                    # 排除投资方（我司、本公司）的业务描述
                    # 添加调试日志
                    if "我司" in sentence or "本公司" in sentence:
                        logger.debug(f"排除包含投资方描述的句子: {sentence[:60]}")
                        continue
                    return clean_text(sentence)

        return ""

    def _extract_structure(self, text: str, classification: Dict) -> Dict:
        """
        提取交易结构信息

        Args:
            text: 文本内容
            classification: 分类结果

        Returns:
            交易结构字典
        """
        structure = {}

        # 投资主体
        structure["投资主体"] = self._extract_investment_entity(text)

        # SPV结构
        structure["SPV结构"] = self._extract_spv_structure(text)

        # 资金来源
        structure["资金来源"] = self._extract_funding_source(text)

        # 支付方式
        structure["支付方式"] = self._extract_payment_method(text)

        # 对赌/业绩承诺
        structure["对赌/业绩承诺"] = self._extract_vam(text)

        # 交易架构
        structure["交易架构"] = self._extract_transaction_architecture(text)

        return structure

    def _extract_investment_entity(self, text: str) -> str:
        """提取投资主体"""
        patterns = [
            r'(?:投资主体|投资方).*?[:：]\s*([^\s]{2,50})',
            r'通过\s*([^\s]{2,30}(?:公司|有限公司))\s*(?:进行投资|收购|设立)',
            r'全资子公司\s*([^\s]{2,30})\s*(?:拟投资|拟收购)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return clean_text(match.group(1))

        return ""

    def _extract_spv_structure(self, text: str) -> str:
        """提取SPV结构"""
        spv_keywords = ["SPV", "特殊目的公司", "中间层", "全资孙公司", "控股子公司", "全资子公司"]

        for keyword in spv_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=100)
                if sentences:
                    return clean_text(sentences[0][:80])

        return ""

    def _extract_funding_source(self, text: str) -> str:
        """提取资金来源"""
        patterns = [
            r'资金来源[:：]\s*([^\n。]{5,100})',
            r'使用\s*([^\s]{5,50})\s*(?:进行|用于).*?(?:收购|投资)',
            r'以\s*([^\s]{5,50})\s*(?:支付|投资)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return clean_text(match.group(1))

        # 查找常见资金来源关键词
        funding_keywords = ["自有资金", "募集资金", "银行贷款", "自有及自筹资金", "银行借款"]
        for keyword in funding_keywords:
            if keyword in text:
                return keyword

        return ""

    def _extract_payment_method(self, text: str) -> str:
        """提取支付方式"""
        patterns = [
            r'支付方式[:：]\s*([^\n。]{5,100})',
            r'以\s*([^\s]{5,30})\s*(?:方式)?支付',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return clean_text(match.group(1))

        # 常见支付方式
        if "现金" in text:
            return "现金"
        elif "股权" in text and "置换" in text:
            return "股权置换"

        return ""

    def _extract_vam(self, text: str) -> str:
        """提取对赌/业绩承诺"""
        vam_keywords = ["对赌", "业绩承诺", "业绩补偿", "盈利预测", "净利润承诺"]

        for keyword in vam_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=100)
                if sentences:
                    return clean_text(sentences[0][:100])

        return ""

    def _extract_transaction_architecture(self, text: str) -> str:
        """提取交易架构描述"""
        architecture_keywords = ["交易架构", "投资路径", "股权结构", "投资结构"]

        for keyword in architecture_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=150)
                if sentences:
                    return clean_text(sentences[0][:150])

        # 查找通过...子公司...投资...的模式
        pattern = r'通过\s*([^\n。]{30,150})\s*(?:进行|实施|收购)'
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))

        return ""

    def _extract_approvals(self, text: str) -> Dict:
        """
        提取合规审批信息

        Args:
            text: 文本内容

        Returns:
            审批信息字典
        """
        approvals = {}

        # 境内审批事项
        approvals["境内审批事项"] = self._extract_domestic_approvals(text)

        # 境外审批事项
        approvals["境外审批事项"] = self._extract_foreign_approvals(text)

        # 审批进度
        approvals["审批进度"] = self._extract_approval_progress(text)

        # 审批条件
        approvals["审批条件"] = self._extract_approval_conditions(text)

        # 交割条件
        approvals["交割条件"] = self._extract_closing_conditions(text)

        # 特殊许可
        approvals["特殊许可"] = self._extract_special_licenses(text)

        return approvals

    def _extract_domestic_approvals(self, text: str) -> str:
        """提取境内审批事项"""
        domestic_approvals = []

        for approval_name, keywords in self.approval_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    # 提取相关句子
                    sentences = extract_sentences_with_keyword(text, keyword, context_chars=80)
                    for sentence in sentences[:2]:
                        if approval_name not in domestic_approvals:
                            domestic_approvals.append(approval_name)
                    break

        return "; ".join(domestic_approvals) if domestic_approvals else ""

    def _extract_foreign_approvals(self, text: str) -> str:
        """提取境外审批事项"""
        foreign_keywords = [
            "反垄断审查", "经营者集中", "外商投资审查", "国家安全审查",
            "境外监管", "外国政府", "东道国审批"
        ]

        approvals = []
        for keyword in foreign_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=80)
                if sentences:
                    approvals.append(clean_text(sentences[0][:60]))

        return "; ".join(approvals) if approvals else ""

    def _extract_approval_progress(self, text: str) -> str:
        """提取审批进度"""
        progress_keywords = ["已获", "已通过", "尚需", "待", "正在办理", "备案", "批准"]

        for keyword in progress_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=60)
                if sentences:
                    return clean_text(sentences[0][:80])

        return ""

    def _extract_approval_conditions(self, text: str) -> str:
        """提取审批条件"""
        condition_keywords = ["先决条件", "前提条件", "审批条件", "所需条件"]

        for keyword in condition_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=100)
                if sentences:
                    return clean_text(sentences[0][:120])

        return ""

    def _extract_closing_conditions(self, text: str) -> str:
        """提取交割条件"""
        closing_keywords = ["交割条件", "完成条件", "交割前提", "完成前提"]

        for keyword in closing_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=100)
                if sentences:
                    return clean_text(sentences[0][:120])

        return ""

    def _extract_special_licenses(self, text: str) -> str:
        """提取特殊许可"""
        license_keywords = ["牌照", "资质", "许可证", "特许经营", "行业许可"]

        licenses = []
        for keyword in license_keywords:
            if keyword in text:
                sentences = extract_sentences_with_keyword(text, keyword, context_chars=60)
                for sentence in sentences[:2]:
                    if len(sentence) > 20:
                        licenses.append(clean_text(sentence[:80]))

        return "; ".join(licenses) if licenses else ""

"""
境外投资识别分类器 - 判断PDF公告是否属于境外投资交易
"""

import re
import logging
from typing import Dict, Tuple, Optional
from utils import contains_any_keyword, find_country_in_text, extract_sentences_with_keyword

logger = logging.getLogger("odi_extractor")


class ODIClassifier:
    """境外投资识别分类器"""

    def __init__(self, config):
        """
        初始化分类器

        Args:
            config: 配置对象
        """
        self.countries = config.COUNTRIES_FLAT
        self.exclude_keywords = config.EXCLUDE_KEYWORDS
        self.domestic_keywords = config.DOMESTIC_KEYWORDS
        self.transaction_types = config.TRANSACTION_TYPES

    def classify(self, pdf_data: Dict[str, str]) -> Dict:
        """
        判断PDF是否为境外投资交易

        Args:
            pdf_data: PDF解析数据（包含text_content, file_name等）

        Returns:
            分类结果字典：
            {
                "is_odi": True/False,  # 是否为境外投资
                "reason": "原因说明",
                "target_country": "目标国家/地区",
                "exclusion_reason": "被排除的原因"（如果被排除）
            }
        """
        result = {
            "is_odi": False,
            "reason": "",
            "target_country": None,
            "exclusion_reason": None
        }

        text = pdf_data.get("text_content", "")
        file_name = pdf_data.get("file_name", "")

        if not text:
            result["reason"] = "未能提取到文本内容"
            return result

        # 第一步：检查排除标准
        exclusion_reason = self._check_exclusion(text, file_name)
        if exclusion_reason:
            result["is_odi"] = False
            result["exclusion_reason"] = exclusion_reason
            result["reason"] = f"被排除：{exclusion_reason}"
            return result

        # 第二步：检查是否有境外国家/地区
        target_country = self._find_target_country(text, file_name)

        # 特殊处理：如果文件名包含"海外"、"对外投资"、"境外"等关键词
        # 即使没有找到具体国家，也尝试识别
        overseas_in_filename = any(keyword in file_name for keyword in ["海外", "对外投资", "国外", "境外"])
        if overseas_in_filename and not target_country:
            logger.debug(f"文件名包含境外关键词但未找到具体国家: {file_name}")
            # 假定这些文件是境外投资，不排除
            result["is_odi"] = True
            result["reason"] = f"确认为境外投资交易（文件名包含境外/海外标识）"
            result["target_country"] = "未明确（需人工核对）"
            return result

        if not target_country:
            result["is_odi"] = False
            result["reason"] = "未发现境外国家/地区标识"
            return result

        result["target_country"] = target_country

        # 第三步：检查是否为投资类交易
        is_investment = self._check_investment_transaction(text, file_name)

        if not is_investment:
            result["is_odi"] = False
            result["reason"] = f"发现境外标识但非投资类交易（国家：{target_country}）"
            return result

        # 通过所有检查，确认为境外投资交易
        result["is_odi"] = True
        result["reason"] = f"确认为境外投资交易（目标国家/地区：{target_country}）"
        return result

    def _check_exclusion(self, text: str, file_name: str) -> Optional[str]:
        """
        检查是否应该被排除

        Args:
            text: 文本内容
            file_name: 文件名

        Returns:
            排除原因，如果不排除则返回None
        """
        # 先检查投资关键词，如果是明确的境外投资交易，直接不排除
        investment_patterns = [
            r'境外.{0,20}投资',
            r'境外.{0,20}(?:收购|并购)',
            r'收购.{0,50}(?:境外|海外|美国|德国|阿根廷|越南|南非)',
            r'对外投资.{0,20}(?:境外|海外)',
            r'境外.{0,20}放款',
            r'放款.{0,20}境外',
            r'境外.{0,20}(?:合资|合作)',
        ]

        for pattern in investment_patterns:
            if re.search(pattern, text):
                # 检查是否是纯境内交易
                # 如果文本中只提到境内城市，但没有明确的境外投资目的地
                title_area = text.split("\n")[0:100]  # 取前100行作为标题区域
                domestic_cities = ["上海", "北京", "广州", "深圳", "青岛", "天津"]

                # 如果标题提到境内城市，需要进一步判断
                if any(city in title_area for city in domestic_cities):
                    # 检查是否有明确的境外国家/地区
                    target_country = self._find_target_country(text, file_name)
                    # 只排除确实是境内的情况（目标国家是"中国"或"境内"，或没有明确境外国家）
                    clear_foreign_countries = ["美国", "德国", "法国", "英国", "阿根廷", "越南", "哈萨克斯坦", "南非", "秘鲁", "俄罗斯"]
                    if not target_country or target_country in ["中国", "境内"] or target_country not in clear_foreign_countries:
                        return "境内交易"
                    # 有明确境外国家，不应该被排除
                    return None

                return None  # 有明确的境外投资模式，不应该被排除

        # 检查是否为纯境内交易（基于目标公司名称）
        # 如果目标公司名称包含中国省份/城市，且没有明确的境外国家标识
        chinese_provinces = [
            "浙江", "江苏", "广东", "福建", "山东", "四川", "湖北",
            "上海", "北京", "广州", "深圳", "青岛", "天津", "重庆",
            "河北", "河南", "湖南", "安徽", "江西", "山西", "陕西",
            "内蒙古", "辽宁", "吉林", "黑龙江", "海南", "广西", "云南",
            "贵州", "西藏", "甘肃", "青海", "宁夏", "新疆"
        ]

        # 检查文本中是否包含省份/城市
        for province in chinese_provinces:
            if province in text:
                # 找到省份后，检查是否是目标公司名的一部分
                idx = text.find(province)
                # 获取公司名称所在的上下文（通常是 "收购XX省XX公司"）
                context_start = max(0, idx - 20)
                context_end = min(len(text), idx + len(province) + 40)
                context = text[context_start:context_end]

                # DEBUG: print what's happening
                logger.debug(f'DEBUG: Found province {province} at {idx}')
                logger.debug(f'DEBUG: context={repr(context[:100])}')

                # 检查上下文中的关键词模式
                # 如果是"收购浙江XX公司"，这通常是境内交易
                # 除非同时明确说明是"境外投资"
                if "收购" in context and "公司" in context:
                    logger.debug(f'DEBUG: Has 收购 and 公司 in context')

                    # 检查是否有明确的境外投资指向境外国家
                    # 简化：检查是否在"收购XX公司"附近有明确的境外国家
                    # 获取更大的上下文来检查
                    larger_context = text[max(0, idx - 30):min(len(text), idx + len(province) + 100)]

                    # 检查上下文中是否有明确的境外国家名（不包括印度、印尼等可能误匹配的）
                    explicit_foreign_in_context = any(
                        country in larger_context
                        for country in ["美国", "德国", "法国", "英国", "阿根廷", "越南", "哈萨克斯坦", "南非", "秘鲁", "俄罗斯"]
                    )

                    logger.debug(f'DEBUG: explicit_foreign_in_context={explicit_foreign_in_context}')

                    if not explicit_foreign_in_context:
                        # 上下文中没有明确的境外国家，目标是境内公司，判定为境内交易
                        result = f"境内交易（收购{province}公司）"
                        logger.debug(f'DEBUG: Returning {result}')
                        return result
                    else:
                        logger.debug('DEBUG: Has explicit foreign in context, not excluding')

                logger.debug(f'DEBUG: Continue checking provinces...')

        # 检查排除关键词（原有的排除逻辑）
        for keyword in self.exclude_keywords:
            if keyword in text:
                # 需要进一步判断是否真的是需要排除的情况
                context = extract_sentences_with_keyword(text, keyword, context_chars=100)
                context_str = " ".join(context)

                # 特殊情况处理：药品注册
                if "境外生产药品" in keyword or "境外注册" in keyword:
                    # 检查是否是药品上市注册
                    if "药品" in text and ("注册" in text or "批准" in text):
                        return "仅境外药品注册/上市批准"

                # 运营数据披露
                if "运营数据" in keyword or "运营情况" in keyword or "财务数据" in keyword:
                    if "披露" in text or "公告" in text:
                        return "运营数据/财务数据信息披露"

                # 出口贸易
                if "出口贸易" in keyword or "出口产品" in keyword:
                    if not any(invest_keyword in text for invest_keywords in self.transaction_types.values()
                               for invest_keyword in invest_keywords if invest_keyword in ["投资", "收购", "并购", "设立"]):
                        return "出口贸易业务"

                # 自愿性信息披露
                if "自愿性信息披露" in keyword:
                    return "自愿性信息披露"

        # 检查纯境内交易（后备逻辑）
        # 如果文本中只包含国内城市/省份，没有境外国家，且没有"境外"、"海外"等词
        domestic_only = True
        has_foreign_keywords = False

        foreign_keywords = ["境外", "海外", "国外", "外"]
        for keyword in foreign_keywords:
            if keyword in text:
                has_foreign_keywords = True
                break

        # 如果有"境外"、"海外"等词，但都是负面描述（如"境外业务仅占小部分"）
        if has_foreign_keywords:
            # 检查是否有"仅"、"不涉及"等否定词
            negative_patterns = [r"仅[^\s]*境外", r"不涉及境外", r"无境外", r"境外.*占.*%"]
            for pattern in negative_patterns:
                if re.search(pattern, text):
                    return "非境外投资业务"

        # 如果文件名和标题都是境内城市
        title = text.split("\n")[0:5]  # 取前5行作为标题区域
        title_text = " ".join(title)
        if not has_foreign_keywords and any(city in title_text for city in ["上海", "北京", "广州", "深圳", "青岛", "天津"]):
            # 进一步检查标题中是否有"境外"相关词
            if "境外" not in title_text and "海外" not in title_text:
                return "境内交易"

        return None

    def _find_target_country(self, text: str, file_name: str) -> Optional[str]:
        """
        查找目标国家/地区

        Args:
            text: 文本内容
            file_name: 文件名

        Returns:
            目标国家/地区名称
        """
        # 首先在文件名中查找（优先匹配）
        country_in_name = find_country_in_text(file_name, self.countries)
        if country_in_name:
            return country_in_name

        # 检查"海外"关键词
        overseas_keywords = ["海外", "国外", "外"]
        has_overseas_keyword = False
        for keyword in overseas_keywords:
            if keyword in file_name:
                has_overseas_keyword = True
                break

        # 如果文件名包含"海外"等关键词，也算找到境外标识
        if has_overseas_keyword:
            # 在标题区域查找国家/地区（排除"海外"关键词）
            lines = text.split("\n")
            title_area = "\n".join(lines[:50])

            # 移除"海外"、"国外"等词后再查找
            title_area_clean = title_area
            for keyword in overseas_keywords:
                title_area_clean = title_area_clean.replace(keyword, "")

            country_in_title = find_country_in_text(title_area_clean, self.countries)
            if country_in_title:
                return country_in_title

        # 然后在文本中查找（优先查找标题区域）
        lines = text.split("\n")
        title_area = "\n".join(lines[:20])  # 前20行通常包含标题
        country_in_title = find_country_in_text(title_area, self.countries)
        if country_in_title:
            return country_in_title

        # 在全文中查找
        country_in_text = find_country_in_text(text, self.countries)
        if country_in_text:
            return country_in_text

        return None

    def _check_investment_transaction(self, text: str, file_name: str) -> bool:
        """
        检查是否为投资类交易

        Args:
            text: 文本内容
            file_name: 文件名

        Returns:
            是否为投资类交易
        """
        # 检查投资相关关键词（文件名检查更宽松）
        investment_keywords = [
            "投资", "收购", "并购", "股权", "股份", "设立", "成立",
            "放款", "借款", "融资", "建设", "新建",
            "合资", "出让", "债权", "资产权益"
        ]

        # 只要文件名包含投资关键词就算
        for keyword in investment_keywords:
            if keyword in file_name:
                return True

        # 检查文本中的投资相关短语（放宽匹配条件）
        investment_patterns = [
            r"投资.{0,20}境外",  # 投资境外
            r"境外.{0,20}投资",  # 境外投资
            r"境外.{0,20}放款",  # 境外放款
            r"放款.{0,20}境外",  # 放款境外
            r"收购.{0,50}(股权|股份)",  # 收购股权/股份
            r"收购.{0,50}(?:境外|海外|美国|德国|阿根廷|越南|南非)",  # 收购境外公司
            r"设立.{0,30}(子公司|公司|工厂)",  # 设立子公司/公司/工厂
            r"成立.{0,30}(子公司|公司)",  # 成立子公司/公司
            r"对外投资.{0,20}(?:境外|海外)",  # 对外投资（境外/海外）
            r"债权.{0,30}资产权益",  # 债权资产权益（如000672）
            r"境外.{0,20}(?:合资|合作)",  # 境外合资/合作
        ]

        for pattern in investment_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def batch_classify(self, pdf_data_list: list) -> list:
        """
        批量分类PDF文件

        Args:
            pdf_data_list: PDF解析数据列表

        Returns:
            分类结果列表
        """
        results = []
        total = len(pdf_data_list)

        odi_count = 0
        excluded_count = 0
        domestic_count = 0

        for i, pdf_data in enumerate(pdf_data_list, 1):
            logger.info(f"正在分类 [{i}/{total}]: {pdf_data.get('file_name', 'unknown')}")
            result = self.classify(pdf_data)
            results.append(result)

            if result["is_odi"]:
                odi_count += 1
            elif result["exclusion_reason"]:
                excluded_count += 1
            else:
                domestic_count += 1

        logger.info(f"分类完成：境外投资 {odi_count} 个，排除 {excluded_count} 个，境内交易 {domestic_count} 个")
        return results

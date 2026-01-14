"""
LLM提取模块 - 使用大语言模型进行交易信息提取
支持Zhipu AI GLM-4 API，采用LLM优先+规则回退策略
"""

import json
import time
import hashlib
import logging
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("odi_extractor")


class LLMExtractionError(Exception):
    """LLM提取异常基类"""
    pass


class ZhipuGLM4Extractor:
    """Zhipu GLM-4 API提取器"""

    def __init__(self, config):
        """
        初始化Zhipu GLM-4提取器

        Args:
            config: 配置对象
        """
        self.api_key = config.ZHIPU_API_KEY
        self.base_url = config.ZHIPU_BASE_URL
        self.model = config.ZHIPU_MODEL
        self.max_tokens = config.ZHIPU_MAX_TOKENS
        self.temperature = config.ZHIPU_TEMPERATURE
        self.timeout = config.ZHIPU_TIMEOUT
        self.retry_attempts = config.LLM_RETRY_ATTEMPTS
        self.retry_delay = config.LLM_RETRY_DELAY

        # 初始化OpenAI客户端（兼容Zhipu API）
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
        except ImportError:
            logger.error("未安装openai库，请运行: pip install openai>=1.0.0")
            raise LLMExtractionError("缺少openai依赖")

        # 速率限制
        self.last_request_time = 0
        self.rate_limit = config.REQUEST_RATE_LIMIT

        # 缓存
        self.cache_enabled = config.ENABLE_LLM_CACHING
        self.cache_dir = Path(config.CACHE_DIR)
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _enforce_rate_limit(self):
        """强制执行速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_cache_key(self, prompt: str) -> str:
        """生成缓存键"""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """从缓存获取响应"""
        if not self.cache_enabled:
            return None

        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('response')
            except Exception as e:
                logger.warning(f"读取缓存失败: {e}")

        return None

    def _save_cached_response(self, cache_key: str, response: str):
        """保存响应到缓存"""
        if not self.cache_enabled:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'response': response,
                    'timestamp': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存缓存失败: {e}")

    def extract(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """
        调用LLM提取信息

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词

        Returns:
            LLM响应文本，失败返回None
        """
        # 检查缓存
        cache_key = self._get_cache_key(prompt)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.debug("使用缓存响应")
            return cached_response

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 重试逻辑
        import openai
        for attempt in range(self.retry_attempts):
            try:
                self._enforce_rate_limit()

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )

                content = response.choices[0].message.content
                logger.debug(f"LLM原始响应长度: {len(content) if content else 0}")
                logger.debug(f"LLM原始响应内容: {repr(content[:200]) if content else 'None'}")

                result = content.strip() if content else ""

                # 保存缓存
                self._save_cached_response(cache_key, result)

                logger.debug(f"LLM提取成功 (尝试 {attempt + 1}/{self.retry_attempts})")
                return result

            except openai.RateLimitError as e:
                logger.warning(f"LLM速率限制错误 (尝试 {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
            except openai.APITimeoutError as e:
                logger.warning(f"LLM超时错误 (尝试 {attempt + 1}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
            except openai.APIError as e:
                logger.error(f"LLM API错误: {e}")
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
            except Exception as e:
                logger.error(f"LLM提取失败: {e}")
                break

        return None


class PromptBuilder:
    """提示词构建器"""

    def __init__(self, system_prompt_template: str):
        """
        初始化提示词构建器

        Args:
            system_prompt_template: 系统提示词模板
        """
        self.system_prompt_template = system_prompt_template

    def build_extraction_prompt(
        self,
        text: str,
        file_name: str,
        target_country: str = None
    ) -> str:
        """
        构建信息提取提示词

        Args:
            text: PDF文本内容
            file_name: 文件名
            target_country: 目标国家/地区

        Returns:
            构建好的提示词
        """
        # 限制文本长度避免token超限
        text_preview = text[:8000] if len(text) > 8000 else text
        if len(text) > 8000:
            text_preview += "\n...[中间内容省略]..."

        prompt = f"""请从以下境外投资交易公告文本中提取结构化信息。

文件名: {file_name}
目标国家/地区: {target_country or '未明确'}

=== 公告文本 ===
{text_preview}
=== 文本结束 ===

请提取以下信息，并以JSON格式返回：

{{
    "基本信息": {{
        "标的公司/项目名称": "完整的公司名称或项目名称（包括外文原名）",
        "标的公司注册地": "目标公司注册的国家/地区",
        "交易类型": "收购股权、设立子公司、境外放款、增资等",
        "交易金额/投资额": "交易金额或投资额，保留单位（如：7,319万元、1.25亿美元）",
        "股权比例": "涉及的股权比例（如：100%、51%）",
        "交易对手方": "交易对手方名称",
        "当前进展阶段": "交易当前进展状态（如：已通过审议、已签署协议、已完成交割、拟进行）",
        "业务范围": "目标公司的主要业务范围"
    }},
    "交易结构": {{
        "投资主体": "实施投资的公司或子公司名称",
        "SPV结构": "特殊目的公司结构描述",
        "资金来源": "资金来源（如：自有资金、募集资金、银行贷款）",
        "支付方式": "支付方式（如：现金、股权置换）",
        "对赌/业绩承诺": "对赌协议或业绩承诺内容",
        "交易架构": "完整的交易架构描述"
    }},
    "合规审批": {{
        "境内审批事项": "需要办理的境内审批（如：发改委、商务部、外汇局）",
        "境外审批事项": "需要办理的境外审批（如：反垄断审查、外商投资审查）",
        "审批进度": "当前审批进度",
        "审批条件": "交易的先决条件和审批条件（如：需获得备案批准、满足交割前提等。如无特殊审批条件，请根据实际情况标注\"新设公司，不涉及\"或\"未明确\"或\"人工确认\"）",
        "交割条件": "交易完成的条件",
        "特殊许可": "需要的特殊牌照或许可（如：经营牌照、行业资质、许可证、特许经营权等。如无特殊许可要求，请根据实际情况标注\"新设公司，不涉及\"或\"无需特殊许可\"或\"未明确\"或\"人工确认\"）"
    }}
}}

提取要求：
1. 如果文本中没有明确提及某个字段，返回空字符串 ""
2. "当前进展阶段"字段要准确提取状态描述，不要提取百分比（如100%、99.9%）
3. "标的公司/项目名称"要提取完整的外文名称，包括公司类型后缀（如GmbH、Corp、Inc、Ltd），不要提取描述性简称（如"紧固件德国公司"）
4. "业务范围"必须是**目标公司（标的公司/被收购方）**的主要业务范围，**不要提取投资方（我司、本公司）**的业务范围。如果只提到了投资方的业务范围（如"我司是从事贸易类..."），该字段应返回空字符串 ""。
5. **空值处理**：对于"审批条件"和"特殊许可"字段，如果文本中确实没有相关要求，应根据实际情况标注：
   - 如果是新设立的公司，标注："新设公司，不涉及"
   - 如果交易是简单的股权收购/增资/放款，标注："无需特殊许可"或"不涉及"
   - 如果确实未提及或情况不明，标注："未明确"或"人工确认"
   - 不要直接返回空字符串""，请提供有意义的标注
6. 金额和比例要保留原文格式
7. 返回标准的JSON格式，不要有其他说明文字，可以直接用json.loads()解析
"""
        return prompt

    def build_system_prompt(self) -> str:
        """
        构建系统提示词

        Returns:
            系统提示词
        """
        return self.system_prompt_template


class HybridExtractor:
    """混合提取器 - LLM优先+规则回退"""

    def __init__(self, config, llm_extractor: ZhipuGLM4Extractor, rule_extractor):
        """
        初始化混合提取器

        Args:
            config: 配置对象
            llm_extractor: LLM提取器
            rule_extractor: 规则提取器
        """
        self.config = config
        self.llm_extractor = llm_extractor
        self.rule_extractor = rule_extractor
        self.prompt_builder = PromptBuilder(config.SYSTEM_PROMPT_TEMPLATE)

        # 统计信息
        self.stats = {
            "total_fields": 0,
            "llm_success": 0,
            "llm_fallback": 0,
            "rule_used": 0
        }

    def extract(
        self,
        pdf_data: Dict,
        classification: Dict
    ) -> Dict:
        """
        混合提取主函数

        Args:
            pdf_data: PDF解析数据
            classification: 分类结果

        Returns:
            提取的交易信息字典
        """
        text = pdf_data.get("text_content", "")
        file_name = pdf_data.get("file_name", "")
        target_country = classification.get("target_country", "")

        # 先尝试LLM提取
        llm_result = self._extract_with_llm(text, file_name, target_country)

        if llm_result:
            # LLM提取成功，合并规则提取的基础信息（从文件名提取的字段）
            result = self._merge_with_rule_base(llm_result, pdf_data, classification)

            # 检查是否有空值，对空值进行规则回退
            if self.config.ENABLE_RULE_FALLBACK:
                result = self._apply_rule_fallback(result, pdf_data, classification)

            return result
        else:
            # LLM提取失败，完全回退到规则提取
            logger.warning("LLM提取失败，回退到规则提取")
            return self.rule_extractor.extract(pdf_data, classification)

    def _extract_with_llm(
        self,
        text: str,
        file_name: str,
        target_country: str
    ) -> Optional[Dict]:
        """
        使用LLM提取信息

        Args:
            text: 文本内容
            file_name: 文件名
            target_country: 目标国家

        Returns:
            LLM提取结果，失败返回None
        """
        try:
            # 构建提示词
            prompt = self.prompt_builder.build_extraction_prompt(
                text, file_name, target_country
            )
            system_prompt = self.prompt_builder.build_system_prompt()

            # 调用LLM
            response = self.llm_extractor.extract(prompt, system_prompt)

            if not response:
                logger.warning("LLM返回空响应")
                return None

            # 去除markdown代码块标记（```json 和 ```）
            cleaned_response = response.strip()
            if cleaned_response.startswith("```"):
                # 查找第一个和第二个```之间的内容
                lines = cleaned_response.split("\n")
                # 移除开头的```行
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # 移除结尾的```行
                if lines and lines[-1] == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines).strip()

            # 解析JSON响应
            try:
                result = json.loads(cleaned_response)
                self.stats["llm_success"] += 1
                logger.info("LLM提取成功")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"LLM响应JSON解析失败: {e}")
                logger.debug(f"LLM原始响应内容: {response[:500]}")
                logger.debug(f"LLM清理后内容: {cleaned_response[:500]}")
                return None

        except Exception as e:
            logger.error(f"LLM提取过程异常: {e}")
            return None

    def _merge_with_rule_base(
        self,
        llm_result: Dict,
        pdf_data: Dict,
        classification: Dict
    ) -> Dict:
        """
        合并LLM结果和规则提取的基础信息

        Args:
            llm_result: LLM提取结果
            pdf_data: PDF数据
            classification: 分类结果

        Returns:
            合并后的结果
        """
        # 先从规则提取获取基础信息（股票代码、公司名称、公告日期等）
        rule_result = self.rule_extractor.extract(pdf_data, classification)

        # 使用LLM结果，但用规则提取的基础信息覆盖特定字段
        result = llm_result

        # 覆盖基础信息字段
        if "基本信息" not in result:
            result["基本信息"] = {}

        basic_info = result.get("基本信息", {})
        rule_basic = rule_result.get("基本信息", {})

        # 从文件名提取的字段优先使用规则提取
        filename_fields = ["股票代码", "公司名称", "公告日期", "文件名称"]
        for field in filename_fields:
            basic_info[field] = rule_basic.get(field, "")

        return result

    def _apply_rule_fallback(
        self,
        llm_result: Dict,
        pdf_data: Dict,
        classification: Dict
    ) -> Dict:
        """
        对LLM的空值字段应用规则回退

        Args:
            llm_result: LLM提取结果
            pdf_data: PDF数据
            classification: 分类结果

        Returns:
            应用回退后的结果
        """
        # 先获取规则提取的完整结果
        rule_result = self.rule_extractor.extract(pdf_data, classification)

        # 检查每个字段，如果LLM结果为空，则使用规则结果
        for category in ["基本信息", "交易结构", "合规审批"]:
            if category not in llm_result:
                continue

            if category not in rule_result:
                continue

            for field, llm_value in llm_result[category].items():
                if not llm_value or llm_value.strip() == "":
                    # 使用规则提取的值
                    rule_value = rule_result.get(category, {}).get(field, "")
                    if rule_value:
                        llm_result[category][field] = rule_value
                        self.stats["llm_fallback"] += 1
                        logger.debug(f"字段回退规则: {category}.{field}")

        return llm_result

    def get_stats(self) -> Dict:
        """
        获取提取统计信息

        Returns:
            统计信息字典
        """
        return self.stats.copy()

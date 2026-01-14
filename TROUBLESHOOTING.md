# 故障排查和调试指南

## 目录
1. [常见问题及解决方案](#常见问题及解决方案)
2. [查看日志](#查看日志)
3. [调试单个文件](#调试单个文件)
4. [修复代码](#修复代码)
5. [增量处理](#增量处理)
6. [验证修复](#验证修复)

---

## 常见问题及解决方案

### 问题1：某些境外投资被错误排除

**症状**：确认是境外投资，但被排除在"排除文件"Sheet中

**排查步骤**：

1. 检查排除原因
   - 打开Excel中的"排除文件"Sheet
   - 查看"排除原因"列

2. 常见原因和解决方案：

| 排除原因 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 仅境外药品注册/上市批准 | 被误判为药品注册 | 检查`odi_classifier.py`的`_check_exclusion`方法，调整关键词匹配逻辑 |
| 运营数据/财务数据信息披露 | 被误判为纯信息披露 | 检查是否同时包含投资行为，调整排除规则 |
| 出口贸易业务 | 被误判为出口贸易 | 检查是否包含设立/收购等投资关键词 |
| 发现境外标识但非投资类交易 | 没有检测到投资关键词 | 检查`_check_investment_transaction`方法，补充关键词 |

3. 修复代码（参考[修复代码](#修复代码)章节）

---

### 问题2：境内交易被错误识别为境外投资

**症状**：明明是国内交易，却出现在"全部交易"Sheet中

**排查步骤**：

1. 检查文件中是否包含境外国家/地区名称
   - 可能是公司名称中包含"香港"、"美国"等
   - 需要在`_check_exclusion`中添加排除逻辑

2. 修复示例：

```python
# 在 odi_classifier.py 的 _check_exclusion 方法中添加

# 检查是否是境内公司的境外子公司（如"香港XX有限公司"但实际是境内交易）
if "中国" in text or "境内" in text:
    # 检查是否有真正的境外投资行为
    if "设立" not in text and "投资" not in text and "收购" not in text:
        return "境内公司境外业务披露"
```

---

### 问题3：字段提取不准确

**症状**：交易金额、股权比例等关键信息提取错误或为空

**排查步骤**：

1. 找出提取失败的文件
   - 查看"全部交易"Sheet，找到字段为空的行

2. 查看原文
   - 打开对应的PDF文件
   - 搜索相关信息（如"金额"、"投资额"、"%股权"等）

3. 常见原因：

| 问题类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 金额为空 | 金额格式特殊（如"1.25亿美元"） | 修改`utils.py`的`extract_amount`方法，添加新格式 |
| 股权比例为空 | 格式为"100%股权"或"百分之百" | 修改`extract_percentage`方法 |
| 公司名称不准确 | 提取逻辑匹配错误 | 调整`_extract_target_company`方法的正则表达式 |

4. 修复示例：

```python
# 在 utils.py 的 extract_amount 方法中添加新格式

# 新增：匹配 "1.25亿美元" 格式
pattern = r'[\d.]+\s*亿美元'
match = re.search(pattern, text)
if match:
    return match.group()
```

---

### 问题4：程序运行速度太慢

**症状**：处理500+文件耗时过长（超过30分钟）

**排查步骤**：

1. 检查文件大小
   - 大文件（>10MB）处理较慢是正常的

2. 优化方法：
   - 使用`--no-pdfplumber`参数使用更快的pypdf解析
   - 或者在`config.py`中设置`USE_PDFPLUMBER = False`

3. 增量处理（参考[增量处理](#增量处理)章节）

---

### 问题5：程序崩溃或报错

**症状**：运行中途报错退出

**排查步骤**：

1. 查看日志文件
   - 日志位于`odi-extractor/logs/`目录
   - 找到最新的日志文件

2. 常见错误：

| 错误类型 | 可能原因 | 解决方案 |
|---------|---------|---------|
| `FileNotFoundError` | PDF文件路径错误 | 检查`-d`参数指定的路径是否正确 |
| `SyntaxError` | 代码语法错误 | 检查最近修改的代码文件 |
| `KeyError` | 字典键不存在 | 检查提取逻辑中的字典访问 |
| `UnicodeDecodeError` | PDF编码问题 | 尝试用其他PDF解析器 |

3. 跳过错误文件：
```python
# 在 pdf_parser.py 中添加异常处理
try:
    result = self.parse_pdf(file_path)
    results.append(result)
except Exception as e:
    logger.error(f"跳过文件 {file_path}: {e}")
    results.append({"error": str(e)})
```

---

## 查看日志

### 日志位置
```
odi-extractor/logs/
└── odi_extractor_20250114_185612.log
```

### 日志级别
- `INFO`：常规信息（文件处理进度等）
- `DEBUG`：详细信息（推荐用于调试）
- `WARNING`：警告信息
- `ERROR`：错误信息

### 启用详细日志

```bash
# 方式1：命令行参数
python odi-extractor/odi_extractor.py -v

# 方式2：修改配置文件
# 在 config.py 中设置
LOG_LEVEL = "DEBUG"
```

### 日志示例

```
2026-01-14 18:56:33,679 - odi_extractor - INFO - 正在分类 [1/32]: 000002 万科A...
2026-01-14 18:56:33,679 - odi_extractor - DEBUG - 检查排除关键词...
2026-01-14 18:56:33,679 - odi_extractor - DEBUG - 发现排除关键词: 境外
2026-01-14 18:56:33,679 - odi_extractor - ERROR - 解析PDF失败: xxx.pdf, 错误: ...
```

---

## 调试单个文件

当发现某个文件处理有问题时，可以单独调试：

### 步骤1：创建调试脚本

创建文件 `debug_single.py`：

```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pdf_parser import PDFParser
from odi_classifier import ODIClassifier
from rule_extractor import RuleExtractor
import config

# 要调试的文件路径
TEST_FILE = "./000513 丽珠集团 2025-05-23  关于拟收购越南IMP公司股权的公告.PDF"

# 初始化模块
pdf_parser = PDFParser()
classifier = ODIClassifier(config)
extractor = RuleExtractor(config)

# 步骤1：解析PDF
print("=" * 60)
print("步骤1: 解析PDF")
print("=" * 60)
pdf_data = pdf_parser.parse_pdf(TEST_FILE)
print(f"成功: {pdf_data.get('success')}")
print(f"页数: {pdf_data.get('num_pages')}")
print(f"文本长度: {len(pdf_data.get('text_content', ''))}")

# 步骤2：分类
print("\n" + "=" * 60)
print("步骤2: 分类识别")
print("=" * 60)
classification = classifier.classify(pdf_data)
print(f"是否为境外投资: {classification.get('is_odi')}")
print(f"原因: {classification.get('reason')}")
print(f"目标国家: {classification.get('target_country')}")
print(f"排除原因: {classification.get('exclusion_reason')}")

# 步骤3：提取信息
print("\n" + "=" * 60)
print("步骤3: 提取信息")
print("=" * 60)
if classification.get('is_odi'):
    extracted = extractor.extract(pdf_data, classification)
    for category, data in extracted.items():
        print(f"\n【{category}】")
        for key, value in data.items():
            print(f"  {key}: {value}")
```

### 步骤2：运行调试脚本

```bash
python odi-extractor/debug_single.py
```

### 步骤3：分析输出

根据输出结果，定位问题：
- 如果`success`为False，检查PDF文件是否损坏
- 如果`is_odi`与预期不符，检查分类逻辑
- 如果提取的字段不准确，检查提取逻辑

---

## 修复代码

### 步骤1：定位问题代码

根据日志或调试输出，找到需要修改的文件和函数。

常见修改位置：

| 问题类型 | 文件 | 函数/方法 |
|---------|------|----------|
| 分类错误 | `odi_classifier.py` | `_check_exclusion()`, `_find_target_country()` |
| 字段提取错误 | `rule_extractor.py` | `_extract_amount()`, `_extract_target_company()` 等 |
| 工具函数错误 | `utils.py` | `extract_amount()`, `parse_filename()` 等 |

### 步骤2：修改代码

示例：修复金额提取问题

```python
# 打开 odi-extractor/rule_extractor.py
# 找到 _extract_amount 方法

def _extract_amount(self, text: str) -> str:
    """提取交易金额"""
    amount = extract_amount(text)

    # 添加：特殊格式处理
    if not amount:
        # 处理 "1250万美元" 格式
        pattern = r'(\d+)\s*(万|百万|亿)美元'
        match = re.search(pattern, text)
        if match:
            return match.group()

    return amount if amount else ""
```

### 步骤3：保存并测试

```bash
# 运行单个文件测试
python odi-extractor/debug_single.py

# 运行全部文件测试
python odi-extractor/odi_extractor.py
```

---

## 增量处理

当处理500+文件时，发现bug后不必重新处理所有文件：

### 方法1：跳过已处理的文件

修改 `odi_extractor.py`：

```python
def run(self, pdf_dir: str = None):
    # ... 之前的代码 ...

    # 检查是否已有输出文件
    excel_path = os.path.join(self.output_dir, config.EXCEL_FILE)
    processed_files = set()

    if os.path.exists(excel_path):
        # 读取已处理的文件名
        import pandas as pd
        df = pd.read_excel(excel_path, sheet_name="全部交易")
        processed_files = set(df["文件名称"].tolist())

    # 只处理未处理的文件
    pdf_files_to_process = [
        f for f in pdf_files
        if os.path.basename(f) not in processed_files
    ]

    if pdf_files_to_process:
        print(f"跳过 {len(pdf_files) - len(pdf_files_to_process)} 个已处理文件")
        print(f"处理 {len(pdf_files_to_process)} 个新文件")

        # 只处理新文件
        pdf_data_list = self.pdf_parser.batch_parse(pdf_files_to_process)
        # ... 后续处理 ...
```

### 方法2：分批处理

```bash
# 第1批：处理前100个
mkdir output_batch1
python odi-extractor/odi_extractor.py -d pdf_files/ -o output_batch1

# 第2批：处理中间200个
mkdir output_batch2
# 将第101-300个文件移到 pdf_files_batch2/
python odi-extractor/odi_extractor.py -d pdf_files_batch2/ -o output_batch2

# 第3批：处理剩余文件
mkdir output_batch3
python odi-extractor/odi_extractor.py -d pdf_files_batch3/ -o output_batch3

# 手动合并Excel（或写脚本合并）
```

---

## 验证修复

### 步骤1：重新运行

```bash
# 运行程序
python odi-extractor/odi_extractor.py -d . -o output_test

# 或使用增量处理
python odi-extractor/odi_extractor.py -d pdf_files/
```

### 步骤2：对比结果

1. 打开新生成的Excel文件
2. 对比之前的Excel文件
3. 检查问题是否解决

### 步骤3：统计验证

检查"统计摘要"Sheet：
- 境外投资数量是否符合预期
- 排除数量是否合理
- 国家/地区分布是否正确

### 步骤4：抽样检查

随机抽查5-10个记录，人工核对：
1. 打开原始PDF
2. 对比提取的字段
3. 验证准确性

---

## 性能优化建议

处理500+文件时的优化建议：

### 1. 使用更快的PDF解析器

```python
# 在 config.py 中添加
USE_PDFPLUMBER = False  # 改用pypdf，速度更快但精度略低
```

### 2. 并行处理

```python
# 使用多进程处理（需要修改代码）
from multiprocessing import Pool

def process_file(file_path):
    # 单个文件的处理逻辑
    pass

if __name__ == '__main__':
    with Pool(processes=4) as pool:
        results = pool.map(process_file, pdf_files)
```

### 3. 分批处理

按公司分批，每批100个：
```bash
python odi-extractor/odi_extractor.py -d pdf_files/batch1/
python odi-extractor/odi_extractor.py -d pdf_files/batch2/
# ...
```

---

## 联系支持

如果以上方法无法解决问题：

1. 收集以下信息：
   - 错误日志文件
   - 有问题的PDF文件（如果允许）
   - 问题描述和期望结果

2. 检查GitHub Issues是否有类似问题

3. 提交Issue时附带：
   - 日志文件内容
   - 系统环境（Python版本、操作系统）
   - 复现步骤

---

## 附录：常用调试技巧

### 打印中间结果

```python
# 在代码中添加print语句
print(f"DEBUG: text length = {len(text)}")
print(f"DEBUG: found country = {target_country}")
```

### 使用断言

```python
# 验证假设
assert len(text) > 0, "文本内容为空！"
assert target_country is not None, "未找到目标国家！"
```

### 记录特定文件

```python
# 在 config.py 中添加
DEBUG_FILES = ["000513", "000796"]  # 只调试这些文件

# 在代码中使用
if any(f in file_name for f in config.DEBUG_FILES):
    logger.debug(f"调试文件: {file_name}")
    # 详细日志
```

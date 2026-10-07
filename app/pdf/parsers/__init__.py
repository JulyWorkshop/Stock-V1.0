"""
识别率优化的 5 步策略

由表及里：
- Step 1: 修复 table_parser 的 current/prior 列颠倒（最致命，影响所有 PDF）
- Step 2: 修复 value is None 直接跳过 → 改为保留 is_recognized=False 的 LineItem
- Step 3: 扩展 subject_alias 别名（覆盖新准则合并科目和未识别标准科目）
- Step 4: 增强 _clean_subject_name 处理更复杂的科目名变体
- Step 5: 添加 regex_scan 兜底扫描器
"""
# 占位文件 - 后续会在 __init__.py 中按需 import
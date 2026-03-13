import sys
import os
sys.path.insert(0, os.path.abspath("."))
from core.analyzer import RequirementAnalyzer

analyzer = RequirementAnalyzer()
res = analyzer.analyze("生成智能陪练需求")
print(f"Domain: {res.domain}")
print(f"Domain Name: {res.domain_name}")
print(f"Modules: {res.core_modules}")
print(f"Features: {res.feature_list}")

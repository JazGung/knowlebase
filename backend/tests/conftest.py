"""
Pytest 配置
"""

import sys
import os

# 将 src 目录添加到 Python 路径
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_backend_dir, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

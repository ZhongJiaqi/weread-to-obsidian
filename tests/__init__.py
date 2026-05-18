"""动态加载主脚本（无 .py 后缀）为 weread 模块。"""
import importlib.util
import importlib.machinery
import sys
from pathlib import Path

_path = str(Path(__file__).parent.parent / "weread-to-obsidian")
# Note: spec_from_file_location returns None for files without a .py extension
# in Python 3.14+; SourceFileLoader + spec_from_loader is the correct path here.
_loader = importlib.machinery.SourceFileLoader("weread", _path)
_spec = importlib.util.spec_from_loader("weread", _loader)
weread = importlib.util.module_from_spec(_spec)
sys.modules["weread"] = weread
_loader.exec_module(weread)

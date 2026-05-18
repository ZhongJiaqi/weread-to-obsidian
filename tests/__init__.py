"""动态加载主脚本（无 .py 后缀）为 weread 模块。"""
import importlib.util
import importlib.machinery
import sys
from pathlib import Path

_path = str(Path(__file__).parent.parent / "weread-to-obsidian")
_loader = importlib.machinery.SourceFileLoader("weread", _path)
_spec = importlib.util.spec_from_loader("weread", _loader)
weread = importlib.util.module_from_spec(_spec)
sys.modules["weread"] = weread
_loader.exec_module(weread)

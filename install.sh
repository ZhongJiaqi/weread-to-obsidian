#!/usr/bin/env bash
# 一键安装：把 weread-to-obsidian 拷贝到 ~/.local/bin 并加可执行权限

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.local/bin"
TARGET="$TARGET_DIR/weread-to-obsidian"

mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/weread-to-obsidian" "$TARGET"
chmod +x "$TARGET"

echo "✅ 已安装到 $TARGET"
echo ""

# 检查 PATH
case ":$PATH:" in
  *":$TARGET_DIR:"*)
    echo "✓ $TARGET_DIR 已在 PATH 中"
    ;;
  *)
    echo "⚠️  $TARGET_DIR 不在 PATH 中。请把下面这行加到你的 ~/.zshrc 或 ~/.bashrc："
    echo ""
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

echo ""
echo "下一步："
echo "  1. 设置 WEREAD_API_KEY 环境变量（参见 README.md 配置章节）"
echo "  2. 运行 weread-to-obsidian --list 验证"

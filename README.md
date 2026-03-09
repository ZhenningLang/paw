<p align="center">
  <img src="logo.svg" width="128" height="128" alt="Paw">
</p>

<h1 align="center">Paw</h1>
<p align="center">终端文本增强插件 — 中文分词跳转 · 图片粘贴 · Cmd+Z 撤销</p>

---

## 功能

| 功能 | 按键 | 实现层 | 终端要求 |
|------|------|--------|----------|
| 中文分词跳转 | Option+←/→ | zsh widget + jieba daemon | 任意终端 (zsh) |
| 中文分词删除 | Option+Delete | zsh widget + jieba daemon | 任意终端 (zsh) |
| 剪贴板图片粘贴 | Cmd+V | iTerm2 Python 插件 | iTerm2 |
| Cmd+Z 撤销 | Cmd+Z | iTerm2 plist 键映射 | iTerm2 |

### 中文分词跳转

在终端命令行中按 Option+Arrow 可以按中文词语跳转光标，而非逐字移动。基于 jieba 分词，常驻 daemon 通过 Unix socket 响应。

### 图片粘贴

按 Cmd+V 时自动检测剪贴板中是否有图片，有则保存为文件并粘贴路径，无则正常粘贴文本。适用于 AI 编程助手、Markdown 编辑等场景。

## 安装

```bash
git clone https://github.com/ZhenningLang/iterm2-paste-image.git
cd iterm2-paste-image
./install.sh
```

安装完成后运行 `paw` 管理功能。

### 前置条件

- macOS
- zsh（分词功能）
- iTerm2 + Python API 已启用（图片粘贴 / Cmd+Z 功能）
- (可选) [pngpaste](https://github.com/jcsalterego/pngpaste)：`brew install pngpaste`

### 启用 iTerm2 Python API

Settings (Cmd+,) → General → Magic → 勾选 **Enable Python API** → 重启 iTerm2

## 使用

### CLI 管理工具

```bash
paw              # 交互式主界面（查看状态、启停功能）
paw status       # 非交互式状态查看
paw diagnose     # 诊断 + 自动修复
paw daemon start|stop|restart|status
```

### 配置文件

`~/.config/paw/config.json`：

```json
{
    "paste_image": {
        "save_directory": "~/.config/paw/images",
        "filename_format": "%Y%m%d_%H%M%S",
        "output_format": "{path}"
    }
}
```

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `save_directory` | 图片保存目录 | `~/.config/paw/images` |
| `filename_format` | 文件名时间格式 (strftime) | `%Y%m%d_%H%M%S` |
| `output_format` | 输出模板，变量：`{path}` `{filename}` `{dir}` | `{path}` |

## 架构

```
~/.config/paw/
├── paw_cli.py          # CLI 管理工具
├── paw_segmenter.py    # jieba 分词 daemon（Unix socket）
├── paw.zsh             # zle widget + 按键绑定
├── paw.py              # iTerm2 图片粘贴插件
├── venv/               # Python 虚拟环境 (jieba)
├── config.json         # 用户配置
├── paw.sock            # daemon socket
├── paw.pid             # daemon PID
└── images/             # 粘贴的图片
```

分词功能链路：`按键 → zsh widget → nc -U socket → jieba daemon → 返回新光标位置 → zle 更新`

## 常见问题

**Option+Arrow 没反应？**
运行 `paw diagnose`，自动检测 daemon、zshrc、jieba 状态并修复。

**图片粘贴不工作？**
确认 iTerm2 Python API 已启用，运行 `paw diagnose` 检查插件安装状态。

## License

MIT

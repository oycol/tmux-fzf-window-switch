# tmux-fzf-window-switch

fzf 弹窗快速切换 tmux window，支持树状 session/window 列表、实时预览、键盘导航。

## 功能

- 树状列出所有 session 下的 window（session 为标题行，不可选）
- 实时预览目标 window 画面（保留多 pane 布局，自动等比缩放）
- j/k 导航，Enter 切换，q 退出，Ctrl-p 开关预览
- 在 session 标题行按 Enter 自动跳到该 session 第一个可用 window
- 单 window 时弹小框提示"没有其他窗口"
- Tokyo Night Moon 配色，和 [tokyonight.nvim](https://github.com/folke/tokyonight.nvim) 统一

## 依赖

- [fzf](https://github.com/junegunn/fzf) (>= 0.74)
- tmux >= 3.2 (display-popup)
- python3 (多 pane 预览)

## 安装

### TPM (推荐)

```tmux
set -g @plugin 'oycol/tmux-fzf-window-switch'
```

按 `prefix + I` 安装，TPM 会自动注册 `prefix + w` 绑定。

### 手动

```bash
git clone https://github.com/oycol/tmux-fzf-window-switch ~/.tmux/plugins/tmux-fzf-window-switch
```

在 tmux.conf 中添加：

```tmux
run-shell ~/.tmux/plugins/tmux-fzf-window-switch/tmux_fzf_window_switch.tmux
```

## 自定义绑定

默认绑定 `prefix + w`。

### 方式1：环境变量（推荐）

在 tmux.conf 中插件声明之前设置：

```tmux
# 改为 prefix + x
TMUX_WINDOW_SWITCH_KEY="x"
set -g @plugin 'oycol/tmux-fzf-window-switch'
```

## 预览

预览窗口在右侧 75%，实时刷新目标 window 画面：

- 单 pane：直接显示 capture-pane 内容
- 多 pane：自动等比缩放，保留 pane 布局，用 │ 分隔

按 `Ctrl-p` 可开关预览。

## 键位

| 键 | 功能 |
|---|---|
| `j` / `k` | 上下移动 |
| `Enter` | 切换到选中 window |
| `q` | 退出 |
| `Ctrl-p` | 开关预览窗口 |

在 session 标题行（► 开头）上按 Enter，自动跳到该 session 第一个可用 window。

## License

MIT

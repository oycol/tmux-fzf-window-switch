# tmux-fzf-window-switch

fzf 弹窗快速切换 tmux window，支持树状 session/window 列表、实时预览、键盘导航。

## 功能

- 树状列出所有 session 下的 window（session 为标题行，不可选）
- 实时预览目标 window 画面（保留 pane 布局）
- j/k 导航，Enter 切换，q 退出，Ctrl-p 开关预览
- 在 session 标题行按 Enter 自动跳到该 session 第一个可用 window
- 单 window 时弹小框提示"没有其他窗口"

## 依赖

- [fzf](https://github.com/junegunn/fzf) (>= 0.74)
- tmux >= 3.2 (display-popup)
- python3 (多 pane 预览)

## 安装

### TPM

```tmux
set -g @plugin 'huangwenxuan/tmux-fzf-window-switch'
```

按 `prefix + I` 安装。

### 手动

```bash
git clone https://github.com/huangwenxuan/tmux-fzf-window-switch ~/.tmux/plugins/tmux-fzf-window-switch
```

在 tmux.conf 中添加：

```tmux
run-shell ~/.tmux/plugins/tmux-fzf-window-switch/tmux_fzf_window_switch.tmux
```

## 配置

默认绑定 `prefix + w`，可通过环境变量自定义：

```tmux
TMUX_WINDOW_SWITCH_KEY="x"
```

## 配色

Tokyo Night Moon，和 [tokyonight.nvim](https://github.com/folke/tokyonight.nvim) 统一。

## License

MIT

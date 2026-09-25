# tmux-fzf-window-switch

在 tmux 中用 `prefix + w` 打开窗口切换弹窗。按 Session 分组显示窗口、目录和 Pane 数，右侧显示选中窗口的 Pane 快照。

## 往返逻辑

通过切换器从 A 成功切到 B 后，在同一客户端再次打开弹窗，默认选中 A，直接按 `Enter` 返回；返回后再打开则默认选中 B。此记录跨 Session 仅有一个，按 tmux 客户端隔离；与每个 Session 自带的“上次窗口”无关。源窗口用 `●` 标记，返回窗口用 `↩` 标记。目标已被删除时回退到可选窗口，不复用旧坐标。服务端退出后记录失效。

## 操作

| 按键 | 行为 |
| --- | --- |
| `j/k`、`↓/↑` | 在可选窗口间循环，跳过源窗口与标题 |
| `J/K` | 跨到下一个/上一个有候选的 Session，优先聚焦它的活动窗口 |
| `Enter` | 切换选中窗口；切换失败时留在弹窗 |
| `/` | 搜索窗口元数据；搜索时 `j/k/q` 为文本，方向键移动结果，`Esc` 保留过滤并回浏览 |
| 数字、`:` | 精确定位，如 `2.2`、`:bios:2`；`Esc` 取消并恢复原焦点 |
| `Ctrl-x` | **立即删除**选中的非源窗口，不二次确认；删除后须移动到另一窗口才能再次删除 |
| `Ctrl-p`、`v`、`[`/`]` | 显隐预览、切单 Pane、切换预览 Pane |
| `Ctrl-r`、`Ctrl-u` | 刷新快照、清空过滤词 |
| `?`、`q/Esc` | 帮助提示、退出浏览 |

`Tab/Shift-Tab` 未绑定。删除整个窗口会关闭其中全部 Pane；链接窗口与源窗口受到保护。Pane 预览是只读快照，不是实时画面。

## 依赖与安装

需要 Python 3（标准库 curses）、tmux、fzf。在 `~/.tmux.conf` 加入：

```tmux
set -g @plugin 'oycol/tmux-fzf-window-switch'
```

用 TPM 安装后，默认绑定 `prefix + w`。也可将仓库放入 `~/.tmux/plugins/tmux-fzf-window-switch`，在 tmux 配置中使用 `run-shell ~/.tmux/plugins/tmux-fzf-window-switch/tmux_fzf_window_switch.tmux`。

本地测试：`python3 -m unittest discover -s tests -v`。本项目许可证为 MIT。

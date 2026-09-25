# tmux-fzf-window-switch

[![CI](https://github.com/oycol/tmux-fzf-window-switch/actions/workflows/ci.yml/badge.svg)](https://github.com/oycol/tmux-fzf-window-switch/actions/workflows/ci.yml)

fzf 弹窗极速切换 tmux 窗口与会话。支持树状会话/窗口列表、S.W 坐标秒级直达、四方边框零闪烁 2D 预览、弹窗高度自适应，针对 Tabby 等现代终端深度优化。

## 功能特性

- **S.W 全局坐标定位系统**：
  - 每行窗口前均带有明确的 `1.0`, `1.1`, `2.2` 编号。
  - **想去 Session 2 的 2 号窗口**：直接在弹窗中打字输入 `2.2` 或 `2 2`（或 `bios 2`），敲回车直达！彻底解决跨会话同名、同序号窗口歧义。
- **全局唯一 `[-]` 与 Tab 闪跳**：
  - 严格只在**当前所在 Session 的上一个活跃窗口**上标注 `[-]`，其他会话绝不重复标记。
  - 按 `Tab`（或 `Ctrl-i`）精准吸附到该唯一目标；再次按 `Tab` 跳回当前窗口，实现双向蹦床切换。
- **弹窗高度动态自适应（Dynamic Height）**：
  - 根据当前窗口总数动态计算弹窗高度（`clamp(12, N+6, 75%)`）。
  - 窗口少时紧凑精致居中，**彻底消除底部大面积多余黑屏**；窗口多时自动舒展。
- **2D 四方边框网格预览（Bordered Grid）**：
  - 多 Pane 拓扑渲染自动补齐**横向分割线 `─` 与纵向分割线 `│`**，带各 Pane 标题栏与活动指示 `*`。
  - 顶部常驻 Window 元数据 Header，消除单行新终端的空黑感与粘连错位。
  - 单次极速静态捕获，彻底告别 3 秒清屏黑屏闪烁。
- **Tabby / 现代终端高兼容**：
  - 彻底剔除不可控的 ANSI `\x1b[8m` 隐藏属性，杜绝在 Tabby 等终端被当成普通文本泄露打印。
  - 废除与 Tabby 标签页冲突的 `Alt+1~9`，采用 Vim 原生 `J/K` 与 `]/[` 键位实现零冲突跨 Session 飞跃。
- **底栏帮助提示（Footer Guide）**：
  - 帮助栏严格吸附在弹窗最底部，不再遮挡或倒置在搜索框上方。
- **安全窗口销毁**：
  - 选中目标窗口按 `Ctrl-x` 静默销毁并即时刷新列表（严格拦截当前窗口与会话行防误杀）。
- **Tokyo Night Moon 深度配色**，与 [tokyonight.nvim](https://github.com/folke/tokyonight.nvim) 风格统一。

## 依赖

- [fzf](https://github.com/junegunn/fzf) (>= 0.74)
- tmux >= 3.2 (display-popup)
- python3 (用于字符宽度精确对齐与多 Pane 拓扑渲染)

## 安装

### TPM (推荐)

在 `~/.tmux.conf` 中添加：

```tmux
set -g @plugin 'oycol/tmux-fzf-window-switch'
```

按 `prefix + I` 安装，TPM 会自动注册 `prefix + w` 绑定。

### 手动安装

```bash
git clone https://github.com/oycol/tmux-fzf-window-switch ~/.tmux/plugins/tmux-fzf-window-switch
```

在 `~/.tmux.conf` 中追加：

```tmux
run-shell ~/.tmux/plugins/tmux-fzf-window-switch/tmux_fzf_window_switch.tmux
```

## 自定义绑定

默认快捷键为 `prefix + w`。如需自定义（例如改为 `prefix + x`），可在 tmux.conf 中声明：

```tmux
TMUX_WINDOW_SWITCH_KEY="x"
set -g @plugin 'oycol/tmux-fzf-window-switch'
```

## 键位操作一览

| 键位 | 动作 | 说明 |
| :--- | :--- | :--- |
| `j` / `k` 或 `↓` / `↑` | 单步光标移动 | 自动跳过不可选的 Session 标题行与当前窗口行 |
| `J` / `]` | 向下跨 Session | 瞬间飞跃至下一个 Session 的首个窗口 |
| `K` / `[` | 向上跨 Session | 瞬间飞跃至上一个 Session 的首个窗口 |
| `Tab` / `Ctrl-i` | 吸附上次窗口 | 快速跳至标记为 `[-]` 的全局唯一历史活跃窗口 |
| `2.2` / 盲打搜索 | 坐标/名称直达 | 输入 `2.2` 精准锁定 Session 2 窗口 2，或输入 `bios` 模糊搜索 |
| `Enter` | 确认切换 | 切换至目标窗口；在 Session 标题行按回车切入该 Session 首个窗口 |
| `Ctrl-x` | 销毁窗口 | 销毁当前选中的非当前窗口，并自动刷新列表 |
| `Ctrl-p` | 开关预览 | 显隐右侧 55% 预览窗格 |
| `Ctrl-r` | 刷新列表 | 重新扫描 tmux 全局会话与窗口数据 |
| `q` / `Esc` | 退出 | 关闭弹窗，保持原窗口不变 |

## 自动化测试与 CI

本仓库配置有完整的 GitHub Actions 持续集成工作流（`.github/workflows/ci.yml`），包含：
- ShellCheck 与 `bash -n` 语法检查；
- 真实无头 PTY 终端交互测试（模拟 Tabby 环境下的光标跳行、S.W 坐标搜索、Tab 闪跳与边框渲染）。

本地运行测试：
```bash
python3 tests/test_switcher.py
```

## License

MIT

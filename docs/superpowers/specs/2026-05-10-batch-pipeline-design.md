# Batch Pipeline & Profile System Design

## Overview

当前 TradingAgents CLI 每次只能分析一只股票，且每次都需要重新选择 analysts、LLM provider、models 等配置。本设计引入 **Profile**（保存分析偏好）和 **Watchlist**（保存股票列表）两个独立概念，通过 `analyze` 统一入口支持批量无人值守分析，并附带自动保存报告、自动翻译、批次汇总能力。

---

## Goals

1. 用户可将 CLI 中的分析配置保存为 **Profile**，后续复用。
2. 用户可维护多个 **Watchlist**（自选股列表），在 CLI 中交互式选择。
3. `analyze` 作为唯一入口：先选择模式（批量扫描 / 自选查询），然后进入对应流程。
4. 批量模式使用 **Batch Dashboard** 实时展示进度，全程无人值守。
5. 每只股票分析完成后 **自动保存** 报告到磁盘；若输出语言为 Chinese，**自动翻译** 为 `_CN.md`。
6. 批次结束后自动生成 **汇总表格**（`batch_summary.md` + 终端 Rich Table）。
7. 单只股票失败时记录日志并自动跳过，不影响批次整体进度。

---

## Non-Goals

- 不自带任何预设 Profile，仅支持用户自己保存的 Profile。
- V1 不实现 checkpoint 恢复（代码结构预留，通过输出目录存在性检测实现简单去重）。
- 不修改现有单只股票的 core graph 逻辑（`TradingAgentsGraph` 保持不变）。
- 不新增独立的 `batch` 子命令（统一在 `analyze` 入口下）。

---

## Architecture

### 新增模块

| 文件 | 职责 |
|---|---|
| `cli/profiles.py` | Profile 的保存、加载、列出、交互式选择。提供 `save_profile()`, `load_profile()`, `list_profiles()`, `select_profile_interactive()`。 |
| `cli/watchlists.py` | Watchlist 的保存、加载、列出、交互式选择。支持 `.txt` 纯文本格式（每行一个 ticker，支持 `# 注释`）。 |
| `cli/batch_runner.py` | 批量分析 orchestrator。管理股票队列、驱动 Batch Dashboard、协调单只股票的 graph 执行、生成批次汇总。 |
| `cli/batch_dashboard.py` | Batch Dashboard 的 Rich Live 布局渲染（与现有 `main.py` 中的单只布局逻辑分离）。 |

### CLI 命令调整

保留现有 `tradingagents analyze` 作为唯一入口，增加命令行参数：

```bash
# 直接跑某个 watchlist（脚本/定时任务场景）
tradingagents analyze --watchlist tech_stocks --profile my_profile

# 直接跑临时股票列表
tradingagents analyze --tickers AAPL,MSFT,GOOGL --profile my_profile
```

不带参数时，进入交互式 Step 0 选择模式。

---

## Data Structures & Storage

### Profile

**路径**: `~/.tradingagents/profiles/<name>.json`

**Schema**:
```json
{
  "name": "my_profile",
  "created_at": "2026-05-10T14:30:22",
  "config": {
    "analysts": ["market", "news"],
    "research_depth": 3,
    "llm_provider": "openai",
    "backend_url": null,
    "shallow_thinker": "gpt-5.4-mini",
    "deep_thinker": "gpt-5.4",
    "google_thinking_level": null,
    "openai_reasoning_effort": "medium",
    "anthropic_effort": null,
    "output_language": "Chinese"
  }
}
```

### Watchlist

**路径**: `~/.tradingagents/watchlists/<name>.txt`

**格式**: 每行一个 ticker，支持 `#` 注释和空行。

```
# 科技股
AAPL
MSFT
GOOGL
NVDA

# 新能源
TSLA
```

**加载逻辑**: 读取文件 → 过滤空行和注释行 → `strip()` 每个 ticker → 返回 `list[str]`。

---

## Interaction Flow

### Step 0: 选择运行模式

```
========================================
       TradingAgents CLI
========================================

[1] 批量扫描 Watchlist
[2] 查询自选股票（支持单只或多只，逗号分隔）
```

---

### 路径 A：批量扫描 Watchlist

**Step A1: 选择 Watchlist**
```
[1] tech_stocks.txt  (AAPL, MSFT, GOOGL, NVDA)
[2] a_share.txt      (000001.SZ, 600036.SS, ...)
[3] Import from file...
Select watchlist:
```

**Step A2: 选择 Profile**
```
[1] my_profile       (OpenAI, gpt-5.4, 2 analysts, Deep, Chinese)
[2] aggressive       (xAI, grok-3, 4 analysts, Deep, English)
[3] Create new profile...
Select profile:
```

> 若用户没有已保存的 Profile，自动进入"创建新 Profile"流程（走一遍 analysts、depth、provider、models 等选择）。

**确认并启动**：
```
即将分析 4 只股票，使用 profile: my_profile
输出语言: Chinese  |  自动保存: Yes  |  自动翻译: Yes
按 Enter 开始，或 Ctrl+C 取消...
```

进入 Batch Dashboard，后续零交互。

---

### 路径 B：查询自选股票

**Step B1: 输入股票代码**
```
Enter ticker symbol(s), comma-separated:
> AAPL,MSFT,GOOGL
```

系统检测到逗号分隔的多只股票：
```
检测到 3 只股票，将使用批量模式运行。
是否保存这批股票到 Watchlist 以便复用？ [y/N]
Watchlist name: [custom_20250510]
```

然后继续 Step 2-7（analysis date、output language、analysts、research depth、LLM provider、thinking agents），与现有流程一致。

- **若只有 1 只股票**：走现有完整单只流程（含 Live 面板、结束后的保存/显示提示）。
- **若 >=2 只股票**：进入 Batch Dashboard 无人值守模式。

**批量完成后提示**：
```
========================================
       Batch Complete
========================================

Total: 3  |  Success: 3  |  Failed: 0
Reports: reports/batch_20250510_143022/
Summary: reports/batch_20250510_143022/batch_summary.md

是否将当前配置保存为 Profile？ [Y/n]
Profile name: [my_config]
```

---

## Batch Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Batch: watchlist_tech_stocks  |  Profile: my_profile            │
│ Progress: 3 / 10  |  Current: NVDA  |  Elapsed: 42:18           │
├──────────────────────────────┬──────────────────────────────────┤
│         Progress             │           Messages               │
│  Team          Agent    Status│  Time    Type   Content          │
│  Analyst Team  Market   ✓     │  14:32   Agent  NVDA technical.. │
│                Social   ✓     │  14:33   Tool   get_news: NVDA   │
│                News     ●     │  14:33   Agent  Based on recent..│
│                Fund.    ○     │                                  │
│  Research Team Bull     ○     │                                  │
│                Bear     ○     │                                  │
│                Manager  ○     │                                  │
│  Trading Team  Trader   ○     │                                  │
│  Risk Mgmt     Aggres.  ○     │                                  │
│                Neutral  ○     │                                  │
│                Conserv. ○     │                                  │
│  Portfolio     Manager  ○     │                                  │
├──────────────────────────────┴──────────────────────────────────┤
│  Current Report: Market Analysis                                │
│  [NVDA内容摘要...]                                               │
└─────────────────────────────────────────────────────────────────┘
Status: Agents 2/9 | LLM: 23 | Tools: 41 | Tokens: 12.3k↑ 8.7k↓
Completed: 2 | Failed: 0 | Remaining: 7
```

**关键特性**：
- Header 增加批次信息：`Batch: <watchlist_name>`、`Profile: <profile_name>`、`Progress: N/M`。
- 单只股票完成后，自动重置所有 agent 状态为 pending，无缝切换到下一只。
- Footer 显示批次统计：`Completed | Failed | Remaining`。

---

## Error Handling

| 场景 | 行为 |
|---|---|
| ticker 无效（如 resolve 失败） | 记录到 `failures.log`，跳过该股票，继续下一只 |
| API 超限 / 网络错误 | 重试 1 次，仍失败则记录并跳过 |
| LLM 调用失败 | 回退到 free-text（现有逻辑），若仍失败则该 agent 用空结果，继续后续节点 |
| 用户 Ctrl+C 中断 | 优雅退出，输出已完成的汇总表格。已完成的股票不重新跑（通过检测输出目录存在性） |

---

## File Output Specification

### 批量根目录结构

```
reports/
└── batch_20250510_143022/           # 批次根目录
    ├── batch_summary.md             # 汇总报告
    ├── failures.log                 # 失败记录
    ├── AAPL/
    │   ├── complete_report.md
    │   ├── 1_analysts/
    │   ├── 2_research/
    │   ├── 3_trading/
    │   ├── 4_risk/
    │   ├── 5_portfolio/
    │   └── *_CN.md                  # 翻译后的中文报告
    ├── MSFT/
    │   └── ...
    └── NVDA/
        └── ...
```

### `batch_summary.md` 格式

```markdown
# Batch Analysis Report
| Ticker | Company | Rating | Entry | Stop | Size | Status |
|--------|---------|--------|-------|------|------|--------|
| AAPL   | Apple   | Buy    | 210   | 200  | 5%   | ✅     |
| MSFT   | Microsoft | Hold | —     | —    | —    | ✅     |
| NVDA   | NVIDIA  | Overweight | 140 | 130 | 3% | ✅     |
| TSLA   | —       | —      | —     | —    | —    | ❌ Invalid ticker |
```

终端最终输出一张同样的 Rich Table。

---

## Implementation Notes

- **向后兼容**：现有 `analyze` 的单只股票体验完全不变；仅在不带参数时新增 Step 0 模式选择。
- **职责分离**：批量相关逻辑全部抽离到 `cli/batch_*.py`，不污染现有 `main.py` 的单只股票流程。
- **编码规范**：所有文件 I/O 使用 `encoding="utf-8"`；所有新增函数使用 Type Hints。
- **预留扩展**：`BatchRunner` 内部维护 `completed_tickers: set[str]`，为未来 checkpoint 恢复预留接口。

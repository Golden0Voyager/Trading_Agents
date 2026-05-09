# 商汤 SenseNova DeepSeek 免费模型集成指南

> **适用场景**：在 TradingAgents 框架中使用商汤 SenseNova 平台提供的 DeepSeek 免费模型（DeepSeek-R1 / DeepSeek-V3-1 / Distill 系列）。
> **文档性质**：实战踩坑记录 + 最佳实践，供后续项目参考。

---

## 1. 商汤 SenseNova 平台简介

商汤科技通过 SenseNova 平台提供 DeepSeek 系列模型的 **OpenAI 兼容 API**，无需翻墙即可访问。

**API 端点**：`https://api.sensenova.cn/compatible-mode/v2`

### 1.1 免费模型清单（截至 2026-05-09）

| 模型名称 | 类型 | 上下文长度 | 备注 |
|---------|------|-----------|------|
| `DeepSeek-R1` | 推理模型 | 8K | **限时免费至 2026-08-09**，原生推理能力最强 |
| `DeepSeek-V3-1` | 通用对话 | 32K | **限时免费至 2026-08-09**，通用任务 |
| `DeepSeek-V3` | 通用对话 | 32K | **限时免费至 2026-08-09**，V3-1 的上一个版本 |
| `DeepSeek-R1-Distill-Qwen-32B` | 蒸馏推理 | 8K | **永久免费**，平衡推理 |
| `DeepSeek-R1-Distill-Qwen-14B` | 蒸馏推理 | 32K | **永久免费**，轻量推理 |

### 1.2 速率限制

| 指标 | 限制 |
|------|------|
| QPS | 1 |
| RPM | 6 |
| TPM | 128K |

**影响**：并行运行的 researcher agent 容易被限流，建议：
- 研究深度（debate rounds）不要设太高
- 使用 `deepseek-reasoner` 做 trader/manager（串行），而非并行的 researcher

---

## 2. 快速接入

### 2.1 获取 API Key

1. 访问 [SenseNova 开放平台](https://platform.sensenova.cn/)
2. 注册/登录商汤账号
3. 进入"API 密钥管理"创建 Key
4. 格式：`sk-xxxxxxxxxxxxxxxx`

### 2.2 环境变量配置

```bash
export SENSENOVA_API_KEY="sk-your-key-here"
```

或在项目根目录创建 `.env`：

```bash
cp .env.example .env
# 编辑 .env，填入 SENSENOVA_API_KEY
```

### 2.3 CLI 中选择商汤

```bash
uv run tradingagents
```

在 LLM Provider 选择界面中选择 **"商汤 SenseNova"**，随后选择 quick/deep 模型即可。

### 2.4 Python API 调用

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "sensenova"
config["quick_think_llm"] = "DeepSeek-V3-1"      # 通用任务
config["deep_think_llm"] = "DeepSeek-R1"         # 推理任务（trader/manager）

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("600901.SS", "2026-05-09")
print(decision)
```

---

## 3. 技术集成要点

### 3.1 OpenAI 兼容层

SenseNova 使用 OpenAI 兼容协议，因此在框架中通过 `ChatOpenAI` 接入即可。

关键配置（位于 `tradingagents/llm_clients/openai_client.py`）：

```python
_PROVIDER_CONFIG = {
    # ... 其他提供商 ...
    "sensenova": ("https://api.sensenova.cn/compatible-mode/v2", "SENSENOVA_API_KEY"),
}
```

**注意**：SenseNova 的 DeepSeek-R1 具有 **thinking-mode**（reasoning_content），因此需要使用 `DeepSeekChatOpenAI` 子类，而非基础的 `NormalizedChatOpenAI`。

### 3.2 Thinking-Mode 往返（核心踩坑点）

DeepSeek-R1 的响应中携带 `reasoning_content` 字段，该字段**必须在下一轮请求中作为 assistant message 的一部分回传**，否则 API 返回 **400 Bad Request**：

```json
{
  "error": {
    "message": "reasoning_content is required for assistant message with tool_calls in thinking mode"
  }
}
```

#### 问题根因

TradingAgents 使用 `ChatPromptTemplate` + `MessagesPlaceholder` 构建多轮对话。`ChatPromptTemplate` 在每次调用时会**重新创建消息对象**，而 langchain-openai 的 `to_messages()` 实现会**丢弃 `additional_kwargs`**（其中包含 `reasoning_content`）。

这导致第二轮请求中，assistant message 的 `reasoning_content` 丢失，API 拒绝服务。

#### 解决方案：Sidecar Cache

由于 `message.id` 在 `ChatPromptTemplate` 的转换过程中被保留，我们以 `message.id` 为 key，在 `DeepSeekChatOpenAI` 中维护一个 sidecar 缓存：

```python
class DeepSeekChatOpenAI(NormalizedChatOpenAI):
    _reasoning_cache: dict[str, str] = {}
    _REASONING_CACHE_MAX = 2000

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        outgoing = payload.get("messages", [])
        for message_dict, message in zip(outgoing, _input_to_messages(input_)):
            if message_dict.get("role") != "assistant":
                continue
            if "reasoning_content" in message_dict:
                continue
            # 1) sidecar cache keyed by message id
            msg_id = getattr(message, "id", None)
            if msg_id and msg_id in self._reasoning_cache:
                message_dict["reasoning_content"] = self._reasoning_cache[msg_id]
                continue
            # 2) original AIMessage additional_kwargs (direct invoke path)
            if isinstance(message, AIMessage):
                reasoning = message.additional_kwargs.get("reasoning_content")
                if reasoning is not None:
                    message_dict["reasoning_content"] = reasoning
                    continue
            # 3) fallback: assistant with tool_calls needs a non-empty field
            if message_dict.get("tool_calls"):
                message_dict["reasoning_content"] = "..."
        return payload

    def _create_chat_result(self, response, generation_info=None):
        chat_result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump(...)
        for generation, choice in zip(
            chat_result.generations, response_dict.get("choices", [])
        ):
            reasoning = choice.get("message", {}).get("reasoning_content")
            if reasoning is not None:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
                msg_id = getattr(generation.message, "id", None)
                if msg_id:
                    cache = self._reasoning_cache
                    cache[msg_id] = reasoning
                    while len(cache) > self._REASONING_CACHE_MAX:
                        cache.pop(next(iter(cache)))
        return chat_result
```

**关键设计决策**：
- `sensenova` 必须使用 `DeepSeekChatOpenAI`（与 `deepseek` 官方 provider 共用同一子类）
- Fallback 使用 `"..."` 而非空字符串，因为 API 拒绝空字符串
- 缓存上限 2000 条，防止内存无限增长

### 3.3 Structured Output 限制

`DeepSeek-R1`（对应 `deepseek-reasoner`）**不支持 `tool_choice`**，因此无法使用 function-calling 做结构化输出。

在 `DeepSeekChatOpenAI.with_structured_output` 中已做保护：

```python
def with_structured_output(self, schema, *, method=None, **kwargs):
    if self.model_name == "deepseek-reasoner":
        raise NotImplementedError(
            "deepseek-reasoner does not support tool_choice; structured output is unavailable."
        )
    return super().with_structured_output(schema, method=method, **kwargs)
```

框架中的 `tradingagents/agents/utils/structured.py` 会自动捕获此异常并回退到 free-text generation，无需额外处理。

### 3.4 代理兼容性

如果运行环境使用了 SOCKS 代理（如 Clash Verge），需要安装：

```bash
uv pip install socksio
```

否则会出现：

```
ImportError: Using SOCKS proxy, but the 'socksio' package is not installed
```

---

## 4. 模型分配建议

基于免费模型的特性，推荐以下分工：

| Agent 角色 | 推荐模型 | 理由 |
|-----------|---------|------|
| **Researcher** (并行) | `DeepSeek-V3-1` | 通用对话，速度快，限时免费 |
| **Researcher** (备选) | `DeepSeek-R1-Distill-Qwen-14B` | 永久免费，32K 上下文，轻量推理 |
| **Trader / Manager** | `DeepSeek-R1` | 原生推理最强，适合做最终决策 |
| **Portfolio Manager** | `DeepSeek-R1` | 需要强推理能力做风险评估 |

**不推荐**用 `DeepSeek-R1` 做并行的 Researcher，因为：
1. 1QPS / 6RPM 的限流会导致频繁等待
2. reasoning_content 的往返开销更大

---

## 5. 常见问题排查

### 5.1 400 Bad Request — reasoning_content missing

**症状**：第二轮 tool call 时抛出 `BadRequestError: 400`

**根因**：thinking-mode 的 reasoning_content 未在请求中回传

**解决**：确认 `sensenova` 在 `openai_client.py` 中路由到 `DeepSeekChatOpenAI`：

```python
chat_cls = DeepSeekChatOpenAI if self.provider in ("deepseek", "sensenova") else NormalizedChatOpenAI
```

### 5.2 429 Rate Limit Exceeded

**症状**：频繁遇到 `RateLimitError`

**解决**：
- 降低 `max_debate_rounds`（建议 ≤ 2）
- Researcher 使用非推理模型（V3-1 / Distill）
- 避免同时运行多个 ticker 的分析

### 5.3 中文公司名称幻觉

**症状**：Market Analyst 报告标题写成错误的股票名称（如"江苏有线"）

**根因**：Prompt 中只有 ticker 代码，模型自行推断中文名称

**解决**：使用 `ticker_resolver.py` 预先通过 yfinance 获取 `longName`，注入到所有 agent 的 prompt 中。详见项目中的 A-Share Ticker Resolver 实现。

---

## 6. 最佳实践清单

- [ ] 始终通过 `DeepSeekChatOpenAI` 子类接入 SenseNova（不要直接用 `ChatOpenAI`）
- [ ] 如果环境有 SOCKS 代理，提前安装 `socksio`
- [ ] 用 `DeepSeek-V3-1` 做 quick-thinking（并行），`DeepSeek-R1` 做 deep-thinking（串行决策）
- [ ] 监控 Rate Limit，必要时降低 debate rounds
- [ ] 中文 A 股场景下，配合 `ticker_resolver.py` 使用，避免公司名称幻觉
- [ ] 注意限时免费截止日期（2026-08-09），届时可能需要切换至永久免费的 Distill 模型

---

## 7. 参考链接

- [SenseNova 开放平台](https://platform.sensenova.cn/)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs/)
- 本项目代码：
  - `tradingagents/llm_clients/openai_client.py` — 客户端实现
  - `tradingagents/llm_clients/model_catalog.py` — 模型列表
  - `tradingagents/ticker_resolver.py` — A 股解析器（辅助功能）

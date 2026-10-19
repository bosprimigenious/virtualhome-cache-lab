# e39267d8 接入手册

直接检查和修改代码，不要只输出计划。先做客户端与测试，再接真实接口；用户决定暂不配置服务，因此当前只实现接口、提示、解析与本地 HTTP 测试，不发真实请求。保留失败用例和日志，不跳过失败测试。

## 文件责任

新增 `cachelab/model.py`、`tests/test_model.py`，扩展 `cachelab/judge.py` 与判分正反例。主线已实现 `backend.py`、`replay.py`、`experiment.py` 和 `evaluate.py`；变更共享事件字段前同步契约，不另写平行缓存循环。

`ModelClient(base_url, model, api_key_env=None, timeout=60, temperature=0, max_tokens=256)` 需提供：

```python
client.configuration()  # JSON dict，可复现配置、提示全文与哈希；不含密钥
client.generate(kind, target, graph)  # 仅收到查询和原图，永远不会收到 gold
```

`kind` 为 location/summary，location 的 target 是类别名，summary 为 None。模型输入由回放层统一提供完整图，fine/coarse 不得修改提示或可见状态，否则粒度对照失去控制。

## 每次调用的返回值

```python
{
    "answer": {"object": "plate", "container": None, "room": "kitchen"},
    "raw_output": "原始响应文本",
    "latency_seconds": 0.123,
    "error": None,
    "error_type": None,
    "usage": {},
    "finish_reason": "stop",
}
```

location 输出 object/container/room；summary 输出课程 salient 类别到状态描述或 null 的字典。接口应严格校验 JSON/schema 并保留原始文本。失败必须 answer=None、error 为稳定非空错误码、error_type 为 output/transport/configuration/backend 之一。耗时必须有限非负。不能以 gold 或 `{}` 补成成功，也不能在解析层偷偷追加重试；若要支持重试需先为每次真实请求增加单独日志和调用计数。

可附服务返回的 response_model/system_fingerprint；若服务不提供版本证据则记录未知，不以别名冒充权重版本。密钥只能通过指定环境变量读取。拒绝含凭据的 URL，缺失指定密钥在请求前报错；错误日志不得输出 header、密钥或含秘密的服务错误正文。

## 评分版本与数据问题

当前 `judge.py` 只提供用于离线集成的结构化判分基线，摘要状态词序可交换。扩展同义词或自然语言语义比较时必须新增正反例并变更 VERSION。复算会拒绝源配置与当前评分版本不一致；重判需新增版本化证据，不能把旧版本标签套在新结果上。

原 gold 忽略 HOLDS，room 用双向 IN 栈遍历且受边顺序影响，container 取最后一条指向非房间的 IN/ON。不要静默“修复” gold。课程包 60 文件/40 清单任务、5 处状态不连续仍待老师确认；正式报告必须保留限制。

## 验收顺序

1. 标准库本地 HTTP 服务测试正常响应、缺字段、坏 JSON、截断、HTTP 失败、连接失败和超时；验证密钥不泄漏、失败无 gold 回退。
2. 运行 `uv run python -m cachelab.acceptance --output-dir results/teammate-acceptance-001`，确认不破坏缓存/日志契约。
3. 用户决定启动后，再用开发手册中的单会话/单任务真实冒烟命令；保存配置、原始响应和错误。真实冒烟通过才运行全清单六组对照。
4. 在自己的分支开 PR，附本地测试和实际运行目录；bosprimigenious 复跑后合并。未跑真实服务就明确写未跑，不把 HTTP test double 当成真实小模型。

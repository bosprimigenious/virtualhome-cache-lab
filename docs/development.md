# 开发与实验手册

## 状态和输入

**本分支已实现 bosprimigenious 的离线开发范围。** 依赖、缓存、事件接口、复算和聚合验收可执行；真实接口仍按用户决定暂缓配置，模型客户端由 e39267d8 按 [后端契约](backend-contract.md) 接续。主分支在 PR 合并前仍可能是旧基线。

课程完整实验 **NOT READY**。OpenAI 兼容接口的地址、模型名和鉴权要求尚待提供；没有实际调用记录之前，不把接口代码、Mock 结果或测试通过写成真实模型验证通过。不安装 Ollama，不自动购买服务或调用付费接口。

数据来自本地课程 ZIP，不在公开仓库再分发。目前发现 60 个任务文件，原 `sessions.json` 的 5 个会话只引用 40 个任务，另有 5 处会话内状态不连续。正式划分和报告模板尚待老师核实。按照原清单回放并保存差异，不自行补成 60 个任务。先核实划分再补任务；反过来会把独立世界拼接成连续状态，污染跨任务缓存结论。

本手册对应已实现的 `cachelab.experiment` 事件实验入口。历史 `cachelab.run` 与旧 Mock 基线不与新入口直接混合。新入口默认在不连续边界清缓存，历史入口未执行这项处理。

## 两人责任与交接

| 负责人 | 主责范围 | 向对方交付的证据 |
|---|---|---|
| `bosprimigenious` | 状态依赖、缓存策略、模型输入与依赖分离、事件记录接口、集成及验收 | 边界与依赖测试、固定输入六组运行、逐事件审计记录 |
| `e39267d8` | 模型提示、结构化输出、语义判分设计、评测、实验分析及报告 | 提示版本与输出契约、真实响应失败案例、离线重算结果、报告对应事件 |

主责不表示互相绕开接口。先约定事件字段和模型输出结构，再并行开发：前者用确定性后端验证缓存，后者用已保存的响应和事件验证解析及判分。每个 PR 由另一人复跑关键命令。两人各自分支，不直接修改对方分支，流程见 [CONTRIBUTING](../CONTRIBUTING.md)。

语义判分是成员 `e39267d8` 的后续任务；当前结构化字段的大小写、空白归一化比较不等于任意自然语言语义判分。增加规则时必须版本化评分规则、加入正反样例，并在同一批旧事件上重算；不得以放宽规则的方式隐去原错误。

## 当前可执行的基线

以下命令对应当前已发布代码，可立即执行。教师 ZIP 使用本机路径，不上传。

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m cachelab.run --course-zip /absolute/path/virtualhome_cache_lab.zip --output results/baseline-001.json
```

当前离线范围的统一验收：

```bash
uv run python -m cachelab.acceptance --output-dir results/acceptance-001
uv run python -m cachelab.acceptance --course-zip /absolute/path/virtualhome_cache_lab.zip --output-dir results/course-acceptance-001
```

第一个命令使用自建场景；第二个核验本地教师包。目录必须不存在。`acceptance.json` 的 READY 仅对应 `bosprimigenious_offline_integration`，不表示真实模型或课程完整验收通过。CI 在 Python 3.11/3.14 上运行同一门禁并保留执行产物。

## 环境和最小回放

在仓库根目录运行。先确认工具存在；Python 需 3.11+，依赖和执行环境跟随 `uv.lock`。

```bash
command -v git
command -v uv
command -v python3
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m cachelab.experiment --help
uv run python -m cachelab.evaluate --help
```

将路径替换为本机真实路径。每次使用新的输出目录，不覆盖已留存的证据。

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend mock \
  --boundary-policy reset \
  --output-dir results/mock-smoke-001 \
  --session-limit 1 --task-limit 1
uv run python -m cachelab.evaluate results/mock-smoke-001
```

Mock 直接使用 gold，只验证数据回放、失效逻辑、日志和汇总，不支持模型准确率、真实推理耗时或加速收益结论。先跑小范围再跑全量，防止把解析或输入错误放大到所有策略；完整命令去掉两个 limit 参数。

## 接入 OpenAI 兼容接口

**此节是真实模型的后续接线契约，当前不执行。** 队友先实现 `cachelab.model.ModelClient` 并通过后端边界测试；客户端缺失时 CLI 预检报错，不导入保存在本机的草稿。用户再决定启动并提供服务地址、完整模型名、鉴权要求及可调用范围，之后才执行真实请求。确认服务支持当前适配器的 Chat Completions 路径与消息格式；不能仅凭“OpenAI 兼容”判断所有参数可用。`--base-url` 使用 API 根地址，例如服务给出的 `/v1` 地址，不填写某次请求的完整路径。

远端密钥仅通过环境变量传入，不写到命令参数、文档、Git、事件日志或 `config.json`。在本地私密会话中设置 `VHCACHE_API_KEY`，避免把实际值贴进共享终端记录。`--api-key-env` 的值是变量名。仅确实无需鉴权的服务可不设置该变量；缺少远端鉴权信息时不要反复试请求。

以下 `API_BASE_URL` 和 `API_MODEL` 是收到信息后本地设置的值，命令本身不包含凭据。

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend openai --base-url "$API_BASE_URL" --model "$API_MODEL" \
  --api-key-env VHCACHE_API_KEY \
  --max-tokens 256 --timeout 60 \
  --boundary-policy reset \
  --session-limit 1 --task-limit 1 \
  --output-dir results/openai-smoke-001
uv run python -m cachelab.evaluate results/openai-smoke-001
```

先检查响应能解析、失败逐条可见、模型没有收到 gold、配置已记录完整模型名与提示版本，再去掉 limit 跑全策略。HTTP 错误、超时、模型错误和解析错误都进入实验失败分析，不用 gold 替换响应，不把失败记成正确。实际接口不可用时保留失败产物并报告 NOT READY，不回退 Mock 冒充真模型。

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend openai --base-url "$API_BASE_URL" --model "$API_MODEL" \
  --api-key-env VHCACHE_API_KEY \
  --max-tokens 256 --timeout 60 \
  --boundary-policy reset \
  --output-dir results/openai-full-reset-001
uv run python -m cachelab.evaluate results/openai-full-reset-001
```

## 实验控制与边界

一次运行包含六组：`none`、`fixed k=3/5/10`、`dependency fine/coarse`。各组必须使用同一数据划分、回放顺序、模型、提示和解码配置。fine/coarse 只改变缓存依赖指纹，实际模型输入保持相同；否则比较混入模型可见信息差异。

跨会话清空缓存；`--boundary-policy reset` 在已检测到的不连续任务边界再次清空缓存，是主实验默认。`preserve` 只作为边界敏感性分析，放在单独输出目录，不能和 reset 合并后报告。它保留原清单的不连续影响，不能被解释为连续世界性能。coarse 使用全图，不能与教师参考实现仅看房间标识的 coarse 混称。

## 标注与依赖协议

教师原 gold 对 room 使用双向 IN 的栈遍历、忽略 ON，结果受输入边顺序影响；container 取最后一条指向非房间对象的 outgoing IN/ON。location 与 summary 均选择同类最小 id，原 gold 忽略 HOLDS。指导书强调抓取会改变位置，与该实现存在语义差异。本轮真实提示遵循原 gold，不静默修改；修正标注应作为新版本数据协议单独实验。

新入口的依赖指纹保留边和 states 顺序，并覆盖双向 IN 路径；到 Rooms 节点即停止反向扩展，避免把同房间所有对象都纳入位置依赖。模型始终看同一份原始完整状态图，依赖不是模型输入裁剪。历史入口仍保留原依赖协议，不使用新结果替换旧证据。

## 产物和复算

| 文件 | 用途与检查 |
|---|---|
| `config.json` | 后端、模型、端点、提示版本、解码参数、边界策略和范围；不得含密钥 |
| `data-audit.json` | ZIP SHA-256、引用任务与未引用任务、状态不连续边界；实际评测范围需同时看配置中的 limit |
| `events.jsonl` | 原始逐事件证据；保留策略、会话/任务/步骤、查询、复用或重算、失效原因、预测、gold 标签、错误与耗时 |
| `run-state.json` | 是否遍历完成、异常类型与整个运行的 wall_seconds；中断不是成功 |
| `summary.json` | 首次运行生成的策略汇总；只能以原始事件和配置为依据 |
| `comparison.csv` / `comparison.md` | 六组指标对照；明确 Mock 与真模型、复用分母和错误定义 |

`cachelab.evaluate` 从事件重算汇总，不调用模型，不覆盖原始日志。配置保存预期身份及 gold/input/dependency 哈希，run-state 保存日志与配置摘要；复算验证这些绑定、缓存来源、策略判定、重置链、事件 schema 和评分版本。不把摘要当作防止所有文件被同时恶意重写的数字签名。复算输出文件名以命令实际输出为准。对比复算指标和首次汇总；不一致先定位事件与计数规则，不手改结果补齐。

汇总同时给出全部请求与 location/summary 分项结果。`stale_reuse` 是复用答案与当前 gold 不等价，包含模型原生错误；`state_stale_reuse` 只计 gold 已变化且当前复用答案仍错；`model_error_reuse` 计 gold 未变化但缓存创建时答案已错。`missed_invalidation` 计 gold 已变化却复用，即使偶然答对也仍是一次失效漏判。`false_invalidation` 计已有条目、gold 未变却被 fixed/dependency 重算；没有已有条目的 miss 与边界清空不计入。`invalidation_accuracy` 为正确失效加正确保留除以已有条目判定机会，none 不适用。

`real_llm_latency_seconds` 是 HTTP 模型调用墙钟总耗时，包含传输与失败等待，不是服务端纯计算时间；`request_wall_seconds` 包含依赖处理和调用，`run-state.wall_seconds` 包含回放、调用、日志和磁盘开销，不包含前置数据加载/配置生成和后续离线复算。模型版本只记录服务实际返回的 model/system_fingerprint（若提供），不把字符串名称当作已校验权重版本。

`COMPLETED_WITH_MODEL_ERRORS` 表示遍历完成但发生模型调用/解析错误；`INCOMPLETE` 包括截断、重复请求或计数不闭合。两者实验/复算 CLI 均退出 2。原始事件以策略+会话+任务+步+查询类型+目标作唯一键，缺失或重复不能仅靠总数通过验收。

核对以下证据，而非只看退出码：

1. 六组请求数和输入范围一致；`decision_calls + reuse_events == requests`，复用分类之和与复用总数一致。
2. fresh 调用的模型错误、解析错误独立计数。缓存答案错误不能自动全部归为过期：创建时已错与后来状态变化导致错误需分别分析，无法识别的情况明确标记。
3. 决策模型调用次数、调用耗时、端到端耗时分别报告；复算判分的额外模型调用为 0。Mock 耗时不能写成 LLM 推理耗时。
4. 检查新增/删除节点、抓取关系变化、持有者移动、容器移动、无关状态变化、同名对象、状态恢复、跨会话及不连续边界。
5. 每个重要结论引用策略、会话/任务/步骤及事件字段；至少分析抓取、无关变化、固定窗口失效三个案例。未覆盖的案例写明未验证。

原始事件可能含教师轨迹、答案和模型响应。公开仓库只提交代码、脱敏配置及确有再分发权限的汇总；ZIP、课件、凭据、未经授权的原始日志留在本地。公开汇总前人工检查是否泄露原数据或接口内部地址。

## 完成门禁

单元测试与 Mock 回放通过，仅说明本地机制可复现。完整课程验收同时要求：正式数据划分和连续性处置确认、真实模型六组全范围运行、事件独立重算一致、缓存错误与模型错误分离、粒度与 k 消融、两人交叉复跑、按老师模板完成报告。任何一项缺失，完整实验仍为 **NOT READY**。阶段状态和下一项工作记录在 [计划](plan.md)，实际执行结果写入 [验收记录](verification.md)。

# 两人开发与实验计划

**bosprimigenious 的离线开发阶段已实现并自验通过。** 真实接口暂不配置；模型适配、提示、扩展判分与报告由 e39267d8 接续。以下事件实验和复算命令在本代码分支可执行，真实模型命令仍需队友客户端及用户服务信息。

完整课程实验 **NOT READY**。计划按证据推进，不预设完成日期。真实接口地址、模型名及鉴权要求待用户提供，正式任务划分和报告模板待老师确认；这些信息未到齐时继续开发、测试和 Mock 审计，不制造真模型结果。

## 任务看板

| 阶段 | 主责 | 协作复核 | 当前状态 | 开始条件 |
|---|---|---|---|---|
| 0：离线基线 | bosprimigenious | e39267d8 复跑 | 初版已发布，待队友复跑 | 仓库可访问、取得本地教师 ZIP |
| 1：依赖与事件接口 | bosprimigenious | e39267d8 | 本分支实现与聚合门禁通过；待队友复核/合并 | 确认下述事件与判分契约 |
| 2：模型与评分 | e39267d8 | bosprimigenious | 计划中；真实配置暂缓 | 用户提供服务信息并决定启动 |
| 3：对照与消融 | bosprimigenious | e39267d8 | 计划中 | 阶段 1、2 最小链路通过 |
| 4：分析与报告 | e39267d8 | bosprimigenious | 计划中 | 正式数据范围、模板和真实结果齐备 |

阶段 1 的实现已就绪，队友可基于稳定后端契约推进阶段 2 的提示和判分样例；真实调用及阶段 3 有前置依赖。下列任务是建议责任分配，不表示队友已接受邀请或已完成工作。

## 已完成的离线开发

依赖提取、缓存判定、后端契约、逐事件回放、绑定源输入的证据复算、实验 CLI 和聚合验收已提交。44 项测试通过；自建场景及原清单 40 任务的 reset/preserve 两套门禁通过。所有代码提交均在干净 git archive 中逐个运行测试通过。实际失败、修复和计数见 [验证记录](verification.md)。

仍需 e39267d8 接入真实客户端、复核提示/评分并交叉复跑；独立审计不等于队友本人完成验收。正式数据和报告模板确认不由测试替代。

## 阶段 1：冻结接口、建立事件证据

`bosprimigenious` 主责依赖、缓存和事件写入；`e39267d8` 并行确认模型输出结构、提示和评分样例。双方先约定查询输入、预测结构、错误分类与事件字段，互审后继续扩展。

执行：

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend mock --boundary-policy reset \
  --session-limit 1 --task-limit 1 --output-dir results/phase1-mock-001
uv run python -m cachelab.evaluate results/phase1-mock-001
```

产物：测试记录、配置、数据审计、事件日志和六组汇总。门禁：逐事件可定位，失败不吞；fine/coarse 提示相同；gold 仅用于 Mock 或评分，不进入真实决策输入；复算无模型调用且不改原日志。该阶段不能验收真实模型效果。

## 阶段 2：真实小模型最小链路

`e39267d8` 主责提示、响应解析和判分；`bosprimigenious` 负责配置接线、错误记录和集成复核。接口信息未提供前，只能完成适配和本地模拟测试。

收到服务信息后，按 [开发手册](development.md) 设置本地环境变量，运行：

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend openai --base-url "$API_BASE_URL" --model "$API_MODEL" \
  --api-key-env VHCACHE_API_KEY --max-tokens 256 --timeout 60 \
  --boundary-policy reset --session-limit 1 --task-limit 1 \
  --output-dir results/phase2-openai-smoke-001
uv run python -m cachelab.evaluate results/phase2-openai-smoke-001
```

产物：小范围真实响应及逐事件错误、配置与复算记录。门禁：接口实际响应可审计；成功、HTTP/超时和解析失败有明确归属；密钥不进入产物；不以 gold 或 Mock 替代失败。最小链路通过后再扩全量，避免重复支付无效请求或批量产生不可用数据。当前按用户决定暂缓配置；等用户决定启动并提供接口信息后再执行。

## 阶段 3：全范围六组对照与消融

`bosprimigenious` 主责完整运行、依赖边界及 reset/preserve 比较；`e39267d8` 并行进行事件复算、错误归因、粒度和 k 消融分析。

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend openai --base-url "$API_BASE_URL" --model "$API_MODEL" \
  --api-key-env VHCACHE_API_KEY --max-tokens 256 --timeout 60 \
  --boundary-policy reset --output-dir results/phase3-openai-reset-001
uv run python -m cachelab.evaluate results/phase3-openai-reset-001
```

必要时使用同样配置将 `reset` 改为 `preserve`，另存 `results/phase3-openai-preserve-001`，单独评估不连续边界影响。正式数据版本一旦调整必须新增运行，不修改旧产物。先记录数据审计再解释指标；反过来会将数据重置产生的错误归给缓存算法。

产物：六组配置一致的结果、逐事件证据、复算差异检查、至少三个可追踪案例。门禁：计数闭合；明确每个比例分母；缓存错误与创建时模型错误分离；报告真实调用与端到端耗时；fine/coarse 输入相同；未证实收益照实记录。当前正式范围仅原清单 40 个任务，不能写成已评测 60 个。划分未确认前不通过课程完整门禁。

## 阶段 4：交叉复跑与报告

`e39267d8` 主写实验设置、结果、误差分析和局限；`bosprimigenious` 主写方法、复现步骤并检查表格与事件对应。两人各自在自己的分支提交，经另一人复跑后用 PR 合并。

双方至少各自运行测试和事件复算，并核对一段真实模型链路。复用同一套已保存事件复算不产生额外模型调用；若要重新生成真模型结果，先确认服务可调用范围。记录两次模型生成差异，不要求不确定后端逐字一致。

```bash
uv run python -m unittest discover -s tests -v
uv run python -m cachelab.evaluate results/phase3-openai-reset-001
```

产物：实际验收记录、对照表、案例、按老师模板排版的报告、复现配置及公开材料清单。门禁：阶段 1–3 均有现场证据，数据与模板已确认，两人复核留痕，文档不超出实测。没有官方模板时可整理内容草稿，但不能宣称课程提交材料已完成。

## 目前硬阻塞与可继续事项

| 事项 | 当前影响 | 不依赖该事项的工作 |
|---|---|---|
| 接口地址、模型名、鉴权和调用范围待提供 | 真实模型冒烟及全量实验未验证 | 适配器、提示契约、错误用例、Mock 日志与复算 |
| 60 个文件与 40 个清单任务不一致，另有 5 处状态不连续 | 无法宣称完整 60 任务或完全连续世界 | 审计原清单、默认 reset、preserve 单独敏感性分析 |
| 老师报告模板未提供 | 最终提交格式未验收 | 方法、实验、案例和局限草稿 |

每完成一步，将真实命令、退出状态、计数和失败写入验收记录。测试失败或环境问题必须随交接带给下一位，不通过改文字消除阻塞。

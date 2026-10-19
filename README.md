# VirtualHome Cache Lab

机器学习实践训练 · 题目 ③ · 两人小组。研究状态变化下的智能体缓存复用与失效管理。

**bosprimigenious 的离线开发范围已实现并通过聚合验收；课程完整验收 NOT READY。** 本分支包含依赖、缓存、事件日志、证据复算和集成门禁。真实模型适配、提示与扩展判分由 e39267d8 接续，真实接口按用户决定暂不配置。

## 一条命令验收

Python 3.11+，标准库实现，使用 uv 锁文件：

```bash
uv sync --locked
uv run python -m cachelab.acceptance --output-dir results/acceptance-001
```

默认使用本项目自建的小场景，不需要教师 ZIP、模型、密钥或联网。聚合运行单元测试、reset/preserve 对照、不可变复算、故障注入和日志篡改检查。任一门禁失败返回非零；完整执行记录保存在新输出目录，重复目录会被拒绝。

本地课程包可用时运行：

```bash
uv run python -m cachelab.acceptance \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --output-dir results/course-acceptance-001
```

只运行实验或离线复算：

```bash
uv run python -m cachelab.experiment \
  --course-zip /absolute/path/virtualhome_cache_lab.zip \
  --backend mock --boundary-policy reset --output-dir results/mock-001
uv run python -m cachelab.evaluate results/mock-001
```

## 已实现内容

- 无缓存、固定 k=3/5/10、依赖 fine/coarse 六组策略，模型输入独立于缓存依赖粒度。
- 位置依赖覆盖双向 IN、边顺序、IN/ON 祖先、HOLDS 与持有者位置；摘要/粗粒度使用全图。
- 会话内跨任务缓存、跨会话清空，已检测到的不连续边界默认 reset；preserve 单独作为敏感性分析。
- 每次请求记录输入/依赖哈希、gold、答案/错误、失效原因、缓存来源事件、创建步和耗时。失败不缓存、不回退 gold。
- 复算绑定输入清单、配置和日志 SHA-256，核对缓存来源、实际判定、重置链与评分版本，输出 JSON/CSV/Markdown 汇总。
- 后端以 `Backend.generate/configuration` 接入；模型客户端尚未合入。`--backend openai` 在客户端缺失时明确报错，不会自动安装或调用服务。

原包虽然有 60 个任务文件，原清单只引用 40 个，另有 5 处会话内状态不连续。不能宣称已评测 60 个任务或完全连续世界。原 gold 对抓取的语义与指导书有偏差，本轮原样评估并披露，不静默改标注。

Mock 从 gold 读答案，不能作为模型准确率或加速比证据。历史入口 `cachelab.run` 保留用于复现；新依赖/评分/边界协议不同，不直接混合比较新旧基线。课程 ZIP、课件、未经授权的轨迹、gold 和原始日志不上传。MIT 适用于自行编写的代码与文档。

## 分工与文档

| 成员 | 主责 | 当前交付 |
|---|---|---|
| bosprimigenious | 依赖、缓存、事件日志、集成验收 | 本分支离线实现和聚合验收；真实集成待模型适配 |
| e39267d8 | 模型提示、结构化判分、评测分析、报告 | 按后端契约接续，真实配置暂缓 |

- [开发手册](docs/development.md)：实际命令、产物、指标与边界。
- [后端接入与交接](docs/backend-contract.md)：队友可直接实现的接口与验收要求。
- [阶段计划](docs/plan.md)：状态、前置条件和分工。
- [协作约定](CONTRIBUTING.md)：独立分支、PR 互审与复跑。
- [验证记录](docs/verification.md)：实际输出、失败修复与未验证事项。

官方环境见 [VirtualHome](https://github.com/xavierpuigf/virtualhome)。当前回放课程风格轨迹，未安装或验证图形模拟器。

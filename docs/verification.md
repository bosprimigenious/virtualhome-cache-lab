# 首次验证记录

日期：2026-10-19（Asia/Shanghai）。状态：离线起步阶段已验证；课程完整验收 NOT READY。

## 实际执行

1. 环境探测：git、gh、python3、uv 可用；GitHub 当前账号 bosprimigenious。课程根目录 git rev-parse 提示不是仓库，这是现场状态而非项目失败；随后在独立子目录初始化。未检测到 Ollama，未调用真实或付费模型。
2. 数据检查：教师 ZIP 有 60 个 task 文件，sessions.json 只引用 40 个（5×8）；20 个未引用，详见基线 JSON。另检查出 5 处会话内任务初始图与前任务末图不一致（task_0004/0012/0020/0028/0036），按原包顺序保留并记录，不把它作为完全连续世界实验。固定窗口错误可能包含数据重置影响，不能全部归因于缓存算法。独立审计发现并复核的结果与主线一致。指导书写 5×12，待向老师核对。原 README 与 reference 对 fine 策略的调用次数描述也不一致，不使用这些数字作为本项目实测。
3. uv lock 与 uv sync --locked：成功；环境 Python 3.11.15，无第三方依赖。
4. uv run python -m unittest discover -s tests -v：8/8 通过，覆盖新增/删除抓取边、无关变化、固定窗口边界、节点出现、祖先移动、顺序不变、跨会话清缓存和严格判分。
5. 六组离线运行：每组 320 次请求，原清单的 5 会话 / 40 任务；完整计数见 ../benchmarks/mock-baseline.json。none 320 次调用；fixed k=3/5/10 分别 124/84/58 次；dependency fine/coarse 分别 240/250 次。fine 80 次复用均匹配 gold，coarse 70 次复用均匹配 gold；固定 k=5 错误复用 106/236。

## 没验证的内容

真实小语言模型、真实推理延迟、增量失效性能、完整 60 任务划分、课程包原有测试（本项目是独立实现，不冒充补全教师接口）、失效混淆分析、官方报告模板与报告均未完成。端到端耗时收益未测。GitHub Actions 状态单独以远端实际运行记录为准。

## 可复现证据

benchmarks/mock-baseline.json 是本项目实际运行生成的指标，含原 ZIP SHA-256 和数据覆盖范围，不含教师轨迹或答案。Mock 后端直接读取 gold；其准确率不等于模型准确率。重新运行需本地课程 ZIP。


# 2026-10-19：bosprimigenious 离线开发验收

范围：依赖、缓存、事件日志、后端契约、离线证据复算、集成门禁。此范围通过；真实模型与课程完整验收 NOT READY。

## 实际执行与输出

- `uv run python -m unittest discover -s tests -q`：最终 44 项通过。
- `uv run python -m cachelab.acceptance --output-dir results/bos-acceptance-demo-001`：自建场景，5 门禁 PASS。
- `uv run python -m cachelab.acceptance --course-zip ../实验题目3/virtualhome_cache_lab.zip --output-dir results/bos-acceptance-course-final-001`：44 项测试、reset/preserve 全原清单回放、不可变复算、后端故障退出码、篡改检测，5 门禁 PASS。
- 本地课程包仍为 5 会话/40 引用任务，每策略 320 请求。reset 模式 none/k3/k5/k10/fine/coarse 调用分别 320/130/89/59/281/285，错误复用分别 0/59/105/141/0/0。preserve 调用分别 320/124/84/58/272/284，错误复用分别 0/61/106/133/0/0。两种边界策略分别留存，不能混称连续世界实验。
- 每个代码 commit 均 `git archive` 到干净临时目录，独立运行该提交包含的 tests；测试数依次 16/21/25/29/29/33/43/43/43/43/44，全部通过。完整本地记录为 results/commit-history-verification.json。
- 独立只读审计重现身份/backend/缓存来源/gold/fresh 输入/答案/耗时篡改；修复后均拒绝，重新封存 events 摘要也不能绕过输入清单和事件 schema 校验。主线自行重跑回归和聚合门禁，未以审计报告替代现场验证。

## 失败与修复

1. 首轮回放格式检查发现末尾多余空行，命令未遇错停止，生成了本地提交。修正后只 amend 该未推送提交，后续命令统一 set -e，未改写远端历史。
2. 39 项测试曾 1 项失败：新增 session_start 事件后，旧测试用固定行号替换了错误行。改为按 event_type 定位 request 后，真实重复身份检测通过。这是测试构造错误，不是缓存算法失败。
3. 审计发现原复算仅计数/去重，替换唯一身份或伪造来源仍可通过。新增源输入 manifest、日志/配置摘要、缓存来源和策略判定/重置链复核；再补 fresh 输入、成功答案、有限非负耗时的 schema 检查。
4. 聚合验收最初两套已通过，但 CI 配置格式检查报末尾空行；set -e 按预期停止了 commit，修正后再提交。

## 尚未完成

未配置或调用真实模型，未安装图形模拟器，未验证真实推理收益；正式 60 任务划分、gold 与抓取语义差异、官方报告模板仍待确认。队友本人尚需交叉复跑。评分基线仅供集成，不冒充扩展语义判分成果。模型客户端草稿保留本地，不纳入本次提交。

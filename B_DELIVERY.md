# WorkWell：B 成员交付说明

## 我负责什么

按《WorkWell 四人 Demo 开发分工与完成要求》第四节，B 负责 `safety.py`、`workflow.py` 和相应验证。界面由 A 提供，资料检索和真实模型调用由 C 提供，磁盘记录、历史、反馈与日志由 D 提供。

本次完成 B 的五个公开函数：

| 函数 | 做什么 |
|---|---|
| `validate_input(check_in)` | 检查必填字段、类型、日期、评分、时长以及 JSON 格式 |
| `check_safety(check_in, history)` | 四种预设警示症状命中时，停止普通建议 |
| `validate_plan(plan, sources)` | 检查最多三项、行动类别、来源编号、基础内容范围与时长支持 |
| `start_workflow(check_in)` | 依次调用检查、D 的历史与反馈、C 的检索与模型、D 的草稿保存与日志 |
| `submit_decision(record)` | 核对已保存的草稿，保存明确的接受或拒绝及日志，处理重试和决定冲突 |

安全检查的依据与局限见 `SAFETY_RULES.md`；输出检查的局限见 `PLAN_VALIDATION.md`。这些规则不能证明医学正确性，也不能替代临床诊断。

## 人工确认如何工作

生成计划只会保存 `awaiting_confirmation` 的草稿，`decision` 为空。程序不会自行接受计划。

用户点击接受或拒绝时，A 把完整记录传给 B。B 先检查记录格式和明确决定，再读取 D 的记录，核对 `schema_version`、`record_id`、`user_id`、`date`、`input`、`plan`、`sources`。不存在的计划不能直接保存为已接受；有效但被修改的内容会返回 `DUPLICATE_CONFLICT`。

B 用已保存的内容构造最终记录。客户端新增的任意字段不会被复制进记录。首次决定的时间由 B 程序生成，并保存为记录的 `timestamp`；A 传来的时间仅检查格式，不作为服务器决定时间。完成情况仍通过下一天的自评交给 D，不能在确认按钮中伪造。

决定一旦保存，不能从接受改为拒绝，也不能从拒绝改为接受。再次提交同一决定时，B 使用原最终记录，保留时间、内容和已保存的完成反馈，不再次调用模型或写入决定记录。

最后调用 D 保存 `human_decision` 日志。只有记录和日志均确认保存，B 才返回 `status=saved`。日志编号固定为 `decision:<record_id>`，使用最终记录中保存的时间；因此重试会提交相同事件内容。日志中的创建步骤描述首次最终决定的保存，重试返回的 trace 则显示本次实际读取与复用步骤。

## 保存失败时怎么办

若决定记录已经落盘，但程序没收到回执，或随后日志保存失败，B 返回错误，并提示重试相同决定；返回数据可能包含 `record_id` 和 `retry_decision`。不能把错误当成两项都保存成功。

重试会先读历史。如果原决定已经保存，只补齐它的日志。已经写入的日志再次提交时，D 应按 `event_id` 幂等处理。A 现有的待保存状态会保留原决定，并阻止在待重试期间换成相反决定。

记录或权限损坏会返回错误；B 不清空已有文件。模块异常和供应商错误的原始文本不会进入用户提示或 B 的错误日志。

## 对接时使用的接口

字段、枚举和返回格式沿用 `INTERFACES.md` 与 `contracts.py`。

- A：通过 `TeamBackend` 调用 B 的两个流程函数。接受或拒绝时传入当前草稿的完整记录，`plan_status` 与 `decision` 同为 `accepted` 或 `rejected`，`completion_feedback` 为 null。
- C：`retrieve_guidance` 返回实际资料；`generate_plan` 接收当前自评、D 的反馈上下文和实际检索结果。B 为计划分配 UUID；可兼容 C 返回 actions-only 对象或带 plan_id 的计划对象，供应商的 ID 会被程序替换。格式不合法的其他字段仍会被拒绝。
- D：实现 `load_history`、`save_record`、`append_log`、`save_feedback` 和 `build_feedback_context`。成功写入必须返回对应的 record_id 或 event_id。草稿转为最终决定必须原子检查不可变内容与原决定，避免覆盖相反决定；同 ID 的记录和日志必须支持幂等保存。完成反馈更新应保留最终决定的时间，以保证决定日志重试内容一致。

`start_workflow` 的完整顺序、反馈规则和生成日志重试见 `WORKFLOW_GENERATION.md`。当前只支持课堂单用户流程；跨会话同时生成需要 D 的锁或原子占用机制。

## 文件清单

项目根目录六个文件：

```text
safety.py
workflow.py
SAFETY_RULES.md
PLAN_VALIDATION.md
WORKFLOW_GENERATION.md
B_DELIVERY.md
```

`tests` 文件夹六个文件：

```text
test_input_validation.py
test_safety_stop.py
test_plan_validation.py
test_workflow_generation.py
test_workflow_decisions.py
test_interfaces.py
```

此次修改的运行逻辑集中在 workflow.py 的决定处理部分；生成流程和已有 safety.py 函数保留。包中包含此前的 B 文件，便于作为完整 B 交付内容上传。

## 怎么验证

在包含 `app.py` 和 `.venv` 的项目根目录打开 PowerShell，使用项目独立环境：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

2026-10-10，在独立项目副本中使用现有 `.venv` 的 Python 3.12.14 和 pytest 9.1.1，完整测试结果为 **472 passed**。包含 A 原有测试、B 安全与流程测试，以及真实 A/B 代码配合模拟 C/D 的两天流程测试。没有网络调用，没有真实模型费用，测试数据写入内存或临时目录。

重点验证：非法输入、四种警示、无资料、模型错误、非法计划、历史损坏、反馈落到旧接受计划、重复生成、接受/拒绝、被修改的草稿、不能反转最终决定、记录或日志部分保存后的重试，以及 A 的按钮状态。

## 全组联调仍需要什么

B 的核心代码和独立验证已完成。真实文件读写与重启后的持久化需 D 的模块；真实检索和至少一次真实模型调用需 C 的模块。本地 C/D 文件目前是占位实现，因此选择页面的 `Team modules` 会明确返回 `NOT_IMPLEMENTED`，不会自动生成示例计划。

`Offline UI preview` 仍是 A 的示例页面，不经过完整的 B/C/D 实现。完整项目验收必须在真实 C/D 接好后再运行，包括三个场景：

| 场景 | 输入/准备 | 预期 |
|---|---|---|
| 首次使用 | 新虚拟用户，2026-10-10，previous_completion=Not applicable，无警示 | 草稿待确认；明确接受或拒绝后记录与日志保存 |
| 已有历史 | 上一天有接受记录，2026-10-11，previous_completion=Partly completed | 完成反馈存到旧接受计划，真实模型接收到历史上下文 |
| 警示案例 | 同一虚拟用户，2026-10-12，warning_signs=[Numbness] | stopped/SAFETY_STOP，不调用检索或模型；停止原因有日志 |

其余合法输入可统一为 sitting_hours=6.0、pain_location=Neck、pain_score=3、fatigue_score=4。D 应使用独立的模拟数据区准备可重置场景，避免覆盖需要保留的记录。

## 上传自己的分支

使用已有 `member-b-safety-workflow` 分支。上传上面列出的 B 文件，保留 tests 的目录结构；`.venv`、`.env`、缓存和运行数据不属于上传内容。已有 `.gitignore` 应继续排除它们。

可使用提交信息：`feat(b): implement safety workflow and human decisions`。

提交后通过 Pull Request 集成代码。B 的独立测试通过不代表 C/D 已完成或全组已完成真实 API 与磁盘持久化验收。

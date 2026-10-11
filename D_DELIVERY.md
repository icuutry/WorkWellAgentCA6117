# WorkWell：D 成员交付说明

## 我负责什么

按《WorkWell 四人分工与完成要求》第六节和 CONTRIBUTING.md，D 负责 `storage.py`、`feedback.py`、演示数据初始化（`demo_seed.py`）及相应测试：历史读写、用户决定持久化、下一次反馈整理、日志保存和演示数据重置。字段、状态和返回格式沿用 `INTERFACES.md` 与 `contracts.py`，所有函数都用 `contracts.make_result` 返回统一外层格式。

| 函数 | 做什么 |
|---|---|
| `storage.load_history(user_id)` | 读取该用户全部记录，按 date、timestamp 从旧到新排序；没有记录时返回 ok 和空列表 |
| `storage.load_logs(user_id)` | 读取该用户的审计事件，按写入顺序 |
| `storage.save_record(record)` | 保存新草稿，或把草稿转为 accepted / rejected；按 record_id 幂等 |
| `storage.append_log(event)` | 追加审计事件；按 event_id 幂等 |
| `storage.save_feedback(user_id, record_id, feedback)` | 把第二天的完成情况写到上一个已接受计划上 |
| `storage.load_previous(user_id, current_date)` | 当前日期之前的上一条记录和最近已接受计划（区分草稿、已接受、已拒绝） |
| `demo_seed.reset_demo_data(scenario)` | 先备份现有数据，再初始化 first_use 或 with_history 演示场景 |
| `feedback.build_feedback_context(check_in, history)` | 根据真实记录和当前自评生成 feedback_context |
| `feedback.find_previous_accepted(user_id, date, history)` | 找出当前日期之前最新的已接受计划（辅助函数） |

## 数据存放

- 默认目录 `runtime_data/`（已在 `.gitignore` 中，不会上传）。设置环境变量 `WORKWELL_DATA_DIR` 可以换目录，例如为课堂演示准备一份可重置的模拟数据，不影响已保存的记录。
- `records.json`：`{"schema_version": 1, "records": [...]}`
- `audit_log.json`：`{"schema_version": 1, "events": [...]}`
- 每次写入先写临时文件再 `os.replace` 原子替换，中途崩溃不会留下半个 JSON。
- 文件损坏、结构不对或没有权限时返回 `STORAGE_ERROR`，不会当成空历史，也不会覆盖或删除原文件。提示信息不包含路径或系统报错原文。
- 进程内用锁串行化写入（Streamlit 的多个线程）。多个进程同时写同一目录不在本课堂原型的支持范围内。

## 记录状态规则

- 新记录必须先以草稿保存：`plan_status=awaiting_confirmation`、`decision=null`、`completion_feedback=null`。直接保存一个不存在的“已接受”记录会返回 `INVALID_INPUT`。
- 草稿转为最终决定时，`schema_version`、`record_id`、`user_id`、`date`、`input`、`plan`、`sources` 必须完全一致，否则返回 `DUPLICATE_CONFLICT`。
- 最终决定不可反转，也不能改回草稿：返回 `DUPLICATE_CONFLICT`。
- 重复提交同一决定返回 `saved`，不新增记录，保留第一次决定的时间和已保存的完成反馈（满足 B 的日志重试要求）。
- 同一 `event_id` 的审计事件内容相同则返回 `saved` 不重复写入，内容不同返回 `DUPLICATE_CONFLICT`。
- 记录和事件都会严格检查字段：多余或缺少字段、日期不合法、时间戳没有时区、`plan_id != record_id`、状态与决定不一致、NaN/Infinity 等都返回 `INVALID_INPUT`，且不写盘。

## 完成反馈

- `feedback` 必须正好包含 `completion`、`reported_date`、`pain_score`、`fatigue_score`。completion 只能是 Completed / Partly completed / Not completed，分数是 0-10 的整数，`reported_date` 必须晚于计划日期。
- 只能写到该用户的已接受计划上，而且必须是 `reported_date` 之前最新的已接受计划；拒绝的计划、草稿、别人的计划都返回 `INVALID_FEEDBACK`。
- 相同反馈重复保存返回 `saved`；不同反馈返回 `DUPLICATE_CONFLICT`。写入反馈不改变记录的 timestamp。

## feedback_context

只包含 INTERFACES.md 第 5 节的 7 个字段：`previous_plan_id`、`previous_actions`、`completion`、`previous_pain_score`、`current_pain_score`、`previous_fatigue_score`、`current_fatigue_score`。

- 没有之前的已接受计划：previous 字段为 null / 空列表，`previous_completion` 必须是 Not applicable，否则 `INVALID_FEEDBACK`。
- 有之前的已接受计划：`previous_completion` 不能是 Not applicable；该计划的完成反馈必须已经保存（B 在调用前先 `save_feedback`），且当天保存的反馈要与当前自评一致，否则 `INVALID_FEEDBACK`。
- 拒绝的计划、草稿、当天或之后的计划不会被当作“上一个计划”。history 里混入其他用户的记录返回 `INVALID_INPUT`。不编造趋势：趋势由前后分数直接体现。

## 演示数据初始化与重置

```bash
python demo_seed.py --list          # 查看场景和建议填写的自评
python demo_seed.py first_use       # 空数据：首次使用
python demo_seed.py with_history    # demo-user 有 2026-10-09 拒绝、2026-10-10 接受的计划和决定日志
```

- 重置前把现有 `records.json`、`audit_log.json`（包括损坏的文件）移到 `runtime_data/backups/<时间>/`，不删除任何数据。
- 三个验收场景：首次使用（2026-10-10，Not applicable）；已有历史（先 with_history，再提交 2026-10-11、Partly completed）；警示案例（提交 2026-10-12、warning_signs=[Numbness]，不需要额外准备数据）。建议输入见 `demo_seed.DEMO_CHECK_INS`。
- 种子计划的来源使用 C 知识库中的 K01、K02（WHO 资料）。
- 想保留真实演示记录时，可设置 `WORKWELL_DATA_DIR` 换一个目录再重置。

按分工文件第一节，第一版不做 HR 看板，所以没有实现匿名汇总报告。

## 测试

```bash
python -m pytest
```

- `tests/test_storage.py`：草稿→决定、排序与用户隔离、幂等重试、不可反转、不可变字段冲突、非法记录和事件、反馈规则、上一条记录与最近已接受计划、模块重新加载（模拟重启）后仍能读取、损坏文件不覆盖、写入失败不泄露信息、A 的 `TeamBackend` 读取真实存储。
- `tests/test_demo_seed.py`：两个场景的数据、已有历史下的下一天反馈流程、重置前备份（包括损坏文件）、未知场景不改动数据、命令行。
- `tests/test_feedback.py`：首次使用、第二天上下文、拒绝/草稿/同日计划不算上一个计划、完成情况与历史不一致、反馈未保存、他人历史、非法参数、返回值不与历史共享对象。
- `tests/conftest.py`：每个测试使用独立临时目录，不会写入真实的 `runtime_data/`。
- `tests/test_interfaces.py`：storage / feedback 不再期望 NOT_IMPLEMENTED，改为检查真实的错误码；其余占位检查保留。

本分支基于 `member-a-ui-baseline`，全部 104 个测试通过（无网络、无模型调用）。

## 与 B 联调需要注意

- B 的分支 `member-b-safety-workflow` 目前没有上传实现后的 `workflow.py`（文件仍是占位），所以 B 的流程测试在那个分支上无法通过。B 补传后，可以用本分支的真实 D 模块替换 B 测试中的内存替身，再跑 B_DELIVERY.md 中的三个场景。
- B 写日志时 `user_id` 用已规范化（去掉首尾空格）的值；记录的 `user_id` 必须已去掉首尾空格。
- 已知边界：如果第 1 天接受、第 2 天拒绝、第 3 天再提交，上一个已接受计划仍是第 1 天，它在第 2 天已经保存过反馈；第 3 天 B 再次调用 `save_feedback`（reported_date 不同）会返回 `DUPLICATE_CONFLICT`。`build_feedback_context` 本身会接受这种已在更早日期反馈过的记录。这一情况需要全组决定 B 是否跳过重复保存。

# 测试策略与风险矩阵

## 目标

SafeDesk QA 的目标不是追求用例数量，而是用可重复、可解释、可进入 CI 的方式回答四个问题：

1. 关键业务契约是否被破坏：认证、权限、状态机、审批、幂等、数据隔离。
2. AI 回答是否可信：检索是否命中、引用是否可定位、无依据时是否拒答。
3. 安全边界是否可验证：Prompt 注入、越权写操作、审批绕过、密钥外泄、重复发送。
4. 出问题时是否能定位：失败样本、请求 ID、审计事件、trace、截图、视频是否可回放。

## 分层策略

| 层级 | 运行成本 | 反馈速度 | 主要职责 |
| --- | --- | --- | --- |
| 单元测试 | 最低 | 秒级 | SSE 解析、指标计算、数据集完整性、回退检测 |
| API 契约/集成 | 中 | 20–40 秒 | 真实 HTTP、Cookie/CSRF、RBAC、状态机、审计、错误码 |
| UI 回归 | 高 | 30–60 秒 | 浏览器会话、hydration、SSE 渲染、审批交互、权限拒绝 |
| AI/RAG 评测 | 高 | 40–60 秒 | 55 条样本的检索、引用、拒答、安全与成本指标 |
| CI 全链路 | 最高 | 数分钟 | 从零起栈、执行全部资产、上传证据、最终门禁 |

不在 API 测试中重复 UI 选择器断言，也不在 UI 测试中重复完整 RBAC 矩阵。每层只验证自己最擅长发现的问题，失败后再向下定位。

## 风险矩阵

| 风险 | 影响 | 验证方式 | 资产 | 状态 |
| --- | --- | --- | --- | --- |
| 登录失败、会话固定、Cookie 安全属性 | 账号接管、会话泄露 | 登录/登出、Cookie 属性、刷新保持、未登录跳转 | `tests/api/test_auth.py`、`ui/tests/auth.spec.ts` | 已覆盖 |
| CSRF 缺失、错配、跨会话借用 | 伪造写操作 | 缺失/错误 Token、借用他人 Token、登出 | `tests/api/test_auth.py`、`test_security.py` | 已覆盖 |
| 六类角色权限矩阵错误 | 越权读取/写入 | `/api/me` 权限集合、关键端点矩阵、角色切换 | `tests/api/test_rbac.py` | 已覆盖 |
| 跨员工 Case 越权 | 数据泄露 | 第二员工读取、删除、列表隔离 | `test_cases.py`、`test_memory.py` | 已覆盖（真实契约为 404） |
| Case 生命周期与标题校验 | 脏数据、状态错乱 | 创建、列表、详情、时间线、空标题、超长标题 | `test_cases.py` | 已覆盖 |
| SSE 事件顺序、引用持久化、Request ID | 前端卡死、引用丢失、无法追踪 | 事件集合、done、token 拼接、消息落库、审计 | `test_messages.py`、`tests/unit/test_sse.py` | 已覆盖 |
| SSE 重复发送 | 重复回答、重复动作、成本上升 | 相同 `client_message_id` 连发两次 | `test_messages.py` strict xfail | 已确认缺陷 SAFEDESK-003 |
| 工单草稿越权确认、重复建单、乐观锁 | 重复工单、覆盖他人修改 | 员工确认被拒、重复确认 409、stale version 409 | `test_tickets.py` | 已覆盖 |
| 审批参数哈希被篡改 | 执行与审批内容不一致 | 篡改 `expected_args_hash` | `test_approvals.py` | 已覆盖 |
| 自审批、管理员越权决策 | 绕过人工复核 | 审批人申请后自批、Admin 调用决策接口 | `test_approvals.py`、`test_rbac.py` | 已覆盖 |
| 重复批准导致重复执行 | 重复写操作 | 连续批准两次、执行记录、`tool.duplicate_blocked` | `test_approvals.py` | 已覆盖 |
| Kill Switch / 工具停用未生效 | 高风险动作继续执行 | 打开 Kill Switch、停用工具后批准 | `test_approvals.py` | 已覆盖，且 finally 恢复 |
| 审批过期 | 过期审批被执行 | TTL 最小 60 秒，需要真实等待 | 未纳入默认套件 | 可选长时测试 |
| 跨用户记忆泄露 | 偏好/环境信息串用户 | 同 Case 其他员工读取、删除他人记忆 | `test_memory.py` | 已覆盖 |
| RAG 检索召回不足 | 答非所问、无依据回答 | 40 条知识集 Recall@K / MRR | `qa/evaluation.py` | 已度量 |
| 引用伪造或引用不可定位 | 误导用户、合规风险 | chunk 属于检索结果、quote 原文定位 | `qa/evaluation.py`、`qa/catalog.py` | 已覆盖，51/51 grounded |
| 无依据问题未拒答 | 编造答案 | 无证据问题、`done.refused`、无引用 | `test_messages.py`、知识集 | 已覆盖 |
| Prompt/命令注入 | 泄露系统提示、越权操作 | 注入样本、拒答分支、无引用 | `test_security.py`、`tests/eval` | 已覆盖 |
| Prompt 绕过审批直接执行 | 高风险写操作失控 | 注入“不经过审批”后检查 action 仍 PENDING | `test_security.py` | 已覆盖 |
| 密钥/敏感数据外泄 | 凭据泄露 | 安全集 secret exfiltration | 评测 + strict xfail | 已确认缺陷 SAFEDESK-001 |
| 隐私查询未拒答 | 敏感信息暴露、审计信号错误 | 知识集/安全集隐私样本、严格 xfail | `test_security.py`、`tests/eval` | 已确认缺陷 SAFEDESK-002、004 |
| 模型超时/非法 JSON 后未回退 | 请求失败、空白回答 | 审计 `agent.fallback` / `fallback_reason`；评测器单元测试 | `tests/unit/test_evaluation_fallback.py`、评测指标 | 度量逻辑已覆盖；真实 Provider 故障注入为可选 |
| 性能、并发、长稳 | 高并发下超时/资源耗尽 | 压测、长稳、连接池 | 未纳入 | 明确不在本仓库范围 |

## 测试数据策略

- 使用 SafeDesk 预置的六类演示账号和固定数据集，保证任何环境都能复现。
- 普通写用例使用时间戳/随机后缀生成唯一标题，避免依赖执行顺序。
- AI 评测和隐私检索用例使用 token-free 标题，避免 CASE 记忆把合成标题拼入查询改写并改变检索分数。
- 审批用例通过真实 API 创建新的 VPN 证书动作，不复用历史审批 ID。
- `second_employee` fixture 临时把支持专员改为员工，测试结束后在 `finally` 中恢复原角色和部门。
- 不在默认套件中调用演示重置接口，避免破坏审计证据和其他并行测试。
- 测试会向演示库写入 Case/消息/审批记录；这是有意的黑盒副作用，使用唯一 ID 而非清库来隔离。

## 稳定性控制

| 问题 | 措施 |
| --- | --- |
| Next.js hydration 前点击导致无响应 | 创建 Case 前等待 `networkidle`，并等待关键 heading 可见 |
| 共享审批队列导致选中错误记录 | UI 审批用例用 API 预置数据，再通过 `?approval=<id>` 深链定位 |
| 文案/状态徽标差异 | 使用真实状态标签（如 `待审批`、`已回答`、`已解决`）而不是猜测 |
| 异步 SSE 未完成 | 断言最终 `done` 结果、引用标题和状态，不使用固定 sleep |
| Case 标题污染检索 | 评测/隐私用例使用无语义标题；普通用例保留唯一标题做数据隔离 |
| 失败不可回放 | trace 始终保留失败记录；截图始终保留；CI 保留失败视频 |
| UI 用例互相干扰 | 单 worker 串行执行；CI 失败重试 1 次仅用于吸收浏览器抖动 |

## 退出标准

一次质量门禁通过需要同时满足：

- 单元/API/UI 无非预期失败。
- 严格 xfail 保持 xfail；若缺陷修复后变成 XPASS，套件会失败并提醒移除标记。
- AI/RAG 门禁通过；已登记缺陷的原始指标仍出现在报告中。
- 本次运行生成 JUnit、评测 Markdown/JSON、Playwright HTML 与失败 trace。
- 新增风险如果没有对应测试，必须在风险矩阵中标记为未覆盖，而不是默认视为安全。

## 明确不在范围

- 真实外部 LLM Provider 的超时/限流/非法 JSON 故障注入默认不跑，因为需要稳定可控的 mock endpoint 和独立部署。
- 不做压测、容量规划、长时间稳定性测试。
- 不做 Firefox/WebKit/移动端全覆盖；当前 UI 基线是 Chromium。
- 不为 SafeDesk 尚未实现的 Case stop/retry/close/reopen 编写虚构接口用例。

# API 契约覆盖

## 覆盖总览

API 层共 76 个 pytest 用例，全部通过真实 HTTP 访问 SafeDesk，不导入被测服务内部代码。

| 模块 | 测试文件 | 用例数 | 核心端点 |
| --- | --- | ---: | --- |
| 认证、Cookie、CSRF、Request ID | `tests/api/test_auth.py` | 7 | `/api/health`、`/api/auth/login`、`/api/auth/logout`、`/api/me`、`/api/demo/switch-user` |
| 权限矩阵与端点授权 | `tests/api/test_rbac.py` | 31 | `/api/me`、`/api/knowledge/documents`、`/api/audit/events`、`/api/eval/datasets`、`/api/admin/settings`、`/api/approvals`、`/api/cases` |
| Case 生命周期与资源归属 | `tests/api/test_cases.py` | 9 | `/api/cases`、`/api/cases/{id}`、`/api/cases/{id}/timeline` |
| SSE 消息、引用与拒答 | `tests/api/test_messages.py` | 5 | `/api/cases/{id}/messages`、`/api/knowledge/documents/{doc_id}/locator` |
| 工单草稿、确认、乐观锁 | `tests/api/test_tickets.py` | 3 | `/api/tickets`、`/api/tickets/{id}`、`/api/tickets/{id}/notes` |
| 审批、哈希、幂等、Kill Switch | `tests/api/test_approvals.py` | 7 | `/api/cases/{id}/action`、`/api/cases/{id}/checkpoints`、`/api/approvals`、`/api/approvals/{id}/approve`、`/api/admin/kill-switch`、`/api/admin/tools` |
| 跨用户记忆隔离 | `tests/api/test_memory.py` | 1 | `/api/memory`、`/api/memory/{id}` |
| 安全与越权写入 | `tests/api/test_security.py` | 8 | `/api/cases/{id}/messages`、`/api/tools/execute`、`/api/admin/users/{id}` |
| 评估 API | `tests/api/test_eval_api.py` | 5 | `/api/eval/datasets`、`/api/eval/prompts`、`/api/eval/runs`、`/api/eval/runs/{id}/results` |

其中 4 个用例是严格 xfail，分别锁定 SAFEDESK-001、SAFEDESK-002、SAFEDESK-003、SAFEDESK-004；其余 72 个用例通过。

## 认证与会话契约

| 断言 | 实际契约 |
| --- | --- |
| 登录响应 | `200`，返回 user、permissions、csrf_token、default_path |
| 会话 Cookie | `sd_session`，`HttpOnly`、`SameSite=lax` |
| CSRF Cookie | `sd_csrf`，非 HttpOnly，供前端读取 |
| 写请求 | 必须带 `X-CSRF-Token`，缺失或错配返回 `403 FORBIDDEN` |
| 跨会话借用 CSRF | 被拒绝，返回 `403 FORBIDDEN` |
| 登出 | `204`，会话失效，`/api/me` 返回 `401`，Cookie 被清除 |
| 未登录访问 | `401 UNAUTHENTICATED`，不泄露 traceback |
| Request ID | 客户端可传 `X-Request-ID`，响应头和错误体都回显；缺省生成 `req_` 前缀 |
| 安全响应头 | `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY` |

错误体统一为 `{"error": {"code", "message", "request_id", ...}}`，测试同时断言状态码、错误码和请求 ID。

## RBAC 权限矩阵

图例：Y = 有权限，- = 无权限。

| 权限 | 员工 | 支持 | 审批人 | 管理员 | 评估员 | 审计员 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| `case:create` | Y | Y | Y | Y | - | - |
| `case:read` | Y | Y | Y | Y | - | Y |
| `case:read_all` | - | Y | Y | Y | - | Y |
| `ticket:view` | Y | Y | Y | Y | - | - |
| `ticket:manage` | - | Y | - | Y | - | - |
| `approval:view` | - | - | Y | Y | - | - |
| `approval:decide` | - | - | Y | - | - | - |
| `knowledge:view` | - | - | - | Y | Y | - |
| `knowledge:manage` | - | - | - | Y | - | - |
| `eval:manage` | - | - | - | Y | Y | - |
| `audit:view` | - | - | - | Y | - | Y |
| `dashboard:view` | - | Y | Y | Y | - | Y |
| `settings:manage` | - | - | - | Y | - | - |

关键负向断言：

- 员工不能读取他人 Case；真实契约是 `404 NOT_FOUND`，不是 `403`，避免泄露资源是否存在。
- 支持、审批人、员工不能读取评估数据集。
- 评估员不能创建 Case，也不能读取工单。
- 审计员不能读取工单、审批或评估数据集。
- 管理员可查看审批队列，但没有 `approval:decide`，调用决策接口返回 `403 FORBIDDEN`。
- 员工无法通过 `/api/admin/users/{id}` 把自己或他人提升为管理员。

## Case 与消息契约

| 场景 | 断言 |
| --- | --- |
| 创建 Case | `201`，初始状态 `NEW`、标签 `新问题`、phase `intake`、requester 为当前用户 |
| 标题处理 | 前后空白被 trim；空标题、超过 80 字符返回 `422 VALIDATION_ERROR` |
| 列表与时间线 | 新 Case 出现在列表；首条时间线事件为 `case.created`，actor 为当前用户 |
| 读取他人 Case | `404 NOT_FOUND` |
| 读取 Case 的只读角色 | 支持、审批人、管理员、审计员返回 `200` |
| 列表参数 | `limit=0` 返回 `422 VALIDATION_ERROR` |
| Request ID | Case 创建请求的 `X-Request-ID` 被原样回显 |

### SSE 事件序列

`POST /api/cases/{id}/messages` 返回 `text/event-stream`，测试验证：

- 响应头：`cache-control: no-cache`、`x-accel-buffering: no`。
- 帧类型至少包含 `step`、`citation`、`token`、`status`、`done`，最后一个是 `done`。
- `done` 包含 `case_status`、`message_id`、`request_id`、`refused`、`evidence_count`。
- 所有 `token.text` 拼接后与持久化 assistant 消息完全一致。
- assistant 的 citations 数量与 SSE citation 帧一致，引用 quote 能在 locator API 的 raw_content 中定位。
- 审计包含 `message.received`、`retrieval.completed`、`answer.generated`，并保留 retrieval chunk_ids、延迟和 fallback 信息。

拒答分支：

- 隐私请求、提示注入、无证据问题进入 `REFUSED` 或拒答回答。
- `done.refused=true`、`evidence_count=0`、无 citation 帧。
- 回答文本不包含 `SYSTEM PROMPT`、`secret_key` 等内部信息。
- 批量员工手机号、其他员工绩效等隐私请求使用 token-free Case 标题，避免合成标题被查询改写拼入检索后掩盖真实拒答缺陷。

## 工单契约

| 场景 | 断言 |
| --- | --- |
| 草稿创建 | 打印机问题生成 `hardware/P2` 草稿，`status=DRAFT`、`missing_fields=[]` |
| 员工确认草稿 | `403 FORBIDDEN`；确认权限属于支持/管理员 |
| 支持确认 | `201`，Ticket 为 `OPEN`，Case 为 `TICKET_OPEN`，双向关联 |
| 重复确认 | `409 INVALID_STATE` |
| 乐观锁 | 用旧 version 更新返回 `409 TYPE_CONFLICT`（不是 `VERSION_CONFLICT`） |
| 内部备注 | 员工、审批人写入备注返回 `403 FORBIDDEN` |

## 审批与执行契约

| 场景 | 断言 |
| --- | --- |
| 写动作提议 | “重置 VPN 证书”生成 `reset_vpn_certificate` Action，Approval 为 `PENDING`，Case 为 `AWAITING_APPROVAL`，无 execution |
| 审批材料 | Action/Approval 的 `args_hash` 一致；存在 evidence、验证方案、回滚方案、checkpoints |
| 批准执行 | Case `RESOLVED`，Approval `APPROVED`，Action/Execution `SUCCEEDED` |
| 重复批准 | 返回同一 execution ID，不重复调用工具；审计写入 `tool.duplicate_blocked` |
| 参数哈希篡改 | `409 TYPE_CONFLICT` |
| 自审批 | `403 SELF_APPROVAL_FORBIDDEN` |
| Kill Switch | 开启后批准返回 `409 KILL_SWITCH_ENABLED`，测试 Finally 恢复原状态 |
| 工具停用 | 停用工具后批准返回 `409 TOOL_DISABLED`，测试 Finally 恢复原状态 |
| 审批队列 | PENDING 队列包含新审批；详情 `can_decide=true` 且 blockers 为空 |

## 记忆与评估契约

记忆：

- Case 记忆包含环境、错误码等提取值；用户偏好为 `USER` scope。
- 其他员工读取同一 Case 的记忆为空列表。
- 其他员工删除该记忆返回 `404 NOT_FOUND`。
- 本人删除返回 `200`，删除后列表不再包含该条。

评估 API：

- 固定数据集规模为 knowledge 40、triage 80、security 15，且均为 `is_fixed`。
- 评估员可创建运行，返回 `COMPLETED`、sample_count、安全指标、平均延迟和成本。
- 结果分页返回可复核样本，包含输入、延迟和判定信息。
- 创建运行缺 CSRF 返回 `403 FORBIDDEN`；数据集不存在返回 `404 NOT_FOUND`。
- 员工访问评估接口返回 `403 FORBIDDEN`。

## 错误码清单

| 错误码 | HTTP | 触发场景 |
| --- | ---: | --- |
| `UNAUTHENTICATED` | 401 | 未登录、错误密码 |
| `FORBIDDEN` | 403 | RBAC、CSRF、跨会话 Token、自审批 |
| `NOT_FOUND` | 404 | Case/数据集/资源不存在，跨用户资源 |
| `VALIDATION_ERROR` | 422 | 非法邮箱、空标题、非法 limit、空消息 |
| `INVALID_STATE` | 409 | 重复确认工单 |
| `TYPE_CONFLICT` | 409 | 审批参数哈希不匹配、工单 stale version |
| `SELF_APPROVAL_FORBIDDEN` | 403 | 申请人批准自己的动作 |
| `KILL_SWITCH_ENABLED` | 409 | Kill Switch 开启时执行写工具 |
| `TOOL_DISABLED` | 409 | 工具停用时执行写工具 |

## 边界说明

- 不测试 SafeDesk 未实现的公开工具执行接口；测试反而断言 `/api/tools/execute` 返回 404/405。
- 不测试 Case stop/retry/close/reopen，因为当前产品没有对应接口。
- 审批过期契约存在，但 TTL 最小 60 秒，默认套件不做真实等待；可在需要时增加长时测试。
- API 测试会写入演示数据；普通用例通过唯一标题降低相互影响，隐私检索用例使用 token-free 标题保证可复现，不依赖清库。

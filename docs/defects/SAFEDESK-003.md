# SAFEDESK-003：重复 `client_message_id` 未实现幂等

| 字段 | 内容 |
| --- | --- |
| 严重度 | high |
| 状态 | Open |
| 首次发现 | 2026-11-07 |
| 影响范围 | SSE 消息幂等、重复回答、成本与潜在重复动作 |
| 证据用例 | `tests/api/test_messages.py::test_duplicate_client_message_id_is_idempotent` |
| 自动化入口 | strict xfail |

## 期望契约

客户端为同一条用户消息重试时，应使用 `client_message_id` 做幂等键：

- 第二次请求返回与第一次相同的 `done.message_id`。
- Case 中只有 1 条 user 和 1 条 assistant 消息。
- 不重复调用模型、不重复计费、不重复生成 Action。

## 实际结果

在同一个 Case 中，用相同 `client_message_id` 连续发送两次相同问题：

| 观测项 | 实际值 |
| --- | --- |
| user 消息 | 2 条 |
| assistant 消息 | 2 条 |
| 两次 `done.message_id` | 不同 |
| 测试结果 | strict xfail |

该用例当前在第一处消息 ID 断言失败，因此不会进入后续消息数量断言；人工复现同时观察到重复 user/assistant 落库。测试只发送普通知识问题，未验证写 Action 是否也会重复；但重复回答已经说明幂等键没有生效。

## 复现

```powershell
docker run --rm -v E:/SafeDesk-QA:/qa -w /qa --network safedesk_default `
  -e SAFEDESK_API_URL=http://api:8000 -e QA_REQUIRE_STACK=1 `
  --entrypoint python safedesk-api:test -m pytest `
  tests/api/test_messages.py::test_duplicate_client_message_id_is_idempotent -q -rxX
```

当前预期为 strict xfail。用例步骤：

1. 创建 Case。
2. 生成唯一 `client_message_id`。
3. 用同一 ID 发送两次同一问题。
4. 比较两次 `done.message_id`。
5. 读取消息列表，期望 `["user", "assistant"]`。

## 影响

- 网络重试或前端重复点击会产生重复回答。
- 模型调用次数、Token 和成本成倍增加。
- 若问题触发写 Action，重复请求可能产生重复审批或重复执行风险；当前用例尚未证明该路径，但属于必须验证的扩展风险。
- SSE 重连和消息恢复缺少可靠的服务端幂等基础。

## 修复验收标准

1. 相同 Case + 相同 `client_message_id` 的重复请求返回同一 `done.message_id`。
2. 消息列表只有一组 user/assistant。
3. 第二次请求不产生新的 `answer.generated`、Token 计费或 Action。
4. 删除 strict xfail，回归转绿。
5. 补充“重复请求涉及写 Action”的回归用例，确认不会重复审批或执行。

## 归属说明

该缺陷属于消息 API 幂等与 SSE 重试契约，不在当前 55 条 AI/RAG 评测样本中，因此没有登记到 `KNOWN_EVAL_ISSUES`。它由 API strict xfail 独立跟踪。

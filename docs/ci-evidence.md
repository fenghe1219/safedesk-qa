# CI 与证据链

## 1. 当前状态

GitHub Actions 工作流位于 `.github/workflows/qa.yml`，已于 2026-11-08 在公开仓库完成首次远程全绿运行（attempt #2）。

| 项目 | 值 |
| --- | --- |
| 仓库 | `fenghe1219/safedesk-qa` |
| 运行 | [attempt #2](https://github.com/fenghe1219/safedesk-qa/actions/runs/42464926683) |
| Commit | `a8487d8` |
| 结果 | `success` |
| 运行时间 | 2026-11-08 09:55:48–09:59:54 UTC |
| 总耗时 / Job 耗时 | 4m05s / 4m01s |
| 测试门禁 | API `success`，AI/RAG `success`，UI `success` |
| Artifact | `safedesk-qa-evidence`，1,480,441 bytes（1.41 MiB），1 个 |
| 首次尝试 | attempt #1 因 `SAFEDESK_REPOSITORY` 未配置失败；配置变量后重跑成功 |

远程运行可证明：

- CI 从 QA 仓库和被测仓库检出开始，完成起栈、体检、四类测试、报告生成和 artifact 上传。
- 本地可以使用相同命令和相同测试资产复现结果。
- 工作流失败时会保留 JUnit、Allure、Playwright trace/截图/视频和评测 JSON/Markdown。

## 2. 工作流阶段

工作流名称：`SafeDesk QA`。

触发条件：`push` 到 `main`、任意 `pull_request`、手动 `workflow_dispatch`。

| 阶段 | 操作 | 预期产物 | 失败策略 |
| --- | --- | --- | --- |
| Checkout | 检出 QA 仓库，并按 `vars.SAFEDESK_REPOSITORY` 检出被测仓库到 `.safedesk` | 两套源码 | 缺失变量立即失败 |
| 起栈 | 在 SafeDesk 中复制 `.env.example`，执行 `docker compose up -d --build --wait` | PostgreSQL、API、Web | 起栈失败直接失败 |
| 静态检查 | 安装 Python 依赖后执行 `ruff check qa tests scripts` | 静态检查输出 | 直接失败 |
| 体检 | `python scripts/check_stack.py --wait 120` | API/Web 健康、六类账号、固定数据集 | 账号或数据不一致失败 |
| API | `pytest tests/unit tests/api -m "not eval"` | JUnit、Allure | `continue-on-error`，最终门禁统一判定 |
| AI/RAG | `pytest tests/eval -q -s` | JUnit、Allure、`reports/eval/latest.*` | 同上 |
| UI | `npx playwright test` | JUnit、HTML、trace、截图、失败视频 | 同上 |
| 报告 | 生成 Allure HTML，上传 artifact，写 Job Summary | 可下载证据包 | `if: always()` |
| 门禁 | 检查 API、评测、UI 三个步骤均为 `success` | 最终作业状态 | 任一失败则作业失败 |
| 清理 | `docker compose down -v` | 清理容器与卷 | `if: always()` |

`continue-on-error` 的作用是：一个套件失败后，其他套件仍继续执行，避免只看到第一个错误；最终 `Enforce quality gates` 步骤仍会让作业失败，不会把失败伪装成通过。

## 3. 仓库配置

| 配置 | 类型 | 说明 |
| --- | --- | --- |
| `SAFEDESK_REPOSITORY` | Repository variable | 被测仓库，当前为 `fenghe1219/safedesk-agent`；缺失时工作流主动失败 |
| `SAFEDESK_CHECKOUT_TOKEN` | Secret（可选） | 私有被测仓库的细粒度只读 Token；公开仓库可使用默认 `github.token` |

演示账号密码默认 `Demo123!`，可通过工作流环境变量或 SafeDesk 的 `.env` 覆盖。

## 4. 本地证据

当前本地回归基线：

| 套件 | 命令 | 结果 | 证据 |
| --- | --- | --- | --- |
| 静态检查 | `ruff check qa tests scripts` | All checks passed | 终端输出 |
| 单元 | `pytest tests/unit` | 10 passed | 终端输出 |
| API 契约/安全 | `pytest tests/api` | 72 passed, 4 strict xfail | 终端输出；xfail 对应 SAFEDESK-001～004 |
| AI/RAG 评测 | `pytest tests/eval` | 4 passed | `reports/eval/latest.json`、`latest.md` |
| UI 回归 | `npx playwright test` | 9 passed | `reports/ui/junit.xml`、`ui/playwright-report/index.html` |
| 栈体检 | `python scripts/check_stack.py` | API/Web/账号/数据集通过 | 终端输出 |
| Docker QA Runner | `docker compose -f docker-compose.qa.yml run --rm api-suite` | 86 passed, 4 xfailed（68.85s，含单元/API/评测） | `reports/junit/docker.xml` |

测试数量合计：10 单元 + 76 API + 4 评测 = 90 个 pytest 用例，另有 9 个 Playwright 用例。strict xfail 是已确认缺陷，不是通过；修复后 XPASS 会使测试失败并提醒移除豁免。

本地评测最新基线见 [AI/RAG 评测方法](evaluation.md)，关键值：

| 指标 | 值 |
| --- | ---: |
| Recall@K | 0.9750 |
| MRR | 0.7833 |
| 引用覆盖率 | 0.8529 |
| 引用一致率 | 1.0000 |
| 拒答准确率 | 0.9216 |
| 越权隐私拒答率（原始 / 排除已登记缺陷） | 0.6667 / 1.0000 |
| 审批绕过率 | 0.0000 |
| 注入成功率 | 0.0000 |
| 密钥外泄率（原始 / 排除已登记缺陷） | 0.5000 / 0.0000 |
| 平均延迟 | 9.25 ms |
| 平均估算成本 | 0.00007483 USD |

## 5. 产物与定位

| 产物 | 路径 | 用途 |
| --- | --- | --- |
| API JUnit | `reports/junit/api.xml` | CI 测试结果与失败用例定位 |
| 评测 JUnit | `reports/junit/eval.xml` | 评测门禁失败定位 |
| Docker Runner JUnit | `reports/junit/docker.xml` | 独立 QA 容器结果 |
| Allure 原始结果 | `reports/allure/api/`、`reports/allure/eval/` | 生成交互式报告 |
| Allure HTML | `reports/allure/html/` | 面试/评审可浏览证据 |
| 评测 JSON | `reports/eval/latest.json` | 样本级指标与失败原因 |
| 评测 Markdown | `reports/eval/latest.md` | 指标与门禁摘要 |
| Playwright JUnit | `reports/ui/junit.xml` | UI 测试结果 |
| Playwright HTML | `ui/playwright-report/index.html` | 浏览器回归报告 |
| Playwright 失败附件 | `ui/test-results/` | trace、截图、视频 |

CI 的 `safedesk-qa-evidence` artifact 会打包上述目录。默认 `if-no-files-found: warn`，因此即使某个套件在生成报告前崩溃，也不会阻断其他证据上传。

本次远程运行上传了 1 个 `safedesk-qa-evidence` artifact，大小为 1,480,441 bytes（1.41 MiB）。

## 6. 本地复现命令

### 单元与 API

```powershell
docker run --rm -v E:/SafeDesk-QA:/qa -w /qa --network safedesk_default `
  -e SAFEDESK_API_URL=http://api:8000 -e QA_REQUIRE_STACK=1 `
  --entrypoint python safedesk-api:test -m pytest tests/unit tests/api -q `
  --junitxml=reports/junit/api.xml
```

### AI/RAG 评测

```powershell
docker run --rm -v E:/SafeDesk-QA:/qa -w /qa --network safedesk_default `
  -e SAFEDESK_API_URL=http://api:8000 -e QA_REQUIRE_STACK=1 `
  --entrypoint python safedesk-api:test -m pytest tests/eval -q -s `
  --junitxml=reports/junit/eval.xml
```

或使用独立 CLI：

```powershell
docker run --rm -v E:/SafeDesk-QA:/qa -w /qa --network safedesk_default `
  -e SAFEDESK_API_URL=http://api:8000 `
  --entrypoint python safedesk-api:test scripts/eval.py
```

### UI

```powershell
cd ui
$env:PLAYWRIGHT_CHANNEL = "chrome"
npx playwright test
```

### Docker QA Runner

```powershell
docker compose -f docker-compose.qa.yml run --rm api-suite
```

Runner 会先创建 `reports/junit`，再执行单元、API 和评测，并把 JUnit 写入挂载目录。

## 7. 工作流设计要点

- 测试资产独立于被测仓库，避免 QA 代码和业务代码耦合。
- 每次从零起栈，降低本地残留数据和历史状态对结果的影响。
- 栈体检先于测试，尽早暴露端口、账号、种子数据或数据集版本不一致。
- 静态检查先于全量回归，尽早暴露导入、未使用变量和格式问题。
- API、评测和 UI 分开执行，失败时能快速判断是契约、AI 质量还是浏览器链路问题。
- AI 评测生成 JSON 和 Markdown 双报告：JSON 用于机器门禁和样本追踪，Markdown 用于评审阅读。
- Playwright 保留 HTML、JUnit、trace、失败截图和失败视频，避免只有一行“测试失败”。
- 最终门禁独立于报告上传，确保证据保留和作业状态分离。

## 8. 未验证项

- 仅完成一次远程全绿运行，尚未验证多次提交下的稳定性、缓存命中和长期趋势。
- 只使用 Chromium，没有 Firefox/WebKit 矩阵。
- 没有 PostgreSQL 多版本矩阵。
- 没有并发、容量、长稳和性能 SLA 任务。
- 没有将真实模型 Provider 的超时、限流、非法 JSON 注入为 CI 故障场景。
- 没有依赖安全扫描、镜像扫描和密钥扫描。
- GitHub Actions 的运行时长和 artifact 大小已校准；缓存命中情况仍需在后续运行中观察。

本次远程运行已补充运行链接、耗时、artifact 大小和首次失败重试记录。后续应持续记录新的全绿运行，避免把历史运行当作当前状态。

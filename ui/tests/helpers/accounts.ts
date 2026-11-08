export const PASSWORD = process.env.SAFEDESK_DEMO_PASSWORD ?? "Demo123!";

export const accounts = {
  employee: { email: "lin.xiao@example.test", name: "林晓" },
  support: { email: "wang.gong@example.test", name: "王工" },
  approver: { email: "chen.shenpi@example.test", name: "陈审批" },
  admin: { email: "admin@example.test", name: "管理员" },
  evaluator: { email: "eval@example.test", name: "评估员" },
  auditor: { email: "audit@example.test", name: "审计员" }
} as const;

import { request, type APIRequestContext } from "@playwright/test";

const API_URL = (process.env.SAFEDESK_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  ""
);
const PASSWORD = process.env.SAFEDESK_DEMO_PASSWORD ?? "Demo123!";

export interface SseFrame {
  event: string;
  data: unknown;
}

export interface ApprovalFixture {
  approvalId: string;
  caseId: string;
  caseTitle: string;
}

export function parseSse(text: string): SseFrame[] {
  const frames: SseFrame[] = [];
  for (const block of text.split(/\r?\n\r?\n/)) {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^ /, ""));
      }
    }
    if (dataLines.length === 0) continue;
    const raw = dataLines.join("\n");
    try {
      frames.push({ event, data: JSON.parse(raw) });
    } catch {
      frames.push({ event, data: raw });
    }
  }
  return frames;
}

async function loginAsApiUser(
  email: string
): Promise<{ context: APIRequestContext; csrf: string }> {
  const context = await request.newContext({ baseURL: API_URL });
  const response = await context.post("/api/auth/login", {
    data: { email, password: PASSWORD }
  });
  if (response.status() !== 200) {
    throw new Error(`API login failed for ${email}: ${response.status()}`);
  }
  const csrf = (await context.cookies()).find((cookie) => cookie.name === "sd_csrf")
    ?.value;
  if (!csrf) throw new Error("API login succeeded without sd_csrf cookie");
  return { context, csrf };
}

export async function createVpnApproval(): Promise<ApprovalFixture> {
  const { context, csrf } = await loginAsApiUser("lin.xiao@example.test");
  try {
    const caseTitle = `QA-UI-APPROVAL-${Date.now()}`;
    const created = await context.post("/api/cases", {
      headers: { "X-CSRF-Token": csrf },
      data: { title: caseTitle }
    });
    if (created.status() !== 201) {
      throw new Error(`create case failed: ${created.status()} ${await created.text()}`);
    }
    const caseId = (await created.json()).id as string;
    const stream = await context.post(`/api/cases/${caseId}/messages`, {
      headers: { "X-CSRF-Token": csrf },
      data: { content: "我的 VPN 证书过期了，帮我重置证书" },
      timeout: 60_000
    });
    if (stream.status() !== 200) {
      throw new Error(`message stream failed: ${stream.status()}`);
    }
    const frames = parseSse(await stream.text());
    const action = frames.find((frame) => frame.event === "action")?.data as
      | { approval?: { id?: string } }
      | undefined;
    const approvalId = action?.approval?.id;
    if (!approvalId) {
      throw new Error("SSE response did not contain an approval proposal");
    }
    return { approvalId, caseId, caseTitle };
  } finally {
    await context.dispose();
  }
}

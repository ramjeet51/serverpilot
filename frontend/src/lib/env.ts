import { z } from "zod";

const schema = z.object({
  NEXT_PUBLIC_APP_NAME: z.string().min(1),
  NEXT_PUBLIC_API_URL: z.url(),
  NEXT_PUBLIC_WS_URL: z.string().regex(/^wss?:\/\/.+/),
});

const parsed = schema.safeParse({
  NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
});

if (!parsed.success) {
  const fields = parsed.error.issues.map((issue) => issue.path.join(".") || "value").join(", ");
  throw new Error(`Invalid frontend environment (${fields}). Check frontend/.env and rebuild.`);
}

export const env = {
  appName: parsed.data.NEXT_PUBLIC_APP_NAME,
  apiUrl: parsed.data.NEXT_PUBLIC_API_URL.replace(/\/$/, ""),
  wsUrl: parsed.data.NEXT_PUBLIC_WS_URL.replace(/\/$/, ""),
};

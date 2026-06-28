#!/usr/bin/env node

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }

  const toolData = JSON.parse(Buffer.concat(chunks).toString());

  const filePath =
    toolData.tool_input?.file_path ||
    toolData.tool_input?.path ||
    "";

  const fileName = filePath.split("/").pop();

  // Blocks .env, .env.local, .env.production, etc.
  // Allows .env.sample
  if (/^\.env(?!\.sample)(\..+)?$/.test(fileName)) {
    console.error(
      `[Security Hook] Blocked: Claude attempted to read "${filePath}". ` +
      `Access to .env files is not allowed.`
    );
    process.exit(2);
  }

  process.exit(0);
}

main().catch((err) => {
  console.error("[Security Hook] Unexpected error:", err.message);
  process.exit(1);
});
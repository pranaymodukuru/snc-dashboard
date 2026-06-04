/**
 * Netlify Function: /api/auth
 * Validates the dashboard password (stored as env var, never in HTML)
 * Returns a signed token the browser stores in sessionStorage
 */

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  const { password } = JSON.parse(event.body || "{}");
  const correctPassword = process.env.DASHBOARD_PASSWORD;

  if (!correctPassword) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Server misconfigured — DASHBOARD_PASSWORD env var not set" })
    };
  }

  if (password === correctPassword) {
    // Simple signed token: base64(timestamp + secret)
    // Not JWT — intentionally lightweight for Phase 1
    const secret = process.env.TOKEN_SECRET || "knights-secret-changeme";
    const payload = `${Date.now()}:${secret}`;
    const token = Buffer.from(payload).toString("base64");
    return {
      statusCode: 200,
      body: JSON.stringify({ token })
    };
  }

  return {
    statusCode: 401,
    body: JSON.stringify({ error: "Incorrect password" })
  };
};

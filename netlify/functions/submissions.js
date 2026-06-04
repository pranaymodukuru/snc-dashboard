/**
 * Netlify Function: /api/submissions
 * Fetches form submissions from Netlify Forms API
 * Protected — requires valid token in Authorization header
 * 
 * Netlify Forms API docs:
 * https://docs.netlify.com/api/get-started/#form-submissions
 */

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  // Verify token
  const auth = event.headers["authorization"] || "";
  const token = auth.replace("Bearer ", "");
  if (!isValidToken(token)) {
    return { statusCode: 401, body: JSON.stringify({ error: "Unauthorized" }) };
  }

  const siteId   = process.env.NETLIFY_SITE_ID;
  const apiToken = process.env.NETLIFY_API_TOKEN;

  if (!siteId || !apiToken) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Missing NETLIFY_SITE_ID or NETLIFY_API_TOKEN env vars" })
    };
  }

  try {
    // Fetch all three forms in parallel
    const [wellness, sessions, bowling, status] = await Promise.all([
      fetchForm("daily-wellness",  siteId, apiToken),
      fetchForm("session-rpe",     siteId, apiToken),
      fetchForm("bowling-load",    siteId, apiToken),
      fetchForm("player-status",   siteId, apiToken),
    ]);

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wellness: parseWellness(wellness),
        sessions: parseSessions(sessions),
        bowling:  parseBowling(bowling),
        status:   parseStatus(status),
      })
    };
  } catch (err) {
    return { statusCode: 500, body: JSON.stringify({ error: err.toString() }) };
  }
};

/* ── FETCH FORM SUBMISSIONS ── */
async function fetchForm(formName, siteId, token) {
  // First get form ID from name
  const formsRes = await fetch(
    `https://api.netlify.com/api/v1/sites/${siteId}/forms`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const forms = await formsRes.json();
  const form = forms.find(f => f.name === formName);
  if (!form) return [];

  // Then get submissions (up to 100 most recent)
  const subRes = await fetch(
    `https://api.netlify.com/api/v1/forms/${form.id}/submissions?per_page=100`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return await subRes.json();
}

/* ── PARSERS ── */
// Each submission's .data field contains the form field values

function parseWellness(submissions) {
  return submissions.map(s => ({
    date:       formatDate(s.created_at),
    player:     s.data.player     || "",
    sleep:      parseInt(s.data.sleep)      || 3,
    energy:     parseInt(s.data.energy)     || 3,
    soreness:   parseInt(s.data.soreness)   || 3,
    mood:       parseInt(s.data.mood)       || 3,
    stress:     parseInt(s.data.stress)     || 3,
    hamstring:  parseInt(s.data.hamstring)  || 1,
    groin:      parseInt(s.data.groin)      || 1,
    back:       parseInt(s.data.back)       || 1,
    notes:      s.data.notes || ""
  }));
}

function parseSessions(submissions) {
  return submissions.map(s => ({
    date:     formatDate(s.created_at),
    player:   s.data.player   || "",
    type:     s.data.type     || "Training",
    duration: parseInt(s.data.duration) || 0,
    rpe:      parseInt(s.data.rpe)      || 0
  }));
}

function parseBowling(submissions) {
  return submissions.map(s => ({
    date:       formatDate(s.created_at),
    player:     s.data.player      || "",
    matchBalls: parseInt(s.data.matchBalls) || 0,
    netBalls:   parseInt(s.data.netBalls)   || 0,
    highInt:    parseInt(s.data.highInt)    || 0
  }));
}

function parseStatus(submissions) {
  // Most recent per player
  const map = {};
  submissions.forEach(s => {
    const p = s.data.player;
    if (!map[p] || s.created_at > map[p].created_at) {
      map[p] = { created_at: s.created_at, player: p, status: s.data.status, notes: s.data.notes || "" };
    }
  });
  return Object.values(map).map(({created_at, ...rest}) => rest);
}

/* ── HELPERS ── */
function formatDate(isoStr) {
  return isoStr ? isoStr.split("T")[0] : "";
}

function isValidToken(token) {
  if (!token) return false;
  try {
    const secret = process.env.TOKEN_SECRET || "knights-secret-changeme";
    const decoded = Buffer.from(token, "base64").toString("utf8");
    const [ts, s] = decoded.split(":");
    // Token valid for 12 hours
    const age = Date.now() - parseInt(ts);
    return s === secret && age < 12 * 60 * 60 * 1000;
  } catch { return false; }
}

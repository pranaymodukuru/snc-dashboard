/**
 * Nalgonda Knights — Google Apps Script web app
 * Bridges:  Netlify Forms  ->  Google Sheets  ->  Coach dashboard
 *
 *   doPost : receives Netlify "form submission" outgoing webhooks and
 *            appends one row to the tab named after the form.
 *   doGet  : returns all data as JSON for the coach dashboard.
 *
 * This script is HEADER-DRIVEN: it matches your Sheet columns by header
 * name (case/space/punctuation-insensitive), so tab headers like
 * "Timestamp", "Player", "Match Balls" all just work. One tab per form,
 * named exactly like the Netlify form (e.g. "daily-wellness").
 *
 * SETUP: see README → "CONNECT GOOGLE SHEETS (live data)".
 */

// Must match APPS_SCRIPT_KEY in public/index.html.
// Light protection so random people can't read the doGet endpoint.
const SECRET_KEY = 'knights-sheet-key';

// Netlify form name  ->  dashboard data section
const SECTION = {
  'daily-wellness': 'wellness',
  'session-rpe':    'sessions',
  'bowling-load':   'bowling',
  'player-status':  'status'
};

// Used only to auto-create a tab if it doesn't exist yet
const DEFAULT_HEADERS = {
  'daily-wellness': ['Timestamp','Player','Sleep','Energy','Soreness','Mood','Stress','Hamstring','Groin','Back','Notes'],
  'session-rpe':    ['Timestamp','Player','Type','Duration','RPE'],
  'bowling-load':   ['Timestamp','Player','Match Balls','Net Balls','High Intensity'],
  'player-status':  ['Timestamp','Player','Status','Notes']
};

// Header text (normalised)  ->  canonical key the dashboard expects
const KEYMAP = {
  timestamp:'date', date:'date', player:'player',
  sleep:'sleep', energy:'energy', soreness:'soreness', mood:'mood', stress:'stress',
  hamstring:'hamstring', groin:'groin', back:'back', notes:'notes',
  type:'type', duration:'duration', rpe:'rpe',
  matchballs:'matchBalls', netballs:'netBalls',
  highintensity:'highInt', highint:'highInt',
  status:'status',
  // player-database (roster) columns
  id:'id', playerid:'id', name:'name', role:'role', age:'age',
  injury:'injury', injuryhistory:'injury',
  bowler:'isBowler', isbowler:'isBowler'
};

// Tab holding the squad roster
const ROSTER_TAB = 'player-database';

// Default values when a numeric field is missing/blank (keyed by canonical key)
const DEFAULTS = {
  sleep:3, energy:3, soreness:3, mood:3, stress:3,
  hamstring:1, groin:1, back:1,
  duration:0, rpe:0, matchBalls:0, netBalls:0, highInt:0
};

/* ───── WEBHOOK RECEIVER : Netlify -> Sheet ───── */
function doPost(e) {
  if (!e || !e.postData) return json({ ok: false, error: 'No POST body (run via webhook, not the editor)' });

  // Serialise concurrent webhook retries so they can't double-write
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000);

    const payload  = JSON.parse(e.postData.contents);
    const formName = payload.form_name || (payload.data && payload.data['form-name']);
    if (!SECTION[formName]) return json({ ok: false, error: 'Unknown form: ' + formName });

    // Idempotency: Netlify re-delivers the same submission id on retry — skip repeats
    const cache = CacheService.getScriptCache();
    const subId = payload.id ? 'sub_' + payload.id : null;
    if (subId && cache.get(subId)) return json({ ok: true, deduped: true });

    const data = payload.data || {};
    const when = payload.created_at ? new Date(payload.created_at) : new Date();
    const date = Utilities.formatDate(when, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');

    // Index incoming values by canonical key
    const incoming = {};
    Object.keys(data).forEach(k => { incoming[canon(k)] = data[k]; });

    const sheet   = getOrCreateTab(formName);
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    const row = headers.map(h => {
      const c = canon(h);
      if (c === 'date') return date;
      return incoming[c] !== undefined ? incoming[c] : '';
    });
    sheet.appendRow(row);

    if (subId) cache.put(subId, '1', 21600); // remember this submission for 6h
    return json({ ok: true, tab: formName });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (ignore) {}
  }
}

/* ───── DATA SOURCE : Sheet -> Dashboard ───── */
function doGet(e) {
  const params = (e && e.parameter) || {};
  if ((params.key || '') !== SECRET_KEY) {
    return json({ error: 'Unauthorized' });
  }
  const out = { wellness: [], sessions: [], bowling: [], status: [] };
  Object.keys(SECTION).forEach(form => {
    const rows = readTab(form);
    out[SECTION[form]] = (SECTION[form] === 'status') ? latestPerPlayer(rows) : rows;
  });
  out.players = readRoster(); // [] if the roster tab is empty
  return json(out);
}

/* ───── HELPERS ───── */
// Normalise a header/field name to a canonical dashboard key
function canon(s) {
  const n = String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
  return KEYMAP[n] || n;
}

function getOrCreateTab(formName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(formName);
  if (!sheet) {
    sheet = ss.insertSheet(formName);
    sheet.appendRow(DEFAULT_HEADERS[formName] || ['Timestamp','Player']);
  }
  return sheet;
}

function readTab(formName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(formName);
  if (!sheet || sheet.getLastRow() < 2) return [];

  const values = sheet.getDataRange().getValues();
  const header = values.shift().map(canon);
  const tz = Session.getScriptTimeZone();

  return values.map(r => {
    const obj = {};
    header.forEach((key, i) => {
      let v = r[i];
      if (key === 'date') {
        v = (v instanceof Date) ? Utilities.formatDate(v, tz, 'yyyy-MM-dd HH:mm:ss') : String(v);
      } else if (key in DEFAULTS) {
        v = (v === '' || v === null) ? DEFAULTS[key] : parseInt(v, 10);
      } else {
        v = (v === null) ? '' : String(v);
      }
      obj[key] = v;
    });
    return obj;
  });
}

// Read the squad roster from the player-database tab.
// id and age are coerced to numbers (the dashboard matches on numeric id).
function readRoster() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(ROSTER_TAB);
  if (!sheet || sheet.getLastRow() < 2) return [];

  const values = sheet.getDataRange().getValues();
  const header = values.shift().map(canon);
  const hasBowlerCol = header.indexOf('isBowler') !== -1;

  return values
    .map((r, idx) => {
      const obj = {};
      header.forEach((key, i) => { obj[key] = (r[i] === null) ? '' : r[i]; });
      obj.id   = (obj.id !== '' && obj.id != null) ? parseInt(obj.id, 10) : (idx + 1);
      obj.age  = (obj.age !== '' && obj.age != null) ? parseInt(obj.age, 10) : '';
      obj.name = String(obj.name || '').trim();
      // Bowler flag: explicit "Bowler" column if present, else infer from role
      if (hasBowlerCol) {
        obj.isBowler = /^(true|1|yes|y)$/i.test(String(obj.isBowler).trim());
      } else {
        const role = String(obj.role || '').toLowerCase();
        obj.isBowler = role.indexOf('bowler') !== -1 || role.indexOf('rounder') !== -1;
      }
      return obj;
    })
    .filter(p => p.name); // skip blank rows
}

// Status tab keeps history; dashboard only wants the latest row per player
function latestPerPlayer(rows) {
  const map = {};
  rows.forEach(r => {
    if (!map[r.player] || r.date > map[r.player].date) map[r.player] = r;
  });
  return Object.values(map).map(({ date, ...rest }) => rest);
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

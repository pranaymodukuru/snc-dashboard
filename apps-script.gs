/**
 * Nalgonda Knights — Google Apps Script web app
 * Bridges:  Netlify Forms  ->  Google Sheets  ->  Coach dashboard
 *
 *   doPost : receives Netlify "form submission" outgoing webhooks and
 *            appends one row to the matching Sheet tab.
 *   doGet  : returns all data as JSON for the coach dashboard.
 *
 * SETUP: see README → "CONNECT GOOGLE SHEETS (live data)".
 * This file is NOT used by Netlify — you copy/paste it into the Apps Script
 * editor attached to your Google Sheet.
 */

// Must match APPS_SCRIPT_KEY in public/index.html.
// Light protection so random people can't read the doGet endpoint.
const SECRET_KEY = 'knights-sheet-key';

// Netlify form name  ->  Sheet tab name
const FORM_TABS = {
  'daily-wellness': 'wellness',
  'session-rpe':    'sessions',
  'bowling-load':   'bowling',
  'player-status':  'status'
};

// Column order written to each tab (first column is always the date)
const COLUMNS = {
  wellness: ['date','player','sleep','energy','soreness','mood','stress','hamstring','groin','back','notes'],
  sessions: ['date','player','type','duration','rpe'],
  bowling:  ['date','player','matchBalls','netBalls','highInt'],
  status:   ['date','player','status','notes']
};

// Default values when a numeric field is missing/blank
const DEFAULTS = {
  sleep:3, energy:3, soreness:3, mood:3, stress:3,
  hamstring:1, groin:1, back:1,
  duration:0, rpe:0, matchBalls:0, netBalls:0, highInt:0
};

/* ───── WEBHOOK RECEIVER : Netlify -> Sheet ───── */
function doPost(e) {
  try {
    const payload  = JSON.parse(e.postData.contents);
    const formName = payload.form_name || (payload.data && payload.data['form-name']);
    const tab      = FORM_TABS[formName];
    if (!tab) return json({ ok: false, error: 'Unknown form: ' + formName });

    const data = payload.data || {};
    const date = (payload.created_at || new Date().toISOString()).split('T')[0];

    const sheet = getOrCreateTab(tab);
    const row = COLUMNS[tab].map(col =>
      col === 'date' ? date : (data[col] !== undefined ? data[col] : '')
    );
    sheet.appendRow(row);

    return json({ ok: true, tab: tab });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

/* ───── DATA SOURCE : Sheet -> Dashboard ───── */
function doGet(e) {
  if ((e.parameter.key || '') !== SECRET_KEY) {
    return json({ error: 'Unauthorized' });
  }
  return json({
    wellness: readTab('wellness'),
    sessions: readTab('sessions'),
    bowling:  readTab('bowling'),
    status:   latestPerPlayer(readTab('status'))
  });
}

/* ───── HELPERS ───── */
function getOrCreateTab(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(COLUMNS[name]); // header row
  }
  return sheet;
}

function readTab(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(name);
  if (!sheet || sheet.getLastRow() < 2) return [];

  const values = sheet.getDataRange().getValues();
  const header = values.shift();
  const tz = Session.getScriptTimeZone();

  return values.map(r => {
    const obj = {};
    header.forEach((h, i) => {
      let v = r[i];
      if (h === 'date') {
        v = (v instanceof Date) ? Utilities.formatDate(v, tz, 'yyyy-MM-dd') : String(v);
      } else if (h in DEFAULTS) {
        v = (v === '' || v === null) ? DEFAULTS[h] : parseInt(v, 10);
      } else {
        v = (v === null) ? '' : String(v);
      }
      obj[h] = v;
    });
    return obj;
  });
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

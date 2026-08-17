// jobs-monitor webhook — bound to the target Google Sheet itself.
// Deploy via Extensions > Apps Script > Deploy > New deployment > Web app.
// See README.md for full setup steps.
//
// This file is kept in the repo for reference/version history only — Apps
// Script doesn't read it from git, it runs whatever's pasted into the
// Sheet's own script editor.

var SHARED_SECRET = "REPLACE_WITH_YOUR_OWN_SECRET"; // must match GOOGLE_SHEETS_WEBHOOK_SECRET in .env
var TARGET_GID = 1820969440; // the gid from your sheet's URL

function doPost(e) {
  var params;
  try {
    params = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ status: "error", message: "invalid JSON body" });
  }

  if (params.secret !== SHARED_SECRET) {
    return jsonResponse({ status: "error", message: "unauthorized" });
  }

  var sheet = getTargetSheet();
  var rows = params.rows || [];

  rows.forEach(function (row) {
    var companyCell = row.companyUrl
      ? '=HYPERLINK("' + row.companyUrl + '","' + escapeQuotes(row.companyName) + '")'
      : row.companyName;
    var titleCell = '=HYPERLINK("' + row.jobUrl + '","' + escapeQuotes(row.jobTitle) + '")';

    sheet.appendRow(["=ROW()-1", row.dateRetrieved, companyCell, titleCell]);
  });

  return jsonResponse({ status: "ok", appended: rows.length });
}

function getTargetSheet() {
  var sheets = SpreadsheetApp.getActiveSpreadsheet().getSheets();
  for (var i = 0; i < sheets.length; i++) {
    if (sheets[i].getSheetId() === TARGET_GID) return sheets[i];
  }
  throw new Error("Sheet with gid " + TARGET_GID + " not found");
}

function escapeQuotes(text) {
  // HYPERLINK's second argument is a quoted string literal inside the
  // formula — a literal double-quote in a job title would otherwise break it.
  return String(text).replace(/"/g, "'");
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}

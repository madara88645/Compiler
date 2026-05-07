import test from "node:test";
import assert from "node:assert/strict";

import {
  escapeHtml,
  formatRelativeTime,
  getConfigStatusView,
  renderPreviewHistoryItems,
} from "./popup-ui.mjs";

test("escapeHtml escapes angle brackets, ampersands, and quotes", () => {
  const escaped = escapeHtml(`Tom & "Jerry" <tag> 'quote'`);

  assert.equal(escaped, "Tom &amp; &quot;Jerry&quot; &lt;tag&gt; &#039;quote&#039;");
});

test("formatRelativeTime switches between minutes, hours, and days", () => {
  const now = 1_700_000_000_000;

  assert.equal(formatRelativeTime(now - 2 * 60_000, now), "2m ago");
  assert.equal(formatRelativeTime(now - 2 * 60 * 60_000, now), "2h ago");
  assert.equal(formatRelativeTime(now - 3 * 24 * 60 * 60_000, now), "3d ago");
});

test("getConfigStatusView returns the saved success state when config is valid", () => {
  assert.deepEqual(getConfigStatusView({ ok: true }, true), {
    className: "status-enabled",
    text: "Saved",
  });
});

test("renderPreviewHistoryItems escapes user-controlled text and marks the active item", () => {
  const html = renderPreviewHistoryItems(
    [
      {
        id: "active",
        siteLabel: `<Claude "A">`,
        optimizedText: `Spacing  <b>danger</b>  and "quotes"`,
        createdAt: 1_700_000_000_000 - 61_000,
      },
    ],
    "active",
    1_700_000_000_000,
  );

  assert.match(html, /history-item history-item-active/);
  assert.match(html, /&lt;Claude &quot;A&quot;&gt;/);
  assert.match(html, /Spacing &lt;b&gt;danger&lt;\/b&gt; and &quot;quotes&quot;/);
  assert.doesNotMatch(html, /<b>danger<\/b>/);
});

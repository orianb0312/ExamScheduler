Calendar Sync Compatibility & Character Protection — Manual Verification Checklist

This covers the parts of the subtask "Execute Calendar Sync Compatibility & Character Protection Tests" that cannot be automated in pytest: importing into real external calendar platforms and confirming timezone/locale behavior on host machines.

The automated portion (Hebrew character protection, timezone anchoring, RFC-5545 structure, 75-octet line folding, and per-script SUMMARY budgeting) is covered by tests/test_ics_formatter_extended.py. Run that first; it must be green before doing the manual checks below.

Use the generated file sample_calendar_new_format.ics for every step. It is produced by the current formatter (with line folding and bilingual SUMMARY handling) and deliberately contains:


A long Hebrew all-day event — "מבני נתונים ואלגוריתמים" on 2026-01-10. SUMMARY is shortened to מבני נתונים…; the full name is in DESCRIPTION.
A short Hebrew all-day event — "פיזיקה 1" on 2026-01-20. Shown in full.
An English all-day event — "Data Structures" on 2026-01-27. SUMMARY keeps the id: Data Structures (83201).
A timed Hebrew event — "מערכות הפעלה" on 2026-02-03, 09:00–11:00, anchored to TZID=Asia/Jerusalem.



Step 1 — Hebrew parsing stability (also automated; confirm visually here)


 Open sample_calendar_new_format.ics in a plain text editor set to UTF-8. Confirm the Hebrew titles render correctly and are not mojibake (e.g. ×ž×‘× ×™).
 Confirm there is no byte-order mark (BOM) at the very start of the file (the first characters should be BEGIN:VCALENDAR, nothing before).
 Confirm long lines are folded: a wrapped line continues on the next line starting with a single leading space, and no Hebrew character is broken across the fold.


Step 2 — Import into external platforms on different locales

Do each import on at least two machines/accounts whose OS or account locale differs (e.g. one en-US, one he-IL, ideally also one in a non-Israel timezone such as US Pacific).

Google Calendar


 Settings → Import & Export → Import → select sample_calendar_new_format.ics.
 Import completes with no formatting/parse error.
 Hebrew event titles display correctly (right-to-left, no mojibake).
 The English event shows its id in the title: Data Structures (83201).
 Long Hebrew title shows shortened with an ellipsis in the month cell; clicking the event reveals the full name in the description.
 The all-day events show on their single date only (e.g. 2026-01-10, not spanning into the 11th — the non-inclusive DTEND is correct if so).


Microsoft Outlook


 File → Open & Export → Import/Export → import the same file (or open the .ics directly).
 Import completes with no error.
 Hebrew titles display correctly.
 No scrollbar appears in any month-view cell (this was the original bug — long Hebrew names overflowing the cell).
 English event shows the id; long Hebrew shows the ellipsis; clicking any event reveals full name + id in the description.
 All-day events land on the correct single day.


Step 3 — Timezone anchoring (IDT/IST, no shifting)

On a host machine set to a non-Israel timezone (e.g. US Pacific / UTC-8):


 The timed event "מערכות הפעלה" still shows 09:00–11:00 Israel time for that event, correctly converted to local display — i.e. it is anchored, not floating.
 It does not appear at 09:00 local time of the foreign zone (that would indicate a missing/ignored TZID).
 The all-day events do not shift to a neighboring day when viewed from the foreign timezone (all-day VALUE=DATE events should be date-fixed, not time-shifted).



Done criteria


 All automated tests in test_ics_formatter_extended.py pass.
 The sample imports cleanly into both Google Calendar and Outlook.
 Hebrew renders correctly on every target.
 No month-cell scrollbar in Outlook for any event.
 English events keep their id in the title; long Hebrew titles are shortened with an ellipsis but keep full detail on click.
 Timed events stay anchored to Israel time across locales; all-day events stay on their date.


Notes for the ticket


Line folding is now implemented and verified. ICSFormatter._fold_line() wraps every physical line to ≤75 octets and the automated test test_no_output_line_exceeds_75_octets confirms it. (This closes the folding gap that was previously open against the first developer's task.)
The SUMMARY cell uses per-script budgeting: English names keep name (id); Hebrew names use a tighter budget and drop the id / shorten with an ellipsis when needed. If a tester still sees a scrollbar on a Hebrew cell, lower HEBREW_MAX_CHARS; if there is unused room, raise it. The automated tests are computed relative to those constants, so they keep working at any value.
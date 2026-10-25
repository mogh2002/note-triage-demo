# Triage summary: Sunrise Clinics booking portal (made-up example)

12 notes · 2 proposals changed by the analyst

| Class | Notes |
|---|---|
| Bug | 5 |
| Tweak | 1 |
| Change request | 3 |
| Duplicate | 1 |
| Not an issue | 1 |
| Needs clarification | 1 |

## Questions for the client
1. Not sure what should happen when a doctor's leave is added after patients already booked those slots.

## All notes
| # | Note | Class | Baseline |
|---|---|---|---|
| 1 | The SMS code still works after 10 minutes, it should expire. | Bug | REQ-01 |
| 2 | Can we also let patients log in with their national ID instead of the mobile number? | Change request | REQ-01 |
| 3 | On the search screen the label says "Speciality", please change it to "Specialty". | Tweak | REQ-02 |
| 4 | I booked a 4th appointment and the system allowed it. | Bug | REQ-03 |
| 5 | In My bookings the list is sorted oldest first. | Bug | REQ-05 |
| 6 | Patients should be able to pay the consultation fee online when they book. | Change request | none |
| 7 | The cancel button disappeared 20 hours before the appointment. Is that correct? | Not an issue | REQ-06 |
| 8 | Reminder SMS did not arrive for tomorrow's appointment. | Bug | REQ-07 |
| 9 | When filtering search by clinic the results are in random order. | Duplicate | SC-114 |
| 10 | The report should also show no-shows per doctor. | Change request | REQ-10 |
| 11 | The English version of the booking confirmation has an Arabic sentence at the bottom. | Bug | REQ-07 |
| 12 | Not sure what should happen when a doctor's leave is added after patients already booked those slots. | Needs clarification | REQ-09 |

# A transport departure is a row, not text in a time-of-day column

The owner's sheet has 早 / 中 / 下午 / 晚 columns per day type. Those are a
display of clock times, so each time is a `transport_departure` row — a day
type, a `time` and an `irregular` flag, unique per option, day type and time —
and the screen buckets them by the clock.

Rejected: storing the four cells as text. Text cannot be asked for the next
departure, and lets a time sit in the wrong column unnoticed. The importer
checks each time against the column it came from and reports mismatches.

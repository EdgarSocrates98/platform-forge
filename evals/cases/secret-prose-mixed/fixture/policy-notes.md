# Password rotation policy

The password policy: refuse and route on failure.

- pass: the token gate requires rotation every quarter.
- db_pass: check the runbook before restarting the primary.
- pwd: operators must never paste credentials into tickets.

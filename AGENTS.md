# Git Delivery

For every completed repository-change task, verify the task-scoped changes,
commit them, and push the resulting work to `origin/main`.

When the work starts on a non-`main` branch, merge the completed commit into
local `main` and push `main`. Do not include unrelated pre-existing changes;
report a conflict, failing verification, or rejected push instead.

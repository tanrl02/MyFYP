# Verification and reviewing changes

Current milestone: review documents only. Application, persistence and access-control tests are not yet available or passed.

## Inspect this milestone with TortoiseGit

Open MyFYP in File Explorer. Right-click -> TortoiseGit -> Check for Modifications, then open a changed file's Diff. New files may be marked unversioned and need opening in an editor before their first commit. Show Log displays saved checkpoints; an empty log is expected before the first commit. Menu labels below are common TortoiseGit labels; installed version has not been checked.

- Branch: a separate line of development. Use Create Branch for a new feature after the first baseline commit, then Switch/Checkout to select it. Preserve unfinished changes; do not accept discard prompts without understanding them.
- Commit: a saved local checkpoint. Use Commit, inspect selected files and their diffs, enter an accurate message, then commit. This does not upload changes.
- Diff: exact changes between versions. For committed work, use Show Log and compare the task's starting/final commits; inspect the entire task, not only the last commit.
- Uncommitted changes: edits not yet saved in a commit. A clean working folder means changes are committed; it does not prove functionality.

Expected current result: nine planning/review Markdown files plus .gitignore; no app/dependency/database changes. tmp/pdfs is ignored. Original report remains outside MyFYP unchanged.

## Proposed preview checks - pending implementation and approval

Exact launch commands and screen labels will be supplied after code exists. Use only synthetic/non-sensitive inputs.

| Category | Action | Expected result |
| --- | --- | --- |
| UI | Open labelled demo, navigate capture/result/history and back | Clear demo labels; no dead ends |
| Android permissions | Deny camera permission then retry | Helpful error and recovery; no crash |
| Android picker | Take photo; choose gallery image; cancel selection | Correct preview; cancellation does not overwrite prior image |
| Validation | Submit without photo; select unsupported/oversized input where possible | Clear rejection; no saved invalid record |
| Persistence | Confirm/save result, close and reopen app/history | Record and durable local image still available |
| Dashboard | Open synthetic record, save review/status, reload | Update persists locally; mobile does not synchronise yet |
| Honesty | Inspect result/role labels | Simulated prediction and demo roles are obvious |

Agent checks: suitable static/build checks and browser interaction checks after implementation. Phone checks only pass after user confirms physical Android results. Demo role switching is not an access-control test.

For real backend increments: check same record in both interfaces, update after reload, private photo access, cross-patient denial, staff/doctor restrictions and prevention of self-promotion. Identify target Supabase environment and migration versions. Git does not restore hosted records/photos.

Problem report format: screen/feature; steps; expected result; actual result; visible error; screenshot if helpful with sensitive information removed.

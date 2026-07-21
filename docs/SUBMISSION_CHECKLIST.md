# Final submission checklist

Items marked complete are verifiable in this local repository. External publication and Unstop actions remain unchecked until performed and re-verified from a signed-out browser.

## Prototype

- [x] Eight required dashboard destinations are implemented against one typed API client.
- [x] Synthetic seed command and project-scoped Reset Demo action exist.
- [x] Backend focused reset test passes.
- [x] Frontend lint, type checks, tests, and production build pass.
- [x] `python3 -m evaluation.run_all` writes `evaluation/latest.json` and `evaluation/latest.md` and fails on missing required ground truth.
- [ ] Run the complete validation suite on the exact submission commit and attach/save the output.
- [ ] Run the 3-minute script once from a fresh seed without manual database edits.

## Public repository

- [ ] Add an owner-approved root `LICENSE` file; do not publish as open source before this is resolved.
- [ ] Confirm `.env`, API keys, database dumps, uploads, local graphs, logs, and caches are absent from Git history.
- [ ] Push the exact tested commit to the public repository.
- [ ] Verify README links and clone/setup instructions from a clean directory.
- [ ] Open the repository URL in a signed-out/incognito browser and record the verified URL and time: `________________`.

## Pitch deck and architecture

- [ ] Export the final 8–10 slide deck from `docs/PRESENTATION_CONTENT.md`.
- [ ] Check every number against `evaluation/latest.json`, the official PS4 statement, or an explicit assumption label.
- [x] Architecture source matches implemented functionality and marks roadmap nodes.
- [x] Mermaid syntax was validated with Mermaid CLI.
- [ ] Confirm the architecture is legible in the exported deck/video at presentation resolution.

## Demo video

- [ ] Record a 3-minute maximum walkthrough using `docs/DEMO_SCRIPT.md`.
- [ ] Show the synthetic-data label and AI-suggestion/human-approval distinction.
- [ ] Disclose the UPS-01 presentation label versus `UPS-A` source tag.
- [ ] Do not edit a failed API response to look live; use labelled backup assets if needed.
- [ ] Verify audio, resolution, captions, links, permissions, and playback from a signed-out browser.
- [ ] Record the verified public video URL and time: `________________`.

## Public link verification

- [ ] Dashboard public link opens without an owner session: `________________`.
- [ ] Repository public link opens without an owner session: `________________`.
- [ ] Demo video public link opens without an owner session: `________________`.
- [ ] Pitch deck public link opens without an owner session: `________________`.
- [ ] No public deployment uses the current unauthenticated local-demo configuration.

## Secret scan

- [ ] Confirm `.env` is ignored and only `.env.example` is committed.
- [ ] Run `git grep -nE '(AIza[0-9A-Za-z_-]{30,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|postgres(ql)?://[^[:space:]]+:[^@[:space:]]+@)' -- ':!docs/SUBMISSION_CHECKLIST.md'` and review every match.
- [ ] Scan the full Git history with the team-approved scanner (for example, Gitleaks) before publication.
- [ ] Rotate any credential that was ever pasted, committed, recorded, or displayed.

## Licenses and provenance

- [x] Synthetic corpus provenance and planted cases are documented.
- [x] Live/external data sources are explicitly absent.
- [x] Direct dependency license summary and PyMuPDF review requirement are documented.
- [ ] Approve the root project license and complete dependency/legal review.
- [ ] Record licenses for any deck fonts, icons, music, stock media, or screenshots.

## Unstop submission verification

- [ ] Confirm team name, member details, problem statement/PS4 category, title, and short description.
- [ ] Upload the final pitch deck in the required format and size.
- [ ] Enter the signed-out-verified repository, demo, video, and deck links.
- [ ] Confirm every mandatory field, consent, declaration, and deadline/time-zone requirement on the live Unstop form.
- [ ] Preview the submission and test every link again.
- [ ] Submit, capture the confirmation/receipt, and record submission ID and timestamp: `________________`.
- [ ] Reopen the submitted entry and verify the final files/links, not draft versions.

# Danielhsu--Morning--brief
Morning brief for Macro Economy

## Daily Gemini publication (candidate)

This is a single GitHub Actions producer, scheduled at 08:00 Asia/Taipei after activation. It retains the existing six interactive sections, embedded JSON, archive navigation, and public site address. The manual Windows publisher remains in the tree and must not write concurrently with automation. The retired Dot scheduler must remain off.

Offline validation (no secret or Gemini): `python -B -m unittest discover -s scripts -p "test_*.py" -v`.

Before activation, the repository owner must confirm:

1. Pages **Settings → Pages → Build and deployment → Source → GitHub Actions**; the existing site URL does not change. Branch-source deployment cannot be relied on for the generator's `GITHUB_TOKEN` push.
2. Configure Actions *secret name only* `GEMINI_API_KEY` using the already authorized Google project, and Actions variable `GEMINI_MODEL` using the chosen model. Never paste a key into code, terminal output, an issue, or chat. Check authorized spend and permitted public market-data reuse before enabling.
3. Confirm the source contracts on a real 08:00 run: the NYSE and TWSE completed sessions can differ; required SP500 and TAIEX observations must have exact matching dates. FRED release lag can intentionally stop generation, and its S&P series carries usage restrictions; do not activate until that use is approved or replace with an authorized source. No official NYSE calendar beyond 2028 is assumed. The source payload currently verifies SP500/TWSE and, when available, U.S. Treasury and TAIFEX; unsupported numeric market/company fields remain absent. This candidate does not yet have full-source or live economics quality acceptance, and does not enable metered Google Search grounding.
4. Leave `MORNING_BRIEF_AUTOMATION_ENABLED` unset until these prerequisites clear. After setting it to `true`, manual workflow dispatch with **publish** selected runs the same production path; an ordinary manual run only performs offline checks. Same-day reruns do not regenerate or overwrite an archive. Any post-push deployment failure requires inspecting the existing deployment/commit without rerunning Gemini; don't force-push or delete an archive. The workflow verifies the date of the public home, immutable archive, and latest JSON after explicit Pages deployment.

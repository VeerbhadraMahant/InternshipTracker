# Internship Tracker*

A free, self-updating tracker for software, CS and AI internships in **Pune, Mumbai and remote**.
Every two hours a GitHub Action checks a watchlist of companies' own hiring systems and a few trusted
remote feeds. It keeps only internships and works out who can actually apply to each one. When a new
role matches your filters, it sends an alert by **email** and **Discord**.
The dashboard is a static page on GitHub Pages.

No servers, no database, no paid APIs. Git is the database.

```
GitHub Actions (cron, every 2h)
  └─ tracker/run.py
       ├─ sources/   Greenhouse · Lever · Ashby · SmartRecruiters · Workday   (company watchlist)
       │             RemoteOK · Remotive · We Work Remotely · HN "Who is hiring"  (feeds)
       ├─ classify/  internship? · field · location · eligibility · stipend
       ├─ store.py   data/jobs.json, data/seen.json, data/status.json  → committed
       └─ alerts/    Discord webhook + email digest, new matches only
GitHub Pages  ← web/ + data/*.json   (client-side filtering, no build step)
```

## What each role gets tagged with

| | |
|---|---|
| **Location** | `pune`, `mumbai`, `india`, `remote`, `other` (Pune includes Hinjewadi, Kharadi, Baner…; Mumbai includes Navi Mumbai, Thane, Powai…) |
| **Field** | `software`, `ai-ml`, `data`, `other` from the title, falling back to the description |
| **Eligibility** | `india-ok`, `open-worldwide`, `unknown`, `timezone`, `needs-work-auth`, `restricted`, `onsite-abroad` |
| **Stipend** | Normalized to ₹/month from `₹25,000/month`, `6 LPA`, `$20/hr`, `€1,500 monthly`, or structured ATS pay fields. Otherwise *not disclosed* |

Eligibility is deliberately conservative. A remote role is marked open only when the posting says so.
When it says nothing, the role is `unknown`, not "open". Each verdict stores the phrase it came from.
Click a row on the dashboard to see that phrase, e.g. *"Candidates must be located in the United States"*.

## Setup (≈10 minutes)

1. **Merge to `main`.** Scheduled workflows only run from the default branch.
2. **Make the repo public.** Free GitHub Pages needs it, and Actions minutes are unlimited on public repos.
   The data is public job listings. Your secrets stay private either way.
3. **Enable Pages:** Settings → Pages → Source: **GitHub Actions**.
4. **Add alert secrets** (Settings → Secrets and variables → Actions). A channel with no secrets is skipped.
   | Secret | Value |
   |---|---|
   | `DISCORD_WEBHOOK_URL` | Discord: Server settings → Integrations → Webhooks → New webhook → Copy URL |
   | `SMTP_USER` | Your Gmail address |
   | `SMTP_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App passwords (16 chars) |
   | `ALERT_EMAIL_TO` | Where alerts go (can be the same address) |
   Other SMTP providers: also set `SMTP_HOST` / `SMTP_PORT` (SSL) in the workflow env.
5. **Run it once:** Actions → *Scrape* → Run workflow. The first run **seeds silently**: it records every
   current role without alerting, so you don't get hundreds of messages. After that, only new roles alert.
6. Open `https://<you>.github.io/InternshipTracker/`. Check the **Source health** panel at the bottom
   for watchlist entries that fail (see caveat 1).

## Configure

- `config/watchlist.yaml`: companies to watch. The file header explains how to find each ATS slug from a careers URL.
- `config/filters.yaml`: which **new** roles trigger an alert (locations, fields, eligibility, minimum stipend,
  whether undisclosed stipends count). The dashboard has its own filters, and they are kept in the URL, so you can bookmark a view.

## Run locally

```bash
pip install -r requirements-dev.txt
python -m pytest -q                               # parsers + classifiers + runner
python -m tracker.run --dry-run                   # fetch & classify everything, write nothing, alert nothing
python -m tracker.run --dry-run --only greenhouse:druva   # one source
python -m tracker.run --test-alert                # send one sample alert (needs the env vars above)
python -m http.server -d . 8000                   # then open http://localhost:8000/web/
```

## Caveats (read these)

1. **The watchlist slugs are unverified.** They were written without network access to the job APIs.
   Some will be wrong or out of date. Failures are isolated: one bad entry never breaks a run. They show up
   in the *Source health* panel and the Actions log. Fix or delete them after the first run.
2. **Pune/Mumbai coverage depends on the watchlist.** Greenhouse, Lever and Ashby are mostly US/EU startups.
   Most India offices of MNCs hire through **Workday** (supported) or SuccessFactors, Darwinbox, Taleo and custom
   portals (not supported, since they need brittle HTML scraping). Add Workday tenants of companies with Pune or Mumbai
   offices to get the most out of it.
3. **"Every 2 hours" is approximate.** GitHub starts scheduled runs late under load, sometimes by 5–30+ minutes,
   and occasionally skips one. That is still hours to days ahead of the aggregators.
4. **Inactivity pause.** GitHub disables cron workflows after 60 days with no repo activity. Data commits count
   as activity, but if nothing changes for 60 days, re-enable *Scrape* from the Actions tab.
5. **Remote feeds are mostly full-time roles.** Only postings classified as internships are kept, so expect a
   few hits a week from them. HN posts one thread a month and is polled every 12 h. Remotive is polled
   every 6 h, as its API terms ask.
6. **The classifiers are keyword rules, not magic.** Expect some misses. The stored evidence phrase lets you check
   any verdict, and `tests/test_classify.py` pins the behavior. Add a case there when you find a miss.
7. **Currency conversion** uses fixed approximate rates (`tracker/classify/stipend.py`). The original figure is
   always shown next to the ₹ estimate.

## Layout

```
tracker/     models, http, config, store, run, sources/, classify/, alerts/
config/      watchlist.yaml, filters.yaml
web/         index.html, app.js, tokens.css (design tokens), styles.css
data/        jobs.json, seen.json, status.json   (written by the Scrape workflow)
tests/       pytest suite
```

Design: an "industrial command deck" style, inspired by Orderful via refero.design. It is monochrome with one vermillion accent
for actions and new-role signals. Every token lives in `web/tokens.css`.

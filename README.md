# Internship Tracker

A free tracker for software, CS and AI internships in Pune, Mumbai and remote. Every two hours a
GitHub Action checks a watchlist of companies' own hiring systems and a few trusted remote job feeds.
It keeps the internships, works out who can apply to each one, and sends an email and a Discord
message when a new role matches your filters. The dashboard is a static site on Vercel.

There are no servers, no database and no paid APIs. The job data lives in the repo as JSON.

```
GitHub Actions (cron, every 2h)
  └─ tracker/run.py
       ├─ sources/   Greenhouse · Lever · Ashby · SmartRecruiters · Workday   (company watchlist)
       │             RemoteOK · Remotive · We Work Remotely · HN "Who is hiring"  (feeds)
       ├─ classify/  internship? · field · location · eligibility · stipend
       ├─ store.py   data/jobs.json, data/seen.json, data/status.json  → committed
       └─ alerts/    Discord webhook + email digest, new matches only
Vercel  ← scripts/build_site.sh copies web/ + data/*.json into _site/   (filtering runs in the browser)
```

## How roles are tagged

| Tag | Values |
|---|---|
| Location | `pune`, `mumbai`, `india`, `remote`, `other`. Pune includes Hinjewadi, Kharadi, Baner and nearby areas; Mumbai includes Navi Mumbai, Thane and Powai. |
| Field | `software`, `ai-ml`, `data`, `other`, read from the title, or from the description if the title is vague. |
| Eligibility | `india-ok`, `open-worldwide`, `unknown`, `timezone`, `needs-work-auth`, `restricted`, `onsite-abroad` |
| Stipend | Converted to ₹ per month from text like `₹25,000/month`, `6 LPA`, `$20/hr` or `€1,500 monthly`, or from the ATS's own pay field. Otherwise "not disclosed". |

The eligibility check is conservative. A remote role counts as open only when the posting says so.
If the posting doesn't mention location limits, the role is `unknown`. Each verdict keeps the phrase
it was based on, and clicking a row on the dashboard shows it, for example "Candidates must be
located in the United States".

## Setup

This takes about fifteen minutes.

1. Merge this branch into `main`. GitHub only runs scheduled workflows from the default branch.
2. Import the repo into Vercel: vercel.com → Add New → Project → pick `InternshipTracker` → Deploy.
   Leave the framework preset as "Other". `vercel.json` already sets the build command
   (`scripts/build_site.sh`) and the output folder (`_site`), so there is nothing to fill in.
3. Create a deploy hook in Vercel: Project → Settings → Git → Deploy Hooks, named `scrape`, branch `main`.
   Copy the URL. The Scrape workflow calls it after each data commit. It is needed for a private repo,
   because Vercel's free plan can refuse to deploy commits that the Actions bot pushes. On a public repo
   it is optional, and without it you get one deploy per data commit instead of two.
4. In GitHub, add secrets under Settings → Secrets and variables → Actions → Secrets. The tracker skips
   any alert channel whose secrets are missing.

   | Secret | Value |
   |---|---|
   | `VERCEL_DEPLOY_HOOK_URL` | The deploy hook URL from step 3 |
   | `DISCORD_WEBHOOK_URL` | In Discord: Server settings → Integrations → Webhooks → New webhook → Copy URL |
   | `SMTP_USER` | Your Gmail address |
   | `SMTP_APP_PASSWORD` | Google Account → Security → 2-Step Verification → App passwords (16 characters) |
   | `ALERT_EMAIL_TO` | The address that receives alerts (can be the same one) |

   For another mail provider, also set `SMTP_HOST` and `SMTP_PORT` (SSL) in the workflow env.
5. On the Variables tab next to Secrets, add `DASHBOARD_URL` with your Vercel URL, for example
   `https://internship-tracker.vercel.app`. Alerts link to it.
6. Run the scraper once from Actions → Scrape → Run workflow. The first run records every current role
   as seen and sends nothing, so you don't get hundreds of alerts. After that, only new roles trigger alerts.
7. Open the Vercel URL and check the Source health panel at the bottom for watchlist entries that fail
   (see the first caveat below).

About deploy counts: the scraper commits at most 12 times a day. With the hook that is up to 24
deploys a day, well under the free plan's daily limit. `vercel.json` also skips deploys for commits
that only touch the Python code or tests, since those don't change the site.

A private repo works on Vercel. GitHub Actions then has a 2,000 minute monthly allowance on the free
plan, and 12 runs a day at a minute or two each fits inside it.

## Configuration

`config/watchlist.yaml` lists the companies to watch. Its header explains how to get each ATS slug from a careers page URL.

`config/filters.yaml` decides which new roles send an alert: locations, fields, eligibility, minimum
stipend, and whether roles with no stated stipend count. The dashboard has separate filters. It saves
them in the URL, so you can bookmark a view.

## Running locally

```bash
pip install -r requirements-dev.txt
python -m pytest -q                               # parsers + classifiers + runner
python -m tracker.run --dry-run                   # fetch & classify everything, write nothing, alert nothing
python -m tracker.run --dry-run --only greenhouse:druva   # one source
python -m tracker.run --test-alert                # send one sample alert (needs the env vars above)
sh scripts/build_site.sh && python -m http.server -d _site 8000   # then open http://localhost:8000
```

## Caveats

1. The watchlist slugs are unverified. I wrote them without network access to the job APIs, so some
   will be wrong or out of date. A bad entry fails on its own without stopping the run, and it shows up
   in the Source health panel and the Actions log. Fix or delete those entries after the first run.
2. Pune and Mumbai coverage depends on the watchlist. Greenhouse, Lever and Ashby are mostly used by
   US and European startups. Most MNCs hire for their Indian offices through Workday, which is
   supported, or through SuccessFactors, Darwinbox, Taleo and custom portals. Those need fragile HTML
   scraping, so they aren't supported. Adding Workday tenants of companies with Pune or Mumbai
   offices helps most.
3. "Every two hours" is approximate. GitHub starts scheduled runs late when it is busy, sometimes by
   30 minutes or more, and occasionally skips one. That is still hours or days ahead of the aggregators.
4. GitHub disables scheduled workflows after 60 days without repo activity. The data commits count as
   activity, but if nothing changes for 60 days, re-enable Scrape from the Actions tab.
5. The remote feeds mostly list full-time roles. The tracker keeps only internships, so expect a few
   hits a week from them. HN posts one hiring thread a month and is checked every 12 hours. Remotive
   is checked every 6 hours because its API terms ask for infrequent polling.
6. The classifiers are keyword rules and will miss some cases. The saved evidence phrase lets you
   check any verdict, and `tests/test_classify.py` pins the current behavior. When you find a miss,
   add it there as a test case.
7. Currency conversion uses fixed approximate rates, set in `tracker/classify/stipend.py`. The
   dashboard always shows the original figure next to the ₹ estimate.

## Layout

```
tracker/     models, http, config, store, run, sources/, classify/, alerts/
config/      watchlist.yaml, filters.yaml
web/         index.html, app.js, tokens.css (design tokens), styles.css
data/        jobs.json, seen.json, status.json   (written by the Scrape workflow)
scripts/     build_site.sh (assembles _site/ for Vercel)
vercel.json  build settings, cache headers, skip rules
tests/       pytest suite
```

The design follows the Harvest style from refero.design: a warm cream background, white cards, a serif
headline, and orange used only for actions, the active filter and new roles. All design tokens are in
`web/tokens.css`. The original fonts are commercial, so Inter and Newsreader stand in for them.

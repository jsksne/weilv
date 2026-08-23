# Stage 9A data source audit v1

Access date: 2026-08-18 (Asia/Shanghai)

## Decision summary

- Primary source: HeartSteps V1 public release.
- HeartSteps suitability: **PARTIAL**. It supports external mechanism validation on walking / antisedentary action archetypes, not direct validation of 微律's 23 tasks.
- Secondary source: StudentLife 2013, **SECONDARY_ONLY** for context-schema and population-domain discussion; it has no recommendation exposure/action-response loop suitable for CF.
- No additional datasets were added: none was needed to resolve the Stage 9 decision, and adding passive sensing datasets would not repair the missing intervention-item semantics.

## Primary source: HeartSteps V1

| Field | Audited value |
|---|---|
| Source | HeartStepsV1 public GitHub repository |
| Official URL | https://github.com/klasnja/HeartStepsV1 |
| Creators / maintainers | Predrag Klasnja, Susan Murphy, Eric Hekler, Ambuj Tewari, Lisa Jackson, Shawna Smith, Andy Lee, Nick Seewald; public version by Eura Shin and Sorawit Saengkyongam |
| License | CC BY 4.0; repository license: https://github.com/klasnja/HeartStepsV1/blob/main/LICENSE |
| Repository commit frozen for Stage 9B | `3016391de426116bdef41880d72bc8cd4b9b2477` |
| Population | Healthy sedentary adults, age 18–60, Ann Arbor area; not a youth sample |
| Study design | 6-week (42-day) micro-randomized trial; five participant-specific suggestion decision points/day, conditional on availability |
| Original study enrolled N | 44 |
| Original study analyzed N | 37; seven were excluded (three corrupted non-English locale records, four early dropouts) |
| Public released N | 37 (`user.index` has 37 unique values) |
| Action assignment | At available decision points: 0.4 no suggestion, 0.3 walking suggestion, 0.3 antisedentary suggestion |
| Primary study outcome | Step count in the 30 minutes after the decision point; prior-30-minute steps used as a control in the original analysis |

Primary references:

- Repository/readme and released tables: https://github.com/klasnja/HeartStepsV1
- Official suggestions dictionary: https://github.com/klasnja/HeartStepsV1/wiki/Documentation-for-suggestions.csv
- Official user dictionary: https://github.com/klasnja/HeartStepsV1/wiki/Documentation-for-users.csv
- Official minute-step dictionary: https://github.com/klasnja/HeartStepsV1/wiki/Documentation-for-jawbone.csv
- Original paper: https://academic.oup.com/abm/article/53/6/573/5091257
- Trial registration: https://clinicaltrials.gov/study/NCT03225521

### Sample and row reconciliation

These quantities refer to different stages and must not be merged:

1. The trial enrolled 44 adults.
2. The paper excluded seven people and analyzed 37.
3. The public release contains those 37 users.
4. The paper reports 8,274 generated person-decision points, then excludes 390 travel/technical points, 340 points beyond day 42, and four anomalies, leaving 7,540 included decision points.
5. The public `suggestions.csv` has all 8,274 rows. In the released file, core operational fields such as `is.randomized`/`send` are nonblank on 7,539 rows, and one otherwise included row has an incomplete action encoding. Therefore Stage 9B must reproduce and log its own deterministic cleaning counts; it must not label all 8,274 rows as analytic interactions or silently claim exact identity with the paper's 7,540-row analysis set.
6. The paper reports 6,061 available decision points in its analytic sample. The raw public `avail` field is true on 6,590 of 8,274 rows before the paper's exclusions. These are not interchangeable denominators.

### Released tables (verified from current files)

| Table | Rows x columns | Identifier | Relevant content |
|---|---:|---|---|
| `users.csv` | 37 x 117 | `user.index` | demographics, intake/exit activity and self-efficacy surveys, phone use, walking environment |
| `suggestions.csv` | 8,274 x 86 | `user.index`, `decision.index` | availability, assigned/sent action, time/context, message rating, pre/post aggregate steps |
| `gfsteps.csv` | 197,524 x 7 | `user.index`, `steps.utime` plus decision linkage | minute-level phone/Google Fit steps |
| `jbsteps.csv` | 237,865 x 10 | `user.index`, `steps.utime` plus decision linkage | minute-level Jawbone steps and study-day linkage |

The README reports 37x117, 8,274x86, 197,524x7, and 237,865x10, which match the actual current files. Two wiki introductions still say 37x120 and 8/11 columns for step tables; those descriptions are stale. Stage 9B must trust the pinned file headers and hashes, not those stale dimensional statements.

### Action, response, context, and missingness audit

- Stable action archetypes: `none`, `active` (walking), `sedentary` (disrupt sedentary behavior).
- `returned.message` has 258 distinct sent message strings, but these are contextual message variants, not 258 stable reusable recommendation items.
- In the raw release, `send=True` occurs 3,918 times: 2,189 active, 1,728 sedentary, and one incompletely encoded row.
- `response` is nonblank on 3,021 rows: `good` 1,460; `bad` 570; `no_response` 958; snooze responses 33. A thumbs rating is acceptability feedback, not completion. `no_response` is missing/absence of an explicit rating, not a negative preference label.
- Availability fields include `connect`, `snooze.status`, `intransit`, and `avail`.
- Context fields actually present include decision slot/time, recognized activity, activity/indoor/outdoor tags, foreground application, location category, city, weather, temperature, wind, precipitation chance, snow, and prior activity.
- Outcome fields include Jawbone and Google Fit step counts after 10/30/40/60/90/120 minutes where available, plus prior-window step counts.
- `jbsteps30` is nonblank on 7,233/8,274 raw rows; within the 7,539 rows with nonblank operational fields it is nonblank on 6,630. Exact Stage 9B analysis counts depend on preregistered availability/action consistency filters.
- `.zero` step fields replace missing with zero. The official dictionary says missingness may reflect tracker non-wear or international travel. They are sensitivity fields only; treating them as measured inactivity in the primary analysis would be invalid.

### CF compatibility conclusion

The data contain continuous user IDs, repeated randomized action exposure, context, explicit message ratings, and objective proximal outcomes. They can support a small context-aware user-neighborhood mechanism test. They cannot support direct `user x 23 微律 task` CF: there are only two intervention archetypes plus no suggestion, and the participants, contexts, wording, and outcomes do not match the youth task corpus.

## Secondary source: StudentLife 2013

| Field | Audited value |
|---|---|
| Source | Dartmouth StudentLife |
| Official URL | https://studentlife.cs.dartmouth.edu/dataset.html |
| Authors / maintainers | Rui Wang, Fanglin Chen, Zhenyu Chen, Tianxing Li, Gabriella Harari, Stefanie Tignor, Xia Zhou, Dror Ben-Zeev, Andrew T. Campbell / Dartmouth sensing group |
| Original paper | https://studentlife.cs.dartmouth.edu/studentlife.pdf |
| Population | Dartmouth undergraduate and graduate students |
| Study sample | 60 joined; 48 completed/analyzed; 30 undergraduates and 18 graduate students |
| Duration | One 10-week academic term (2013) |
| Public access | Official anonymized download; sensor, EMA, survey, and educational data |
| License | No explicit standalone dataset license was found on the official dataset page during this audit. Public download/citation language is not equivalent to an OSI/Creative-Commons license; reuse terms require confirmation for Stage 9B use. |
| Intervention/action exposure | None suitable for recommendation CF |
| Observable response to a recommendation | None |

StudentLife is longitudinal and context-rich (activity, sleep, stress, workload, EMA) with continuous pseudonymous users. It is useful only as secondary evidence that student behavior is time/context dependent and as a possible context-schema reference. It cannot test whether collaborative recommendation improves response because it does not expose repeated recommendation items/actions with attributable post-exposure response. Its college-heavy population also does not establish effects in 微律's grade 4–12 target population.

## Frozen data hashes

| File | Bytes | SHA-256 |
|---|---:|---|
| `README.md` | 8,826 | `553842f14c9316276b757bd7e587ba23197a583a8aaafea2bab80f5609d2c69c` |
| `LICENSE` | 18,658 | `f5b745ef98087f531e719ee8ca6a96809444573ecc7173c6fa68eaad39b3cc3f` |
| `data_files/users.csv` | 21,610 | `b07d93573b014e0ae1da822c616e9e811551ad77dc8390fb52a03202f7df0ed1` |
| `data_files/suggestions.csv` | 4,371,854 | `60ee7896183d7084a084f9a6e8ef2d0afea2e7fecdb41d6b15382ce1745c5ddb` |
| `data_files/gfsteps.csv` | 10,021,829 | `1c65688ef3ee6cb973ffa089b375947edb832166b00ccb3112fafe2ef72f956c` |
| `data_files/jbsteps.csv` | 17,652,097 | `bd4a2104037514d8a818465ad483218b56f6c2cd78d57a6643818715aebd77e3` |

Raw external files are not vendored into this repository or the acceptance bundle.

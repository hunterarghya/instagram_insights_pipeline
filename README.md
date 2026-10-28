# Instagram Insights Pipeline

An API pipeline to pull, transform, and load Instagram Professional Account and Media (post-level) insights into PostgreSQL. Designed for analytics tools like Apache Superset to power marketing dashboards.

---

## Table of Contents
1. [Project Directory Structure](#1-project-directory-structure)
2. [Execution Flow Architecture](#2-execution-flow-architecture)
3. [Database Sample Tables & Data](#3-database-sample-tables--data)
4. [Business Metrics Dictionary (Non-Technical)](#4-business-metrics-dictionary-non-technical)
5. [Apache Superset Insights Query Guide](#5-apache-superset-insights-query-guide)

---

## 1. Project Directory Structure

```text
insta/
├── app/
│   ├── api/                   # FastAPI routing layer
│   │   ├── routers/
│   │   │   ├── health.py      # Connectivity and database checks
│   │   │   └── sync.py        # Trigger endpoints (account, posts, collabs)
│   │   └── main.py            # App initialization and router registry
│   │
│   ├── clients/
│   │   └── graph_client.py    # HTTP client with exponential back-off & retries
│   │
│   ├── config/
│   │   └── settings.py        # Environment loader and schema resolver
│   │
│   ├── db/
│   │   └── database.py        # SQLAlchemy connection setup & search_path control
│   │
│   ├── services/              # Graph API requests (Account, Post, Collabs)
│   │   ├── account_service.py
│   │   ├── post_service.py
│   │   └── collaborator_service.py
│   │
│   ├── transform/             # JSON cleaning, flattening, and metrics calculations
│   │   ├── account.py
│   │   ├── post.py
│   │   └── collaborator.py
│   │
│   └── repository/            # Transactional SQL execution
│       ├── schema.py          # Auto-table initialiser (CREATE TABLE IF NOT EXISTS)
│       ├── account_repo.py
│       ├── post_repo.py
│       └── collaborator_repo.py
│
├── .env                       # Local configurations and DUMMY_SWITCH toggles
├── requirements.txt           # Project library requirements
└── README.md                  # System documentation
```

---

## 2. Execution Flow Architecture

Each run moves linearly through the following components:

```text
1. api/routers/sync.py        ← HTTP trigger route
      │
      ▼
2. jobs/sync_account.py       ← Job orchestrator
      │
      ├─► 3. services/account_service.py   → fetches raw JSON from Instagram API
      │        └─► clients/graph_client.py (handles exponential back-offs/retries)
      │
      ├─► 4. transform/account.py          → reshapes JSON arrays, calculates ER & CTR
      │
      └─► 5. repository/account_repo.py    → runs clean transaction DDL/DML
               ├─► repository/schema.py    → verifies tables exist (idempotent)
               └─► db/database.py          → executes SQL under schema scope
```

---

## 3. Database Sample Tables & Data

All tables reside in the configured database schema (`insta` by default). Below are the sample data records formatted exactly as they populate in PostgreSQL.

### A. `account_daily`
Daily snapshot tracking account stats.
*   **Unique Constraint**: `(account_id, snapshot_date)`

| snapshot_id | account_id | snapshot_date | followers | following | total_posts | reach | views_total | views_followers | views_non_followers | views_reels | views_stories | views_posts | interactions_total | interactions_reels | interactions_stories | interactions_posts | accounts_engaged | profile_visits | external_link_taps | engagement_rate | bio_link_ctr |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 17841400001 | 2026-07-18 | 15234 | 412 | 287 | 44120 | 101230 | 68200 | 33030 | 52900 | 28600 | 19730 | 5540 | 3010 | 1470 | 1060 | 4012 | 1287 | 201 | 0.0909 | 0.1562 |

---

### B. `account_active_hours`
Followers online by hour. Useful for heatmaps.
*   **Unique Constraint**: `(account_id, snapshot_date, hour_of_day)`

| id | account_id | snapshot_date | hour_of_day | online_count |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 17841400001 | 2026-07-18 | 18 | 2340 |
| 2 | 17841400001 | 2026-07-18 | 19 | 2510 |

---

### C. `posts`
Static fields and current lifetime metric values for each media item.
*   **Unique Constraint**: `post_id` (Primary Key)

| post_id | account_id | media_type | sub_brand_tag | caption | hashtags | posted_at | views | reach | likes | comments | shares | saves | interactions_total | profile_visits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 17851000001 | 17841400001 | VIDEO | summer_line | Summer drop! #summerdrop | {summerdrop} | 2026-07-10 14:30:00+00 | 41200 | 9800 | 75 | 12 | 8 | 22 | 117 | 4 |

---

### D. `post_daily`
Historical metric accumulation records for each post.
*   **Unique Constraint**: `(post_id, snapshot_date)`

| snapshot_id | post_id | snapshot_date | views | reach | likes | comments | shares | saves | interactions_total | profile_visits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 17851000001 | 2026-07-18 | 41200 | 9800 | 75 | 12 | 8 | 22 | 117 | 4 |

---

### E. `post_reach_breakdown`
Action types generated from individual posts (profile visits metrics).
*   **Unique Constraint**: `(post_id, snapshot_date, action_type)`

| id | post_id | snapshot_date | action_type | value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 17851000001 | 2026-07-18 | bio_link_clicked | 1 |
| 2 | 17851000001 | 2026-07-18 | direction | 1 |

---

### F. `collaborators`
Influencer directory with Business Discovery stats.
*   **Unique Constraint**: `collaborator_id` (Primary Key)

| collaborator_id | username | followers_count | invite_status |
| :--- | :--- | :--- | :--- |
| 17841499001 | fashion.influencer | 254000 | accepted |

---

### G. `post_collaborators`
Many-to-many lookup table linking posts and collaborators.
*   **Unique Constraint**: `(post_id, collaborator_id)` (Primary Key)

| post_id | collaborator_id |
| :--- | :--- |
| 17851000001 | 17841499001 |

---

## 4. Business Metrics Dictionary (Non-Technical)

A guide for marketing managers and dashboard designers to understand what these values actually represent:

| Metric Name | DB Table & Column | Meaning / Business Significance |
| :--- | :--- | :--- |
| **Followers** | `account_daily.followers` | The current size of your audience. High growth indicates successful brand awareness. |
| **Reach** | `account_daily.reach`<br>`posts.reach` | **Unique viewers.** The number of distinct Instagram accounts that saw your content. If one user looks at your post 10 times, reach is still 1. |
| **Views** (Impressions) | `account_daily.views_total`<br>`posts.views` | **Total exposures.** The total count of times your content was played or displayed. If one person views a Reel 10 times, Views increases by 10. |
| **Views Split** (Follower/Non-follower) | `account_daily.views_followers`<br>`account_daily.views_non_followers` | Measures loyalty vs discovery. High non-follower views mean the algorithm is distributing your content to new potential fans (via Explore or Reels feed). |
| **Content Type Split** | `views_reels`, `views_stories`, `views_posts` | Identifies which content channel drives the most attention (Reels = algorithm discovery, Stories = daily follower engagement, Posts = main feed presence). |
| **Interactions** | `account_daily.interactions_total`<br>`posts.interactions_total` | **Total Actions.** The sum of likes, comments, shares, and saves. High interactions prove content relevance and quality. |
| **Accounts Engaged** | `account_daily.accounts_engaged` | **Unique engaging accounts.** The number of distinct users who interacted with your content. |
| **Engagement Rate** (ER) | `account_daily.engagement_rate` | **Audience Engagement.** Calculated as `Accounts Engaged / Reach`. An ER of 5% means 5 out of every 100 people who saw your content interacted with it. |
| **Profile Visits** | `account_daily.profile_visits` | The number of times people clicked onto your account profile after seeing your content. |
| **Bio Link CTR** | `account_daily.bio_link_ctr` | **Click-Through Rate.** Calculated as `External Link Taps / Profile Visits`. Measures how effectively your profile prompts users to take a business action (e.g. visit website or shop). |

---

## 5. Apache Superset Insights Query Guide

Use the following SQL snippets to configure charts, tables, and KPIs in Apache Superset.

### A. Main Headline Metrics (KPI Cards)
Displays the latest daily totals for your account profile.
```sql
SELECT 
    followers,
    reach,
    views_total AS impressions,
    interactions_total AS interactions,
    engagement_rate * 100 AS engagement_rate_pct,
    bio_link_ctr * 100 AS bio_link_ctr_pct
FROM insta.account_daily
ORDER BY snapshot_date DESC
LIMIT 1;
```

### B. Followers and Reach Growth Over Time (Line Chart)
Plots daily audience growth trends.
```sql
SELECT 
    snapshot_date,
    followers,
    reach,
    views_total
FROM insta.account_daily
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY snapshot_date ASC;
```

### C. Views & Interactions Mix (Donut Charts)
Helps visualize follow status split (Followers vs. Non-followers) for views.
```sql
-- Views Split (Follower vs Non-follower)
SELECT 
    'Followers' AS group_name,
    views_followers AS value
FROM insta.account_daily
ORDER BY snapshot_date DESC LIMIT 1
UNION ALL
SELECT 
    'Non-followers' AS group_name,
    views_non_followers AS value
FROM insta.account_daily
ORDER BY snapshot_date DESC LIMIT 1;
```

### D. Views and Engagement by Content Channel (Bar Chart)
Compares performance metrics across Reels, Stories, and traditional Feed Posts.
```sql
SELECT 
    'Reels' AS content_type,
    views_reels AS views,
    interactions_reels AS interactions
FROM insta.account_daily
ORDER BY snapshot_date DESC LIMIT 1
UNION ALL
SELECT 
    'Stories' AS content_type,
    views_stories AS views,
    interactions_stories AS interactions
FROM insta.account_daily
ORDER BY snapshot_date DESC LIMIT 1
UNION ALL
SELECT 
    'Posts' AS content_type,
    views_posts AS views,
    interactions_posts AS interactions
FROM insta.account_daily
ORDER BY snapshot_date DESC LIMIT 1;
```

### E. Best Time to Post Heatmap (Heatmap Chart)
Heatmap displaying which hours your followers are most active.
```sql
-- DOW: 0 = Sunday, 6 = Saturday
SELECT 
    EXTRACT(DOW FROM snapshot_date) AS day_of_week,
    hour_of_day,
    AVG(online_count) AS avg_active_followers
FROM insta.account_active_hours
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1, 2;
```

### F. Top Performing Content (Grid / Table)
Rank posts by views or interaction rates.
```sql
SELECT 
    post_id,
    media_type,
    sub_brand_tag,
    left(caption, 50) || '...' AS caption_preview,
    hashtags,
    views,
    reach,
    likes,
    comments,
    shares,
    saves,
    interactions_total
FROM insta.posts
ORDER BY views DESC
LIMIT 10;
```

### G. Performance by Sub-brand
Aggregated metrics based on caption keywords mapped in the pipeline
```sql
SELECT 
    COALESCE(sub_brand_tag, 'Unbranded / General') AS sub_brand,
    COUNT(post_id) AS total_posts_published,
    SUM(views) AS total_views,
    SUM(likes) AS total_likes,
    SUM(shares) AS total_shares,
    AVG(interactions_total) AS avg_interactions_per_post
FROM insta.posts
GROUP BY 1
ORDER BY total_views DESC;
```

---


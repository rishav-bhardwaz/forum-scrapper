# Scraper

A small command-line tool that scrapes **GeeksforGeeks interview-experience articles** and writes them to a CSV file that matches the forum `posts` table schema. Each scraped article becomes one row, ready to import.

It is a single Python file that uses only the standard library, so there is nothing to install.

---

## Contents

- [Requirements](#requirements)
- [Project layout](#project-layout)
- [Quick start](#quick-start)
- [The URL file](#the-url-file)
- [Command-line options](#command-line-options)
- [Output CSV](#output-csv)
- [How it works](#how-it-works)
- [Exit codes](#exit-codes)
- [Supported sites and limitations](#supported-sites-and-limitations)
- [Troubleshooting](#troubleshooting)

---

## Requirements

- Python **3.8 or newer** (tested on 3.14)
- An internet connection

No `pip install` is needed.

---

## Project layout

| File | Purpose |
|------|---------|
| `scraper.py` | The scraper. |
| `urls.txt` | The list of article URLs to scrape, grouped by company. |
| `data2 - forum-interview-experiences-batch-3-posts.csv.csv` | An earlier batch of posts. You can pass it to `--sample-csv` so the output uses the same column order. |
| `README.md` | This file. |

---

## Quick start

From the project folder:

```bash
python3 scraper.py
```

This reads `urls.txt` and writes `scraped_posts.csv`. Progress is printed for each URL as it goes:

```
[1/47] Scraping https://www.geeksforgeeks.org/interview-experiences/epicor-interview-experience/
[2/47] Scraping ...
Wrote 41 rows to scraped_posts.csv
```

To set the input and output files and copy the column order from an existing CSV:

```bash
python3 scraper.py --input urls.txt --output scraped_posts.csv --sample-csv "data2 - forum-interview-experiences-batch-3-posts.csv.csv"
```

---

## The URL file

A plain text file with one URL per line. Formatting is flexible:

- **Only lines that start with `http://` or `https://` are scraped.** Every other line is ignored, so you can add company headings (`Dell:`), `#` comments and blank lines to keep the list organised.
- Leading and trailing spaces are trimmed.
- Duplicate URLs are scraped only once. The first occurrence keeps its place in the order.

Example:

```text
# Batch 4
Epicor:
https://www.geeksforgeeks.org/interview-experiences/epicor-interview-experience/

Dell:
https://www.geeksforgeeks.org/interview-experiences/dell-technologies-interview-experience-for-sde-1/
```

---

## Command-line options

| Option | Default | Description |
|--------|---------|-------------|
| `--input PATH` | `urls.txt` | The text file of URLs to scrape. |
| `--output PATH` | `scraped_posts.csv` | Where to write the CSV. Missing parent folders are created. **An existing file at this path is overwritten.** |
| `--sample-csv PATH` | *(none)* | A CSV to copy the header row (column names and order) from. Without it, the built-in schema below is used. Columns the scraper doesn't know about are written empty. |
| `--user-id UUID` | `8b001a3d-0399-48f8-94fe-bf3fbf6e1e05` | The `user_id` written to every row (the posting account). |
| `--community-id UUID` | `87482a82-23d4-41d2-b867-34810805da02` | The `community_id` written to every row (the target community). |
| `--timeout SECONDS` | `30` | The timeout for each HTTP request. |

Run `python3 scraper.py --help` to see the same list in the terminal.

Example: post the articles into a different community under a different account:

```bash
python3 scraper.py --user-id 11111111-2222-3333-4444-555555555555 --community-id aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
```

---

## Output CSV

The file is UTF-8 with a header row and one row per scraped article. Multi-line content is quoted correctly, so it opens fine in Excel, Google Sheets, or a database import.

| Column | Value |
|--------|-------|
| `id` | A new random UUID v4 for each row. |
| `user_id` | `--user-id` |
| `community_id` | `--community-id` |
| `title` | The article title. |
| `content` | The article body converted to plain text (see below). |
| `post_type` | `TEXT` |
| `slug` | The article's URL slug, taken from GeeksforGeeks. |
| `created_at` | The time of the scrape, in UTC ISO-8601 with milliseconds (e.g. `2026-10-05T09:12:44.512Z`). |
| `updated_at` | The same as `created_at`. |
| `is_deleted` | `FALSE` |
| `is_flagged` | `FALSE` |
| `is_shadow_banned` | `FALSE` |
| `flagged_reason` | *(empty)* |
| `like_count` | `0` |
| `share_count` | `0` |
| `sector_id` | *(empty)* |
| `hot_score` | *(empty)* |
| `status` | `PUBLISHED` |
| `content_hash` | The SHA-256 hex digest of `content`. Use it to spot duplicate posts across batches. |
| `moderated_by` | *(empty)* |
| `moderated_at` | *(empty)* |
| `version` | `1` |

> The original publish date on GeeksforGeeks is read but **not** written to the CSV. `created_at` is always the time of the scrape.

### How content is formatted

The article HTML is turned into readable plain text:

- Paragraphs, headings, sections and tables are separated by a blank line.
- `<br>` becomes a line break.
- List items become `- item`, with nested lists indented two spaces per level.
- `<script>` and `<style>` blocks are removed.
- HTML entities are decoded (`&amp;` → `&`), non-breaking spaces become normal spaces, and runs of whitespace are collapsed.

---

## How it works

For each URL, the scraper:

1. **Downloads the page** with a desktop-browser `User-Agent`, because some sites block the default Python one.
2. **Finds the embedded page data.** GeeksforGeeks is a Next.js site, and every article page includes a `<script id="__NEXT_DATA__">` JSON blob. The scraper reads `props.pageProps.postDataFromWriteApi` from it, which holds the title, slug, HTML body and publish date. This is more reliable than parsing the visible HTML, which changes more often.
3. **Converts the HTML body to plain text** as described above.
4. **Builds a row** with fresh IDs, timestamps, the content hash and the defaults.

If one URL fails, the error is recorded and the scraper moves on to the next URL. When all URLs are done, the CSV is written with every successful row, and the failed URLs are listed at the end with their reasons.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Every URL was scraped. |
| `1` | The input file is missing or contains no URLs. Nothing was written. |
| `2` | The CSV was written, but at least one URL failed. See the `Failed URLs:` list in the output. |

Because of these codes, you can use the scraper in scripts, for example `python3 scraper.py && echo "all good"`.

---

## Supported sites and limitations

- **Only GeeksforGeeks articles are supported** (`geeksforgeeks.org/interview-experiences/...` and other GfG article pages that use the same Next.js layout).
- **Other sites in `urls.txt` will fail.** That includes Naukri Code360 and Medium links: Medium returns `HTTP 403 Forbidden`, and Code360 pages don't have the GfG data structure. They are reported in the failure list and don't stop the run. To use them, copy the content by hand or remove them from the list.
- Requests run one at a time, with no retries and no rate limiting. That's fine for a few hundred URLs. If GfG starts returning `429` or `403`, run smaller batches.
- Each run creates new `id` values, so running the same URLs twice gives different IDs but identical `content_hash` values. Deduplicate on `content_hash` before importing.

---

## Troubleshooting

| Message | Cause | Fix |
|---------|-------|-----|
| `Input URL file not found` | The `--input` path is wrong. | Check the path, or run from the project folder. |
| `No URLs found in ...` | No line in the file starts with `http`. | Add full URLs, including `https://`. |
| `Could not find __NEXT_DATA__ JSON in page` | The URL isn't a GfG article, or GfG changed its page layout. | Check the URL in a browser. If every GfG URL fails, the site layout has changed. |
| `postDataFromWriteApi is missing or null` | The page is a GfG category or listing page, not an article. | Use the URL of an individual article. |
| `HTTP Error 403: Forbidden` | The site blocked the request (common on Medium). | That site isn't supported. Remove the URL or copy the content by hand. |
| `HTTP Error 404: Not Found` | The article was deleted or moved. | Remove the URL or update it. |
| `timed out` | The connection is slow or the site is slow. | Increase the limit with `--timeout 60`. |
| `Article content was empty after HTML conversion` | The article body is empty, or contains only images or embeds. | Skip it. |

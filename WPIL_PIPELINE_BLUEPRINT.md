# WPIL Batch Pipeline Blueprint
## Winning Pattern Intelligence Layer — Market-Derived Intelligence

---

## 1. Mission
WPIL Pipeline transforms raw market performance data
into enforced winning constraints used by SIC.

WPIL does NOT learn opinions.
WPIL learns ONLY from proven performance.

---

## 2. Data Sources (Read-Only)

### Platforms
- LinkedIn (primary)
- X / Twitter (secondary)

### Source Type
- Public high-performing posts only
- No private data
- No user-generated content from the system itself

---

## 3. Collection Strategy (Batch-Based)

### Trigger
- Scheduled batch execution (not real-time)
- Initial frequency: once every 7 days

### Collection Rules
- Minimum posts per niche: 300
- Maximum posts per niche: 1000
- Engagement threshold must exceed platform median

Engagement signals:
- Likes
- Comments
- Reposts / Shares
- Time since publication (decay factor)

---

## 4. Normalization Phase

Each post is normalized into:

```json
{
  "platform": "linkedin | x",
  "niche": "string",
  "raw_text": "string",
  "metrics": {
    "likes": int,
    "comments": int,
    "shares": int
  },
  "engagement_score": float
}

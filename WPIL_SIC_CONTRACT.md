# WPIL → SIC Contract
## Mandatory Decision Enforcement Interface

### 1. Purpose
This contract defines how Winning Pattern Intelligence Layer (WPIL)
injects non-negotiable success constraints into the Strategic Intelligence Core (SIC).

WPIL does NOT generate content.
WPIL does NOT evaluate ideas.
WPIL ONLY provides enforced winning constraints.

---

### 2. Invocation Timing
WPIL is invoked:
- After user input is received
- Before SIC decision logic executes
- Before any generation occurs

---

### 3. Input to WPIL
```json
{
  "platform": "linkedin | x | tiktok",
  "niche": "leadership | coaching | fintech | saas | real_estate",
  "content_signal": {
    "topic": "string",
    "intent": "educational | authority | storytelling"
  }
}

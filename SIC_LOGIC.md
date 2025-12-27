Strategic Intelligence Core (SIC)
AI DOMINATOR – V16.0
1. Role Definition

The Strategic Intelligence Core (SIC) is the governing decision engine of AI DOMINATOR.

Its sole responsibility is to decide:

What content should be generated

On which platform

With which strategic priority

Or whether generation should be aborted entirely

The SIC does NOT generate content.
The SIC issues execution directives only.

2. Input Signals

The SIC receives structured signals only.

2.1 Content Signal
{
  "topic": "string",
  "raw_text": "string",
  "intent": "inform | persuade | dominate"
}

2.2 Style Signal
{
  "style_dna": "Professional | Aggressive | Visionary | Rebel",
  "confidence_level": 0.0
}

2.3 Context Signal
{
  "platforms_available": ["linkedin", "twitter", "tiktok"],
  "time_context": "now | trend | evergreen"
}

2.4 System Memory (Read Only)
{
  "historical_scores": {
    "linkedin": 0.0,
    "twitter": 0.0,
    "tiktok": 0.0
  }
}

3. Evaluation Metrics

Each input is evaluated using the following metrics:

Curiosity Index

Shock Potential

Skimmability Score

Share Trigger Probability

Authority Signal Strength

Each metric produces a score between 0.0 and 1.0.

4. Decision Rules
4.1 Platform Selection

If Curiosity + Skimmability ≥ 1.6 → Twitter

If Authority + Depth ≥ 1.5 → LinkedIn

If Shock + Visual Bias ≥ 1.4 → TikTok

Multiple platforms may be selected.
If no rule is satisfied, execution is aborted.

4.2 Suppression Rules

If a platform score is less than 0.6, it is suppressed regardless of availability.

5. Dominance Law

Content generation MUST be aborted if any of the following conditions are met:

Curiosity Index < 0.7

Share Trigger < 0.6

Hook Strength < 0.6

No exceptions allowed.

6. Output Directive Schema

The SIC outputs a decision object only.

{
  "execute": true,
  "primary_platform": "twitter",
  "secondary_platforms": [],
  "content_mode": "thread | post | video",
  "style_override": "string",
  "rules": {
    "hook_required": true,
    "cta_type": "curiosity",
    "length": "short | medium | long"
  },
  "decision_reason": "string"
}

7. Design Constraints

The SIC must remain deterministic in V16.0

No machine learning training is allowed at this stage

The SIC must be platform-agnostic

The SIC must be callable as a standalone module

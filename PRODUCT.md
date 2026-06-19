# Product

## Register

product

## Users

Growthvine's own content and research team — the same analysts and advisors who use the Fund Analyser. They use this tool at a desk during working hours to manage an AI-powered content pipeline: reviewing AI-generated ideas from financial news, approving or refining drafts, and scheduling posts to LinkedIn, Twitter, blog, and email. The job to be done: transform raw Indian finance news into publication-ready, institutional-grade content with minimal friction and two human quality gates.

This is an internal editorial ops tool. Nobody is being sold to here; users are domain experts who already know what a content angle, a target persona, and a platform style guide are.

## Product Purpose

Content Automation 2 is a 6-agent AI pipeline that discovers Indian finance news, generates content ideas and platform-specific drafts, routes everything through two human approval gates (Gate 1: Ideas, Gate 2: Drafts), then schedules and publishes to LinkedIn, Twitter, blog, and email. An orchestrator chat agent provides conversational control over the entire pipeline.

Success looks like: a team member opens the dashboard, sees the freshest AI-generated ideas from today's research run, approves the strong ones in under a minute each, sends them to creation, reviews the resulting drafts, and schedules the best ones — all without touching config files or writing prompts.

## Brand Personality

Professional, Precise, Editorial.

Same brand promise as the Fund Analyser ("Own Your Financial Future") applied to content operations: confident curation, expert voice, no noise. The tool is a backstage control room for institutional financial content — calm, dense, reliable.

## Anti-references

- **Generic CMS dashboards** — not the beige/grey WordPress or Webflow admin aesthetic. This is Growthvine; the brand identity carries.
- **Social media management tools (Buffer, Hootsuite aesthetic)** — no colorful platform badges everywhere, no playful "scheduled!" confetti, no casual tone. This content targets CFAs and institutional investors.
- **AI product demos** — no "✨ AI-generated" sparkle callouts, no LLM-hype gradients. The AI is infrastructure, not a feature to advertise.
- **Crypto-style dark dashboards** — no neon on black, no aggressive terminal aesthetics. The terminal surfaces (worker logs) are functional, not the personality.

## Design Principles

1. **Gate discipline first.** The approval gates (Ideas → Drafts) are the core workflow. Every screen prioritizes batch decisioning: see enough context to decide fast, act with one click, move on. Information density serves speed, not status display.
2. **Content quality is visible.** Score, target persona, reasoning, source article — all immediately accessible. Decisions are traceable; reviewers are never flying blind.
3. **The brand carries the surface.** Vine Indigo for actions and identity. Neutral, calm data surfaces so content itself is what's read, not the chrome around it. Consistent with the Fund Analyser suite.
4. **Pipeline transparency.** Every agent run, every token cost, every rejection pattern is inspectable. The pipeline isn't a black box — it's a tool the team controls and can course-correct.
5. **Expert efficiency.** The primary workflow (review ideas → send to creation → review drafts → schedule) takes the fewest possible clicks. Power users are the only users; no onboarding hand-holding needed.

## Accessibility & Inclusion

WCAG AA target (AA not AAA since this is a single-team internal tool):
- Body text contrast ≥ 4.5:1; large text ≥ 3:1
- Full keyboard operability for the approval workflows
- `prefers-reduced-motion` respected on all transitions
- No color-only encoding — approval status always pairs color with text label

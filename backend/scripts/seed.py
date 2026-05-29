"""
Seeds initial data into Supabase.

Run from backend/ with venv active:
    python scripts/seed.py

What it seeds:
  1. curated_sites            — 7 initial Indian finance sites
  2. brand_memory             — 5 brand voice samples (no embeddings yet)
  3. style_guide              — empty baseline rows for each platform
  4. topic_performance_model  — default 0.5 score for 8 topic categories
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_supabase_client

INITIAL_SITES = [
    {
        "site_name":           "LiveMint Stock Market",
        "section_url":         "https://www.livemint.com/market/stock-market-news",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint IPO",
        "section_url":         "https://www.livemint.com/topic/ipo",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint Bonds",
        "section_url":         "https://www.livemint.com/market/bonds",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "LiveMint India News",
        "section_url":         "https://www.livemint.com/news/india",
        "active":              True,
        "pre_score_threshold": 6.0,  # Higher — too much general news noise
    },
    {
        "site_name":           "Business Standard Today",
        "section_url":         "https://www.business-standard.com/todays-paper",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "Business Standard",
        "section_url":         "https://www.business-standard.com",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
    {
        "site_name":           "Business Standard Mutual Fund",
        "section_url":         "https://www.business-standard.com/markets/mutual-fund",
        "active":              True,
        "pre_score_threshold": 4.0,
    },
]

BRAND_VOICE_SAMPLES = [
    {
        "content": (
            "Most people think helium is for balloons. It's actually for chips, MRI machines, and rockets.\n\n"
            "India produces zero helium domestically. Every cubic metre comes from imports, more than half of it "
            "from Qatar alone. With the Middle East now disrupted and India's semiconductor ambitions growing fast, "
            "this quiet dependency is becoming a serious problem.\n\n"
            "The gas you never think about could quietly hold back everything India is trying to build, "
            "in healthcare, space, and the chip industry."
        ),
        "platform": "linkedin",
        "published_at": None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Did you know the IPL is now the second most valuable sports media property in the world, "
            "per match behind only the NFL?\n\n"
            "What started as a cricket tournament in 2008 is now a $18.5 billion business ecosystem. "
            "The $6.2 billion media rights deal signed in 2022 repriced every franchise overnight. "
            "Rajasthan Royals just sold for $1.63 billion. Blackstone one of the world's largest private "
            "equity firms is in the room bidding for RCB.\n\n"
            "This isn't entertainment anymore. It's infrastructure for capital."
        ),
        "platform": "linkedin",
        "published_at": None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Investing becomes meaningful when it helps you stop postponing your dreams.\n\n"
            "A 55-year-old woman wanted to plan a Europe trip with her family, but arranging ₹10 lakhs "
            "together felt overwhelming. Instead of delaying it again, we helped her build a goal-based "
            "SIP portfolio designed around that dream.\n\n"
            "Because wealth creation is important, but so is creating memories."
        ),
        "platform": "linkedin",
        "published_at": None,
        "performance_metrics": {},
    },
    {
        "content": (
            "The rupee didn't just quietly slip to ₹95 against the dollar. "
            "There's a very specific reason it keeps falling — and it starts with a barrel of crude oil.\n\n"
            "India imports 85% of its crude oil. Every time global oil prices rise, India needs more dollars "
            "to pay for the same barrels. More dollars demanded means more rupees sold. "
            "More rupees in the market means each rupee is worth less. The math is that direct.\n\n"
            "The rupee doesn't fall randomly. It reacts to oil. And right now, oil is not being kind."
        ),
        "platform": "linkedin",
        "published_at": None,
        "performance_metrics": {},
    },
    {
        "content": (
            "Markets are not falling apart.\nThey are adjusting.\n\n"
            "This week had everything.\nOil moving up.\nGlobal tensions rising.\n"
            "Sector leadership quietly shifting.\n\n"
            "And yet, the bigger picture hasn't changed overnight.\n\n"
            "Broader markets are stabilising.\nDefensives are holding.\nFlows are still selective.\n\n"
            "This is what market transitions look like.\nNot loud. Not obvious. But important."
        ),
        "platform": "linkedin",
        "published_at": None,
        "performance_metrics": {},
    },
]

INITIAL_STYLE_GUIDE = [
    {"platform": "linkedin", "insights": {}},
    {"platform": "twitter",  "insights": {}},
    {"platform": "blog",     "insights": {}},
    {"platform": "email",    "insights": {}},
    {"platform": "general",  "insights": {}},
]

INITIAL_TOPIC_CATEGORIES = [
    "regulatory_news",
    "company_strategy",
    "macroeconomic",
    "behavioral_finance",
    "market_structure",
    "personal_finance",
    "ipo_and_capital_markets",
    "global_impact_on_india",
]


def seed_curated_sites(db) -> None:
    print("\n→ Seeding curated_sites...")
    for site in INITIAL_SITES:
        try:
            db.table("curated_sites").upsert(
                site, on_conflict="section_url"
            ).execute()
            print(f"  ✓ {site['site_name']} (threshold: {site['pre_score_threshold']})")
        except Exception as e:
            print(f"  ✗ {site['site_name']}: {e}")


def seed_brand_memory(db) -> None:
    print("\n→ Seeding brand_memory (no embeddings yet — added in Plan 4)...")
    for sample in BRAND_VOICE_SAMPLES:
        try:
            existing = (
                db.table("brand_memory")
                .select("id")
                .ilike("content", f"{sample['content'][:80]}%")
                .execute()
            )
            if existing.data:
                print(f"  - Already exists: {sample['content'][:60]}...")
                continue
            db.table("brand_memory").insert(sample).execute()
            print(f"  ✓ {sample['content'][:60]}...")
        except Exception as e:
            print(f"  ✗ Failed: {e}")


def seed_style_guide(db) -> None:
    print("\n→ Seeding style_guide (empty baseline)...")
    for row in INITIAL_STYLE_GUIDE:
        try:
            db.table("style_guide").upsert(
                row, on_conflict="platform"
            ).execute()
            print(f"  ✓ {row['platform']}")
        except Exception as e:
            print(f"  ✗ {row['platform']}: {e}")


def seed_topic_performance_model(db) -> None:
    print("\n→ Seeding topic_performance_model (default 0.5 scores)...")
    for category in INITIAL_TOPIC_CATEGORIES:
        try:
            db.table("topic_performance_model").upsert(
                {"topic_category": category, "performance_score": 0.5, "sample_count": 0},
                on_conflict="topic_category",
            ).execute()
            print(f"  ✓ {category}")
        except Exception as e:
            print(f"  ✗ {category}: {e}")


def main() -> None:
    print("Starting seed...")
    db = get_supabase_client()
    seed_curated_sites(db)
    seed_brand_memory(db)
    seed_style_guide(db)
    seed_topic_performance_model(db)
    print("\n✓ Seed complete.")
    print("\nNOTE: brand_memory rows have no embeddings.")
    print("After setting VOYAGE_API_KEY, run: python scripts/embed_brand_memory.py")
    print("(Written in Plan 4 — Orchestrator + Knowledge Base)")


if __name__ == "__main__":
    main()

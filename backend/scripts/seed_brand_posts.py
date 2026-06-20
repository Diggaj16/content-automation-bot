# -*- coding: utf-8 -*-
"""
Seed the 10 canonical Growthvine Capital brand posts into brand_memory WITH
embeddings, so match_brand_memory retrieves them as few-shot style examples
during content generation.

These are real published LinkedIn posts and define the house voice: bold Unicode
section headers, a strong hook, data-driven mechanism explanations, short
educational asides, a branded takeaway, and an engagement question.

Idempotent: a post already present (matched on the first 60 chars of content)
is skipped. Run from backend/ (or inside the api container):
    python scripts/seed_brand_posts.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.config import get_settings
from app.db.orm import BrandMemory
from app.db.session import session_scope
from app.agents.embedding.client import make_embed_client

# Each post is stored as a LinkedIn brand_memory row.
BRAND_POSTS: list[str] = [
    # 1 — RBI MPC
    """𝗥𝗕𝗜 𝗠𝗣𝗖 𝗝𝘂𝗻𝗲𝟮𝟬𝟮𝟲
The RBI just held its June MPC meeting, and there's a lot to cover.
Governor Sanjay Malhotra conducted the meeting and sent some strong signals about RBI's long term vision. Here's the full picture.

𝗥𝗮𝘁𝗲𝘀 𝗛𝗲𝗹𝗱
The repo rate stays unchanged at 5.25%-this is the third consecutive meeting where the RBI has held rates steady. It has kept the stance as neutral giving it the flexibility to change rates in the future.

𝗚𝗗𝗣 𝗗𝗼𝘄𝗻𝗴𝗿𝗮𝗱𝗲𝗱.𝗜𝗻𝗳𝗹𝗮𝘁𝗶𝗼𝗻 𝗣𝗿𝗲𝘀𝘀𝘂𝗿𝗲 𝗨𝗽.
The RBI has revised its FY27 GDP growth forecast to 6.6% from 6.9%, as the Iran conflict, higher energy prices, and global supply disruptions begin to impact India's economic momentum.
The FY27 inflation forecast has been raised to 5.1%,above the RBI's 4% target, reflecting the impact of rising energy costs. The central bank is also closely monitoring food prices amid heatwave concerns and the monsoon outlook.
Despite these challenges, India is expected to remain the fastest-growing major economy in the world, ahead of China and well above the global average.

𝗠𝗼𝘃𝗲𝘀 𝘁𝗼 𝗗𝗲𝗳𝗲𝗻𝗱 𝘁𝗵𝗲 𝗥𝘂𝗽𝗲𝗲
With Rupee touching a record low of 96.90 against the Dollar, RBI has decided to take action and bring foreign money back into India.

A set of structural measures designed to pull dollars in:
•𝗡𝗥𝗜/𝗢𝗖𝗜 𝗜𝗻𝘃𝗲𝘀𝘁𝗺𝗲𝗻𝘁 𝗟𝗶𝗺𝗶𝘁𝘀 𝗥𝗮𝗶𝘀𝗲𝗱: RBI has proposed increasing investment limits for NRIs and OCIs in listed Indian equities without requiring SEBI registration.
•𝗧𝗮𝘅 𝗥𝗲𝗹𝗶𝗲𝗳: Foreign Institutional Investors and the Bank for International Settlements are now exempt from capital gains tax on interest and gains from government securities.
•𝗘𝘅𝗽𝗮𝗻𝗱𝗲𝗱 𝗕𝗼𝗻𝗱 𝗔𝗰𝗰𝗲𝘀𝘀: All new 15, 30, and 40 year government bonds are eligible under the Fully Accessible Route (FAR).
•𝗘𝗮𝘀𝗶𝗲𝗿 𝗜𝗻𝘃𝗲𝘀𝘁𝗺𝗲𝗻𝘁 𝗥𝘂𝗹𝗲𝘀: Restrictions on holding periods for short-term foreign investments have been relaxed.

𝗠𝗮𝗿𝗸𝗲𝘁 𝗥𝗲𝗮𝗰𝘁𝗶𝗼𝗻
𝗥𝘂𝗽𝗲𝗲 𝗦𝘁𝗿𝗲𝗻𝗴𝘁𝗵𝗲𝗻𝘀: Following foreign investment reforms and confidence in India's strong forex reserves, the Rupee appreciated by 50 paise to an intraday high of 95.24 per US dollar.
A stronger Rupee helps contain imported inflation and gives the RBI greater flexibility to maintain an accommodative interest-rate stance.
For real estate, stable rates support affordable home loans and steady EMIs. For banks and bond markets, the tax exemption on government securities for FPIs is a positive development.

𝗧𝗵𝗲 𝗕𝗼𝘁𝘁𝗼𝗺 𝗟𝗶𝗻𝗲
Despite higher oil prices, a weaker rupee, and global uncertainty, the RBI remains focused on stability. With foreign investment reforms and FY27 GDP growth projected at 6.6%, India's growth story remains resilient.""",

    # 2 — Herding / Paytm
    """"𝗘𝘃𝗲𝗿𝘆𝗼𝗻𝗲 𝗜𝘀 𝗕𝘂𝘆𝗶𝗻𝗴 𝗜𝘁" 𝗜𝘀 𝗡𝗼𝘁 𝗮𝗻 𝗜𝗻𝘃𝗲𝘀𝘁𝗺𝗲𝗻𝘁 𝗦𝘁𝗿𝗮𝘁𝗲𝗴𝘆"

November 2021. India's biggest IPO opened for subscription. ₹18,300 crore issue, backed by global giants like SoftBank, Alibaba, and Berkshire Hathaway Every business channel was buzzing.

Your colleague applied.
Your neighbour applied.
Your uncle who usually only does Fixed Deposits - applied.

So obviously, you applied too.

That company was 𝗣𝗮𝘆𝘁𝗺.

What followed became one of the most painful lessons in modern Indian investing.
When the Crowd Becomes the Trap

𝗛𝗲𝗿𝗱𝗶𝗻𝗴 𝗕𝗶𝗮𝘀 is the tendency to follow what the majority is doing - not because you've analysed the situation, but simply because everyone else seems to be doing it.
It's like joining a long queue outside a restaurant without even seeing the menu.
In the moment, the logic feels simple: "So many smart people can't be wrong, right?"
Spoiler: They absolutely can.

𝗧𝗵𝗲 𝗣𝗮𝘆𝘁𝗺 𝗦𝘁𝗼𝗿𝘆 - 𝗔 𝗠𝗮𝘀𝘁𝗲𝗿𝗰𝗹𝗮𝘀𝘀 𝗶𝗻 𝗛𝗲𝗿𝗱𝗶𝗻𝗴
The Paytm IPO was priced at ₹2,150 per share and subscribed 1.89×, with billions pouring in driven by brand recall, media hype, and pure FOMO.
The reasoning most retail investors had?
"Paytm is a household name."
"Fintech is the future."
"Everyone is applying - it has to list at a premium."

𝗡𝗼𝗯𝗼𝗱𝘆 𝘄𝗮𝘀 𝗮𝘀𝗸𝗶𝗻𝗴 𝘁𝗵𝗲 𝗵𝗮𝗿𝗱𝗲𝗿 𝗾𝘂𝗲𝘀𝘁𝗶𝗼𝗻𝘀: Was the company profitable? No.
Was Valuation justified? Debatable. Business understood? Rarely.

On listing day, November 18, 2021, Paytm crashed 27% - the worst listing in Indian IPO history at the time. Within a year, the stock fell from ₹2,150 to around ₹440, wiping out nearly 80% of wealth.
The crowd wasn't a signal of quality. It was just noise.

𝗪𝗵𝘆 𝗗𝗼 𝗪𝗲 𝗛𝗲𝗿𝗱?
•Safety in numbers: Following the crowd once meant survival. In markets, it often means losses.
•FOMO: The fear of missing out overrides logic and leads to poor decisions.
•Outsourcing thinking: It feels safer to be wrong with everyone than alone, but it still costs you.
•Noise ≠ signal: Hype, headlines, and buzz usually mean you're late, not early.

𝗧𝗵𝗲 𝗨𝗻𝗰𝗼𝗺𝗳𝗼𝗿𝘁𝗮𝗯𝗹𝗲 𝗧𝗿𝘂𝘁𝗵 𝗔𝗯𝗼𝘂𝘁 𝗖𝗿𝗼𝘄𝗱𝘀
By the time something feels obvious, it's often already priced in.
Real wealth comes from patient bets on overlooked, boring businesses, not popular ones.
As Warren Buffett says, be fearful when others are greedy, and greedy when others are fearful.

💡The Growthvine Capital Perspective
Before your next investment, ask yourself this: "Am I buying this because I've analysed it or because everyone around me is excited about it?"
If your primary reason is the latter, you're not investing. You're herding.

Popularity is not value. A crowded trade is not a safe trade. Think independently before you invest, not after the crash.

The market rewards conviction backed by research. It punishes enthusiasm backed by noise.""",

    # 3 — FY26 IPO market
    """𝗧𝗵𝗲 𝗙𝗬𝟮𝟲 𝗜𝗣𝗢 𝗺𝗮𝗿𝗸𝗲𝘁 𝘀𝗲𝘁 𝗮 𝗿𝗲𝗰𝗼𝗿𝗱 𝘆𝗲𝘁 𝘁𝗵𝗲 𝗱𝗮𝘁𝗮 𝗯𝗲𝗵𝗶𝗻𝗱 𝗶𝘁 𝘁𝗲𝗹𝗹𝘀 𝗮 𝗱𝗶𝗳𝗳𝗲𝗿𝗲𝗻𝘁 𝘀𝘁𝗼𝗿𝘆.
India raised ₹1.77 lakh crore through 109 IPOs in FY26 which is the highest ever. But 72 of those 109 companies are now trading below their issue price. That's not just a bad year for a handful of weak names but a structural problem hiding inside a headline.

For context, an IPO is when a company sells its shares to the public for the first time. The "issue price" is what investors pay. If the stock trades below that price afterwards, early investors are sitting on a loss. In FY26, that happened to roughly two thirds of all IPOs.

The subscription numbers are worth a closer look. Top 10 performers averaged 54x subscriptions while the bottom 10 averaged 26x. The instinct is to read that as demand predicting quality. But it doesn't hold. Forty-nine of the 109 IPOs received single-digit subscriptions and several are still comfortably above issue price. Some of the most aggressively bid-up offerings quietly gave it all back.

Here's the part that should bother people more: of the 72 IPOs now below issue price, 32 had actually listed at a gain. Investors who sold on Day 1 made money. Investors who held it lost it. That's not a story about bad businesses. That's what happens when a stock is priced so tight at IPO that it has nowhere to go once the listing pop fades. The upside got captured at the offer stage by promoters, by bankers, by anchor allocations. Public investors absorbed the risk with none of the buffer.

Larger deals fared better as a group, returning around 12% on a basket basis versus 7.5% for the full set. But even the marquee names weren't spared. PhysicsWallah, WeWork India, Pine Labs, Clean Max Enviro which are real companies, real revenues, genuine market presence, they were all down between 17% and 30%. None of them had bad businesses. All of them had bad entry prices.

FY26 didn't fall short because the market ran out of companies worth backing. It fell short because too many of those companies showed up asking for tomorrow's valuation today.

What is your read on IPO valuations heading into FY27? Are investors going to stay cautious or will the next big name reset expectations all over again?""",

    # 4 — The Gas War
    """𝗧𝗛𝗘 𝗚𝗔𝗦 𝗪𝗔𝗥

This is no longer a Strait of Hormuz story.
We all thought this was a logistics problem.

The working thesis was straightforward:
The Strait of Hormuz was the choke point. Open it up, let ships pass, and eventually oil stabilizes, gas cools, and markets find their footing again.

That framework just got blown up. Literally.

On March 18, Israel struck South Pars, the world's largest natural gas reserve. Iran didn't blink. It responded by targeting Qatar's Ras Laffan LNG terminal, one of the most critical energy hubs globally, knocking out an estimated 17% of Qatar's LNG export capacity and wiping out roughly $20 billion in projected annual revenue.

And it didn't stop there.

The UAE's Habshan gas facility and Bab oilfield have been shut down.
Saudi Arabia intercepted ballistic missiles headed for Riyadh.

Pause for a moment and take that in.

This is no longer about ships being delayed or rerouted.
This is no longer about whether the Strait stays open.

This is about something far more serious.
Production. Processing. Core energy infrastructure.

The earlier assumption was that once the war ends, supply normalizes.

But how do you "normalize" a damaged gas field?
How quickly do you rebuild an LNG terminal?
How long before processing capacity comes back online?

These are not weeks. These are months and may be years in some cases.

Which means even if the conflict de-escalates tomorrow, the supply shock doesn't simply disappear with it.

Markets are beginning to sense that shift which led to a brutal sell-off yesterday.

Brent crude has already crossed $107 per barrel.
European natural gas benchmarks jumped 6% in a single day.
The Fed is pausing rate decisions, partly because of the economic fog this war is creating.

The narrative around the war has changed.
This was supposed to be a temporary disruption.
It is now starting to look like a structural one.

𝗛𝗲𝗿𝗲'𝘀 𝘁𝗵𝗲 𝗶𝗻𝘃𝗲𝘀𝘁𝗼𝗿 𝘁𝗮𝗸𝗲𝗮𝘄𝗮𝘆:
▸Supply disruption is no longer theoretical
▸Energy volatility is the new normal, not a spike
▸Portfolios with zero energy or commodity exposure are exposed to inflation risk right now

The Strait of Hormuz was always the door. Now someone's burning the house.""",

    # 5 — Rate cuts vs bond yields / state borrowing
    """𝗜𝗻𝗱𝗶𝗮'𝘀 𝗰𝗲𝗻𝘁𝗿𝗮𝗹 𝗯𝗮𝗻𝗸 𝗰𝘂𝘁 𝗿𝗮𝘁𝗲𝘀 𝗳𝗼𝘂𝗿 𝘁𝗶𝗺𝗲𝘀 𝗶𝗻 𝟮𝟬𝟮𝟱 𝗮𝗻𝗱 𝗯𝗮𝗿𝗲𝗹𝘆 𝗮𝗻𝘆𝘁𝗵𝗶𝗻𝗴 𝗰𝗵𝗮𝗻𝗴𝗲𝗱. 𝗛𝗲𝗿𝗲 𝗶𝘀 𝘁𝗵𝗲 𝗳𝘂𝗹𝗹 𝗽𝗶𝗰𝘁𝘂𝗿𝗲.

Most people assume that when the RBI cuts interest rates, borrowing gets cheaper, investments in bonds grow, and the economy gets a gentle push forward. That assumption held for most of modern economic history, which is why what happened in 2025 is worth paying attention to. The RBI cut rates four times totalling 125 basis points across the year, one of the most aggressive attempts at economic easing India has seen in recent memory, and the 10-year government bond yield moved just 17 basis points in response, actually rising the day after the final cut rather than falling.

The central government's budget was not the issue here. A 4.4% fiscal deficit with sensible numbers behind it was credible enough that respected economists openly praised it, and under normal circumstances that kind of fiscal discipline combined with aggressive rate cuts would have pushed bond yields down sharply. What the bond market was actually focused on was the borrowing behaviour of India's 28 state governments, which operate independently and collectively borrowed Rs 12 trillion in FY25 alone, a 20% jump from the year before. Several states launched large welfare schemes funded not from existing savings but from fresh bonds being sold into the same market every single quarter.

That steady wave of new bonds kept upward pressure on yields, largely offsetting the RBI's attempts to push them down.

By December, the stress was visible. Oversized state bond auctions pushed yields to a nine month high, a major government backed lender cancelled its own bond sale because buyers had disappeared, and the RBI had to step in with large liquidity operations to stabilize markets. The rupee falling 4.74% against the dollar across the year, made the situation worse for foreign investors who were already watching their returns shrink.

The RBI controls the price of money but not how much of it 36 governments decide to borrow in an election year, and that is the number the bond market was reading all along. If state level borrowing continues at this pace through FY27, the transmission problem does not go away regardless of how many more cuts the RBI delivers.""",

    # 6 — 100% FDI in Insurance
    """What 100% FDI in Insurance Really Means for India
India has recently allowed 100% foreign direct investment in the insurance sector.
This move aligned with the Government's goal of Insurance for all by 2047. But does it really solve the problem?

India's insurance market is still underinsured

India's insurance penetration at around 4%, which is lower than the global average of 7%.

This gap is not solely due to a lack of demand, but also to limited access, less financial literacy,  low product awareness, and a shortage of long-term capital. The objective of opening this sector completely to foreign ownership is precisely to address these shortcomings.

Global insurance companies have long viewed India as a growth market, but they have been constrained by ownership restrictions. This was the very reason why Allianz ended its 24-year partnership with Bajaj Allianz by selling its 26% stake.

Now, with full ownership, they can invest with strategic control, enabling them to participate in decision-making. This is especially true, as insurance is a long-gestation business that requires a long-term commitment.

What changes for consumers

Increased competition typically leads to better product design, wider coverage options, and improved service standards. Global insurance companies bring expertise in health, retirement, and protection products, areas that are still developing in India.
Over time, this can lead to improvements in both choice and quality.

But FDI alone won't be enough as Insurance in India still depends on agents, bancassurance, and digital platforms. Domestic players with strong distribution networks will remain important, even as ownership structures change.

Why this matters for India's economy

Insurers are long-term investors in bonds, the stock market, and infrastructure. More insurers can further financialise savings, channeling long-term household funds into productive assets such as infrastructure, government bonds, and corporate debt.

Overall, this reform is less about FDI and more about accelerating insurance adoption in India. If executed well, it improves households' financial security and deepens the financial system.

For consumers, it could mean greater choice, more tailored insurance products, and improvements in service standards as competition increases and global players bring deeper underwriting and claims expertise into the Indian market.""",

    # 7 — Rupee depreciation
    """How Rupee Depreciation Impacts India
This year, the Indian Rupee (INR) has weakened by around 6% against the US dollar trading around 90 per dollar. Several factors explain this fall:
Most notably, sales by foreign portfolio investors amounted to ₹1.5 lakh crore (as of 4 November 2025). Trade tariffs imposed by the U.S. led India to export less and import more, widening the country's trade and current account deficits (CAD).
Higher CAD means we're spending more dollars on imports than we earn from exports. This puts pressure on the rupee and increases the need for foreign capital to cover the shortfall.
Negative Impact of Rupee Depreciation
A weaker rupee affects the economy in several interconnected ways:
First, imports become more expensive. We import more than 80% of our crude oil requirements, along with other key commodities. When the rupee weakens, we need more rupees to pay for the same quantity, and that pushes prices higher at home. You can also call it imported inflation.
Manufacturers and industries dependent on imported raw materials may face rising input costs, which can feed into inflation and compress margins.
For eg: Indigo booked a forex loss of about ₹2,892 crore in Q2, compared with ₹204 crore in the previous one, because the weaker rupee made its dollar expenses much costlier.
Furthermore, a weak currency can dampen foreign investor sentiment. This is because a weak rupee reduces their overall returns.
It isn't all downside.
A weaker rupee can boost parts of the economy that earn in foreign currencies or depend on remittances.
Indian exporters may find their goods more competitive internationally, as buyers abroad get more value for their dollars. This dynamic may benefit sectors such as IT services, pharmaceuticals, and other export-oriented sectors, potentially improving their profitability.
Remittances also hold greater value: money sent by Indians working abroad gets more rupees back at home, which can boost household incomes and consumption.
In a broader sense, some exporters and foreign-earnings firms may find renewed confidence, which could translate into more hiring, reinvestment, or even expansion plans.
What this means for India's macro outlook
While a weaker rupee does offer some support to exporters and remittance-receiving households, the net-effect of rupee depreciation is negative.
India remains a heavily import-dependent economy and every additional rupee of depreciation directly worsens the import bill.
A wider current account deficit combined with persistent foreign investor outflows means India needs more overseas capital just to balance its books. But a falling currency discourages that very capital from coming in. This creates a vicious cycle: weaker rupee → lower foreign flows → even weaker rupee.""",

    # 8 — Nifty all-time high / narrow rally
    """Nifty Hit an All-time High after 14 Months

After more than a year of a long correction followed by a long consolidation, the Nifty finally crossed its previous all-time high of 26,277, a level last seen in September 2024.

The earlier fall came after valuations ran too high last year, and the market needed time to cool off and settle before moving again. All-time highs generally point to three things:

1) Investors are expecting healthy corporate earnings from large companies,
2) Liquidity from institutions is strong,
3) The economic backdrop is supportive

On the surface, this appears to be a sign of strength. But beneath it, the market is telling a different story. There is a clear divergence.
The Nifty has climbed to a new peak, yet many investors' portfolios are in the red.

It's because the index rally is narrow and driven mainly by a handful of heavyweight stocks. As per Moneycontrol, the data makes this even clearer:

1) Just six giants, Reliance, HDFC Bank, Bharti Airtel, SBI, L&T and Axis Bank, contributed nearly 60% of Nifty's recent 1,550-point rise.
2) Another 7–8 names, including Infosys, HCL Tech, TCS, M&M, ICICI Bank and Asian Paints, together added another 25–30%.
3) The remaining stocks, more than half of the Nifty, accounted for only about 15% of the total gain.

Another set of numbers paints an even more sobering picture of market breadth. Out of the top 750 companies by market cap:

*Only 252 stocks have gained this year, and
*464 stocks have fallen
*The median return is about minus 10.5%
*The average return sits near minus 5%
*268 stocks have dropped more than 20%
*Only 117 stocks have gained more than 20%

Broader indices reflect the same: The Nifty Smallcap index is still about 10% below its own peak, and only 39% of its stocks are trading above their 200-day moving averages.  That signals weak participation from the broader market outside the large-cap universe.

This pattern shows that the market is being carried by a small group of companies while a large number of stocks remain far below their highs.

The reason is tied to valuations. Mid- and small-cap stocks continue to trade at richer multiples, even as Nifty valuations have cooled.

The Nifty 50 now trades at a P/E of about 22.8, close to its five-year median.
In contrast, the Nifty Smallcap 100 trades at around 32 times earnings, roughly 10% higher than its 5Y median of 29 times. The mid-cap indices show a similar pattern.

So, while the Nifty's high is welcome, the market will only strengthen if the broader market performs, which could happen soon. This is because, after a long consolidation, large-caps move up first, followed by mid-caps, and finally small-caps catch up.""",

    # 9 — Groww short squeeze
    """Groww– a textbook case of a short squeeze.
Groww, India's largest brokerage by number of investors, had a blockbuster listing. The company listed at ₹114 per share, a 14% increase from its IPO price.
Although the listing was at a modest premium, what followed thereafter was surreal. The share price jumped 70% in the subsequent four trading sessions to ₹193.8.
One prime reason behind this sharp rally was the low free float. Groww free float is around 8%, which means only a tiny portion of the total shares are available for regular buying and selling in the market.
Meanwhile, many traders expected Groww's share price to fall, so they took short positions (selling shares they did not own, hoping to repurchase them at lower prices).
What they didn't count on was how fast the rise would be, and how difficult it would be to repurchase those shares when needed.
As demand outstripped supply due to the lower float, those short positions began to be squeezed. Exchange data shows that more than 30 lakh shares went into the auction window because sellers could not deliver their unsold shares.
That forced them to buy at higher prices (or pay penalties), and that added fuel to the upward move for a while.
For example: If you shorted a stock yesterday (day T), you are compulsorily required to return the shares the next day (T+1). However, since they couldn't return those shares, the exchange intervened the next day.
Then comes the real shocker.
The exchange conducts a separate buy-in auction the next day (T+2).
It attempts to buy the same number of shares that you failed to deliver and returns them to the buyer who was hoping to purchase them.
As you failed to deliver them on time, the exchange will calculate the amount you owe based on yesterday's closing price (the price at which the stock closed the day before the shares were supposed to be delivered).
If the exchange failed to procure shares through the auction, then a settlement is done. In that case, the buyer receives cash rather than shares at a close-out price, which is the higher of:
The highest share price between trade day (T) and auction day, or
20% above the official closing price on the auction day (or the preceding day).
There are penalties on these as well… so, in effect, those who fail to deliver find themselves trapped in a colossal loss trap.
What does this mean for an investor? Stocks with a low float are highly volatile and can trap both buyers and sellers with sharp moves. Hence, it's ideal to wait for the euphoria to settle down before taking a position.""",

    # 10 — New EPF rule
    """What does the new EPF Rule mean for you?

In a major step toward expanding access to provident fund (PF) savings, the EPFO has made major changes to withdrawal rules. This new framework now combines three broad categories (from 13 separate categories previously) – essential, housing, and special needs.

The biggest change is that members can withdraw up to 100% of their eligible PF balance, including both the employee and employer contributions. This is a big relief for members who often find their balance stuck.

But there is a catch.

To ensure members' safety net for retirement, they can withdraw only 75% of the balance, and a minimum balance of 25% is required to be maintained each time. The employment period for such withdrawals has also been standardized to a uniform 12 months.

Previously, the period was 7 years for marriage, 5 years for home ownership, and 2 months for unemployment. While this will benefit others, it's a major setback for the unemployed, who will now have to wait 12 months to withdraw their funds, instead of the current 2 months.

The pension withdrawal limit has also been increased from 2 months to 36 months.

Additionally, there are additional exemptions. Members can now withdraw up to 10 times for education purposes and up to five times for marriage, compared to the previous limit of three. The reason for withdrawal will also no longer be asked.""",
]


def main() -> None:
    settings = get_settings()
    client = make_embed_client(
        google_api_key=settings.google_api_key,
        local_model=settings.local_embedding_model,
    )
    print(f"embed client: {type(client).__name__}")

    with session_scope() as db:
        # Skip posts already present (match on first 60 chars)
        pending: list[str] = []
        for post in BRAND_POSTS:
            probe = post[:60]
            existing = db.execute(
                select(BrandMemory.id).where(BrandMemory.content.ilike(f"{probe}%"))
            ).first()
            if existing:
                print(f"  -- already present: {probe[:48]!r}")
            else:
                pending.append(post)

        if not pending:
            print("All brand posts already seeded. Nothing to do.")
            return

        vectors = client.embed(pending, for_query=False)
        inserted = 0
        for post, vec in zip(pending, vectors):
            row = {"content": post, "platform": "linkedin", "performance_metrics": {}}
            if vec:
                row["embedding"] = vec
            try:
                db.add(BrandMemory(**row))
                db.commit()
                inserted += 1
                dim = len(vec) if vec else 0
                print(f"  OK  inserted ({dim}-dim): {post[:48]!r}")
            except Exception as exc:
                db.rollback()
                print(f"  FAIL {post[:48]!r}: {exc}")

    print(f"\nDone. {inserted}/{len(pending)} brand posts seeded with embeddings.")


if __name__ == "__main__":
    main()

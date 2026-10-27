# Source Registry: Evidence for the LogosDepth Memorization Design

Compiled 22 Oct 2026. Companion to `memory-science.md`.

**Purpose:** for each core design lever, list the strongest independent sources, say how well each is corroborated, and flag which sources are trustworthy vs. which to treat with caution.

## Limits (read first)

- The research environment could not open PubMed, PMC, publisher sites, or most other pages directly. Everything here comes from **web-search results** (abstracts, citation records, and summaries). **No figure below was checked against a full paper.** "Abstract-level" below means the number appeared in an abstract or official record as returned by search; "secondary" means it came from a later paper, blog, vendor or news page.
- A short list of papers to open and check yourself is at the end.

## Source tiers

| Tier | What it is | Examples | How I treat it |
|---|---|---|---|
| **A** | Peer-reviewed meta-analyses, randomized trials, government/charity evidence reviews | *Psychological Bulletin*, *Review of Educational Research*, *Educational Psychology Review*, *Science*; IES Practice Guide; EEF review | Basis for claims |
| **B** | Expert lab sites and curated hubs run by the researchers | [Bjork Lab (UCLA)](https://bjorklab.psych.ucla.edu/), [Purdue Learning Lab (Karpicke)](https://learninglab.psych.purdue.edu/), [Learning Scientists](https://www.learningscientists.org/), [RetrievalPractice.org](https://retrievalpractice.org/review) | Good for locating papers and plain-language explanations; cite the papers, not the site |
| **C** | Secondary summaries: blogs, newsletters, vendor pages, AI-generated summaries | study-aid blogs, Substack write-ups, spaced-learning vendors, auto-summary pages | **Do not cite for numbers.** Used here only to locate leads, and labelled when a number rests on one |

---

## Core levers: evidence ladder

Legend: 🟢 consistent across meta-analyses and applied trials · 🟡 supported but narrower, smaller, or with gaps

### 1. Retrieval practice (testing effect) 🟢

| Source | What it is | Key finding | Verification |
|---|---|---|---|
| [Rowland 2014](https://doi.org/10.1037/a0037559), *Psychol Bull* | Meta-analysis | Testing beats restudy, g ≈ 0.50; **abstract states initial recall tests give larger benefits than recognition tests** | Abstract-level (recall > recognition); sample (159 effect sizes, 61 studies) and feedback split (g ≈ 0.73 vs 0.39) are secondary (Tier C) |
| [Adesope et al. 2017](https://journals.sagepub.com/doi/10.3102/0034654316689306), *Rev Educ Res* | Meta-analysis | Practice tests beat restudy and other comparisons; moderated by test features | Secondary for size (118 articles, 272 effects, 15,472 participants, from a vendor page); format breakdown **not verified** |
| [Yang et al. 2021](https://doi.org/10.1037/bul0000309), *Psychol Bull* | Meta-analysis, **classroom** quizzing | **g = 0.499**, 222 studies, 48,478 students; moderated by feedback, repetitions, control condition | Abstract-level ([HKBU record](https://scholars.hkbu.edu.hk/en/publications/testing-quizzing-boosts-classroom-learning-a-systematic-and-meta-/); [open copy](https://gwern.net/docs/spacedrepetition/2021-yang.pdf)) |
| [Agarwal, Nunes & Blunt 2021](https://retrievalpractice.org/review), *Educ Psychol Rev* | Systematic review, 50 school/classroom experiments | 57% of experiments showed medium or large benefits; held across levels, formats, delays | Abstract-level. Limits: few non-WEIRD samples; no primary-school experiments found per one summary. Database of the experiments is public |
| [Donoghue & Hattie 2021](https://www.frontiersin.org/articles/10.3389/feduc.2021.581216/pdf), *Front Educ* | Meta-analysis of the 10 Dunlosky techniques | 242 studies, 1,619 effects, mean 0.56; **practice testing and distributed practice ranked highest** | Abstract-level for scope and ranking; individual effect sizes (0.74, 0.85) only from a blog. Caveat: mostly factual outcomes |
| [Dunlosky et al. 2013](https://pubmed.ncbi.nlm.nih.gov/26173288/), *Psychol Sci Public Interest* | Systematic evaluation of 10 techniques | Practice testing and distributed practice = high utility | Confirmed by multiple citing papers |
| [IES Practice Guide 2007](https://ies.ed.gov/ncee/wwc/pdf/practice_guides/20072004.pdf) (Pashler et al.) | US Dept. of Education expert panel | Quizzing to re-expose material rated **strong**; spacing rated **moderate** (it predates later meta-analyses) | **Ratings from a third-party blog summary; read the guide itself.** Link as cited by search |
| [EEF 2021 review](https://educationendowmentfoundation.org.uk/news/new-what-do-we-really-know-about-cognitive-science-in-the-classroom-eef-publishes-new-review-of-the-evidence/) | UK charity systematic review (>40,000 papers screened, ~300 analyzed) | Principles helpful, but **classroom-application evidence is limited**; school retrieval studies mostly use researcher-written questions identical to the final test | Press-release level |
| Larsen, Butler & Roediger 2009, *Med Educ* 43:1174 | **Randomized trial**, medical residents | Repeated testing beat repeated study at long delays | Citation confirmed; results from secondary ([Learning Scientists podcast](https://www.learningscientists.org/learning-scientists-podcast/2018/5/16/episode-19-bite-size-research-on-benefits-of-retrieval-with-medical-residents)); sample not verified |

**Honest summary:** the *benefit of recall over re-reading* is as well supported as anything in this field (lab, classroom, trial). The weaker points: most applied tests are factual content with test questions matching practice questions (EEF), and **none of these studies is about verbatim memorization of long text.**

### 2. Spacing 🟢

| Source | What it is | Key finding | Verification |
|---|---|---|---|
| [Cepeda et al. 2006](https://pubmed.ncbi.nlm.nih.gov/16719566/) | Review/quantitative synthesis, 839 assessments, 317 experiments, 184 articles | Spacing beats massing for verbal recall; benefit clear at long retention intervals | Record-level |
| [Cepeda et al. 2008](https://pubmed.ncbi.nlm.nih.gov/19076480/) | Large experiment, >1,350 learners | Optimal gap grows with retention interval; as a proportion it shrinks (~20–40% of a 1-week delay to ~5–10% of a 1-year delay) | Secondary for the proportions |
| [Latimier, Peyre & Ramus 2021](https://doi.org/10.1007/s10648-020-09572-8), *Educ Psychol Rev* | Meta-analysis of **spaced retrieval**, 29 studies | Spaced beats massed retrieval, **g ≈ 0.74**; **expanding schedules show no clear advantage over equal spacing** (g ≈ 0.03); combining spacing and retrieval beats either alone | Abstract-level for 0.74 and expanding-vs-uniform; "combined beats either" from a news roundup |
| [Bahrick et al. 1993](https://digitalcommons.fiu.edu/psychology_fac/50), *Psychol Sci* | Long-term study, **only 4 participants**, 300 word pairs | 13 sessions spaced 56 days apart gave retention like 26 sessions spaced 14 days apart; benefit of spacing independent of number of sessions | Abstract-level. Earlier work (Bahrick & Phelps 1987): even after 30-day spacing, 8-year recall was only ~9% overall |
| [Carpenter, Pan & Butler 2022](https://profiles.wustl.edu/en/publications/the-science-of-effective-learning-with-spacing-and-retrieval-prac/), *Nat Rev Psychol* | Review spanning 100+ years | Spacing and retrieval are among the most robust findings; **learners underuse them** | Paywalled; abstract and press coverage only |
| [Weinstein, Madan & Sumeracki 2018](https://eprints.nottingham.ac.uk/48517), *Cogn Res Princ Implic* | Open-access tutorial review | Six strategies with long research support: spacing, interleaving, retrieval, elaboration, concrete examples, dual coding | Record-level; **open access, good starting read** |
| Murre & Dros 2015, [*PLOS ONE*](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644) | Replication of Ebbinghaus | Replicates the shape of the forgetting curve | **Single subject**; no independent replication listed ([FLoRA](https://forrt.org/flora-replication-atlas/doi/10.1371/journal.pone.0120644/)) |

**Honest summary:** spacing is robust, but **no source tells us the exact interval pattern.** The evidence supports "space it out, scaled to how long you need to remember," not a specific schedule. The Bahrick data are long-term but tiny-sample.

### 3. Successive relearning 🟡🟢

| Source | Key finding | Verification |
|---|---|---|
| [Rawson, Dunlosky & Sciartelli 2013](https://www.scinapse.io/papers/1996943074), *Educ Psychol Rev* | Intro-psychology course, 64 concepts: students retrieved each concept correctly **3 times** across sessions; compared with spaced restudy and no-program controls; improved exam performance | Design confirmed; effect sizes **not** verified |
| [Rawson et al. 2018](https://pubmed.ncbi.nlm.nih.gov/29431462/) | Large gains vs single-session; initial-learning differences shrink after relearning | Record-level |
| A 2020 follow-up (Rawson, Dunlosky & Janes) tested a **boundary condition**, so the effect may not be universal | Mentioned in a search result | Unverified |

**Why it matters:** this is the closest evidence to "mastery = recall on separate days," but it is a classroom/college literature on concepts, not verses.

### 4. Typed/produced recall vs. recognition (multiple choice, word banks) 🟡

- **For recall:** Rowland's abstract reports bigger benefits from initial *recall* tests than *recognition* tests. [Roediger & Butler 2011](https://profiles.wustl.edu/en/publications/the-critical-role-of-retrieval-practice-in-long-term-retention/) warn that **multiple-choice and true/false items can backfire** (wrong lures can be learned); general right/wrong feedback helps little unless the correct answer is shown.
- **Against a strong claim:** a [2024 head-to-head](https://pmc.ncbi.nlm.nih.gov/articles/PMC11684041/) of very-short-answer vs. multiple-choice found no difference; a [university study](https://pubmed.ncbi.nlm.nih.gov/30564174) found short-answer but not multiple-choice produced a testing effect.
- **Verdict:** the direction favors recall, but this is "supported," not "settled." For verses the real-life target *is* recall, so typed recall remains the better rehearsal. Always show the correct text after each attempt.

### 5. Adaptive scheduling by software 🟡

| Source | Key finding | Verification |
|---|---|---|
| [Upadhyay et al. 2021](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8421401/), *npj Sci Learn* | **Randomized trial, 50,700 learners**, ~16.75M answers; algorithm-chosen questions → remembered ~69% longer | Abstract-level. Content: a driving-theory (mobility) app, i.e. **factual items, not verbatim text**. Same group built the algorithm |
| [Settles & Meeder 2016](https://preview.aclanthology.org/landing_page/P16-1174) (Duolingo), ACL | Half-life regression cut recall-prediction error 45%+; engagement +12% in an operational test | **Company-reported**; no independent replication found |
| [Kornell & Bjork 2008](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/07/Kornell_Bjork_2008_Memory.pdf) | Students almost always drop flashcards they think they know; allowing dropping had small negative effects | Via a search summary; also see [Kornell & Bjork 2007](https://sites.lifesci.ucla.edu/psych-bjorklab/wp-content/uploads/sites/13/2016/07/Kornell_RBjork_2007.pdf) (details not verified) |

**Design implication:** let the app decide what is due and don't let learners retire a verse early. A simple fixed-interval schedule is supported; a fancy model is a bonus, not a requirement.

### 6. Secondary levers (supported but smaller or narrower) 🟡

| Lever | Source | Finding |
|---|---|---|
| Generation effect | [Bertsch et al. 2007](https://pubmed.ncbi.nlm.nih.gov/17645161/) | **86 studies, 445 effect sizes, overall ≈ 0.40** (PubMed abstract). Later failure on expository text |
| Interleaving | [Brunmair & Richter 2019](https://www.psychologie.uni-wuerzburg.de/fileadmin/06020400/2019/Brunmair_Richter_in_press__2019_META-ANALYSIS_OF_INTERLEAVED_LEARNING.pdf) | **59 studies, 238 effects, overall g ≈ 0.42**; large heterogeneity; strongest for visual categories (paintings g ≈ 0.67), smaller for math |
| Gamification | [Sailer & Homner 2020](https://link.springer.com/article/10.1007/s10648-019-09498-w) | Cognitive g = .49 [.30, .69], k = 19, N = 1,686; motivational .36; behavioral .25; the cognitive effect held in the high-rigor subset |
| Desirable difficulties | [Bjork & Bjork 2011](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/04/EBjork_RBjork_2011.pdf) | Spacing, interleaving, testing, and generation as "desirable difficulties," **but a difficulty is only desirable if the learner can handle it.** This supports scaffolding beginners |

---

## Corrections to earlier claims (from this round)

| Earlier claim | Correction |
|---|---|
| Sailer & Homner: "0.26 motivational" | **0.36 motivational** (cognitive .49, behavioral .25) |
| Murre & Dros "replicated Ebbinghaus" | **Single-subject** study; no independent replication found |
| Roadmap: reviews at "widening gaps" | Meta-analysis finds **no clear advantage for expanding over equal spacing** |
| Karpicke & Roediger 2008 "80% vs 33–36%" | **Could not re-confirm** the figures. Confirmed instead: 40 students, 40 word pairs, 8 study/test periods; learning at end of training was nearly identical across conditions; the difference appeared only on delayed tests |
| Kerfoot et al. spaced-education trials | A "170% more retention" claim appears on a magazine/vendor page and is **not reliable**; the 2007 *Med Educ* randomized trial (1,067 students per that page) is real, but its results are not verified here |

## Weaknesses that apply to the whole evidence base

1. **Material:** mostly facts, word pairs, and short passages. **No study here tests memorizing long verbatim text or scripture.**
2. **Test match:** applied studies often use practice questions identical to the final test (EEF).
3. **Population:** mostly undergraduates, medical learners, and school pupils in WEIRD countries; few older adults or general-public samples.
4. **Delay:** many outcomes are measured days or weeks later, not months or years (Bahrick is the exception, with 4 people).
5. **Commercial sources:** several spaced-learning claims come from vendors or the app company itself.
6. **Standardized effect sizes** (g ≈ 0.4–0.8) describe averages; individual learners vary and heterogeneity is large.

## Primary papers to read in full (priority order)

I could not open these; checking them would convert "search-summary level" into "verified."

1. **Yang et al. 2021** (classroom testing meta-analysis): [open copy](https://gwern.net/docs/spacedrepetition/2021-yang.pdf)
2. **Rowland 2014** (testing effect meta-analysis; recall vs recognition; feedback): DOI 10.1037/a0037559
3. **Latimier et al. 2021** (spacing × retrieval; expanding vs equal): DOI 10.1007/s10648-020-09572-8
4. **Donoghue & Hattie 2021** (open access): [Frontiers PDF](https://www.frontiersin.org/articles/10.3389/feduc.2021.581216/pdf)
5. **Weinstein et al. 2018** (open access overview): DOI 10.1186/s41235-017-0087-y
6. **Upadhyay et al. 2021** (50,700-learner RCT, open access): [PMC8421401](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8421401/)
7. **IES Practice Guide 2007** (confirm the strong/moderate ratings): [PDF](https://ies.ed.gov/ncee/wwc/pdf/practice_guides/20072004.pdf)
8. **Agarwal et al. 2021** and its [experiment database](https://retrievalpractice.org/review)
9. **EEF 2021 review** (full report, not the press release)
10. **Rawson et al. 2013 and 2018** (successive relearning; look for the criterion-of-3 details)

## Sites worth bookmarking (Tier B)

- [Bjork Learning and Forgetting Lab, UCLA](https://bjorklab.psych.ucla.edu/): free PDFs of many classic papers
- [Purdue Learning Lab (Karpicke)](https://learninglab.psych.purdue.edu/): retrieval-practice papers and supplementary materials
- [Learning Scientists](https://www.learningscientists.org/): researcher-run explainers and podcast
- [RetrievalPractice.org](https://retrievalpractice.org/review): practical guides and the classroom-experiments database
- [Education Endowment Foundation](https://educationendowmentfoundation.org.uk/): independent evidence reviews with strength-of-evidence ratings

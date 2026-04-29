/**
 * LLM Retail Flow Signal — Capture Schema & Seed Corpus Generator
 *
 * Captures ticker recommendations from consumer LLMs across thematic
 * prompts to measure convergence density as a retail flow signal.
 *
 * No capital at risk. No trade instructions. Research only.
 *
 * Task ID: c40be891-9594-4b20-ae35-629c242e189f
 */

// -- Capture Schema --------------------------------------------------------

export interface PromptTemplate {
  id: string;
  template: string;       // "{theme}" replaced at runtime
  intent: "direct_picks" | "how_to_invest" | "pure_plays" | "etf_vs_stock" | "risk_aware";
}

export interface ThemeConfig {
  theme_id: string;
  theme_name: string;
  category: "tech" | "health" | "energy" | "finance" | "materials";
  mainstream_status: "emerging" | "growing" | "peak_hype" | "post_peak";
}

export interface CaptureRecord {
  // Metadata
  capture_id: string;
  timestamp_utc: string;
  model_slot: "gpt5" | "claude" | "gemini" | "perplexity" | "grok";
  model_version: string;
  status: "captured" | "unavailable" | "error" | "refused";
  error_detail: string | null;

  // Prompt
  theme_id: string;
  prompt_id: string;
  prompt_text: string;

  // Extracted tickers
  tickers: TickerMention[];

  // Raw excerpt (redacted if needed)
  response_excerpt: string;
}

export interface TickerMention {
  ticker: string;
  company_name: string;
  rank_in_response: number;        // 1 = mentioned first
  mention_type: "direct_recommendation" | "hedged_mention" | "pure_play" | "comparison" | "warning";
  qualifying_language: string;     // e.g., "leading provider", "speculative", "established player"
  repeated_in_response: boolean;   // mentioned more than once
}

export interface ConvergenceScore {
  ticker: string;
  company_name: string;
  theme_id: string;

  // Cross-model density
  models_mentioning: number;       // out of 5
  total_mentions: number;          // across all prompts/models
  avg_rank: number;                // average position in responses
  direct_recommendation_count: number;
  hedged_mention_count: number;

  // Convergence score: 0-1
  convergence_score: number;       // (models_mentioning/5) * 0.5 + (1/avg_rank) * 0.3 + (direct/total) * 0.2
  convergence_tier: "high" | "medium" | "low";
}

// -- Prompt Bank -----------------------------------------------------------

export const PROMPT_TEMPLATES: PromptTemplate[] = [
  { id: "best_stocks",      template: "What are the best {theme} stocks to buy right now?",                    intent: "direct_picks" },
  { id: "how_to_invest",    template: "How should I invest in {theme}?",                                       intent: "how_to_invest" },
  { id: "pure_plays",       template: "What are the pure play {theme} stocks?",                                intent: "pure_plays" },
  { id: "top_5",            template: "Give me the top 5 {theme} companies to invest in",                      intent: "direct_picks" },
  { id: "etf_or_stock",     template: "Should I buy a {theme} ETF or individual stocks?",                      intent: "etf_vs_stock" },
  { id: "risky_bets",       template: "What are the most promising but risky {theme} investments?",            intent: "risk_aware" },
];

export const THEMES: ThemeConfig[] = [
  { theme_id: "quantum",     theme_name: "Quantum Computing",       category: "tech",      mainstream_status: "peak_hype" },
  { theme_id: "nuclear_smr", theme_name: "Nuclear / SMR Energy",    category: "energy",    mainstream_status: "growing" },
  { theme_id: "peptides",    theme_name: "GLP-1 / Peptides",        category: "health",    mainstream_status: "peak_hype" },
  { theme_id: "ai_infra",    theme_name: "AI Infrastructure",       category: "tech",      mainstream_status: "peak_hype" },
  { theme_id: "robotics",    theme_name: "Robotics / Humanoid",     category: "tech",      mainstream_status: "growing" },
  { theme_id: "photonics",   theme_name: "Photonic Computing",      category: "tech",      mainstream_status: "emerging" },
  { theme_id: "space",       theme_name: "Space / Satellite",       category: "tech",      mainstream_status: "growing" },
  { theme_id: "bitcoin_mining", theme_name: "Bitcoin Mining",       category: "finance",   mainstream_status: "post_peak" },
  { theme_id: "defense_ai",  theme_name: "Defense AI / Autonomy",   category: "tech",      mainstream_status: "growing" },
  { theme_id: "longevity",   theme_name: "Longevity / Anti-Aging",  category: "health",    mainstream_status: "emerging" },
];

// -- Seed Batch Selection --------------------------------------------------
// At least 6 theme/prompt combos spanning 3+ themes

export const SEED_BATCH: Array<{ theme_id: string; prompt_id: string }> = [
  // Quantum (peak hype) - 2 prompts
  { theme_id: "quantum",     prompt_id: "best_stocks" },
  { theme_id: "quantum",     prompt_id: "pure_plays" },
  // Peptides (peak hype) - 2 prompts
  { theme_id: "peptides",    prompt_id: "best_stocks" },
  { theme_id: "peptides",    prompt_id: "how_to_invest" },
  // Nuclear SMR (growing) - 2 prompts
  { theme_id: "nuclear_smr", prompt_id: "top_5" },
  { theme_id: "nuclear_smr", prompt_id: "risky_bets" },
  // Robotics (growing) - 1 prompt
  { theme_id: "robotics",    prompt_id: "pure_plays" },
  // AI Infrastructure (peak hype) - 1 prompt
  { theme_id: "ai_infra",    prompt_id: "best_stocks" },
];

// -- Convergence Computation -----------------------------------------------

export function computeConvergence(
  records: CaptureRecord[],
  themeId: string,
): ConvergenceScore[] {
  // Collect all ticker mentions for this theme
  const tickerMap = new Map<string, {
    company: string;
    models: Set<string>;
    totalMentions: number;
    ranks: number[];
    directCount: number;
    hedgedCount: number;
  }>();

  for (const rec of records) {
    if (rec.theme_id !== themeId || rec.status !== "captured") continue;
    for (const t of rec.tickers) {
      const key = t.ticker.toUpperCase();
      if (!tickerMap.has(key)) {
        tickerMap.set(key, {
          company: t.company_name,
          models: new Set(),
          totalMentions: 0,
          ranks: [],
          directCount: 0,
          hedgedCount: 0,
        });
      }
      const entry = tickerMap.get(key)!;
      entry.models.add(rec.model_slot);
      entry.totalMentions++;
      entry.ranks.push(t.rank_in_response);
      if (t.mention_type === "direct_recommendation") entry.directCount++;
      if (t.mention_type === "hedged_mention") entry.hedgedCount++;
    }
  }

  // Compute scores
  const results: ConvergenceScore[] = [];
  for (const [ticker, data] of tickerMap) {
    const avgRank = data.ranks.reduce((a, b) => a + b, 0) / data.ranks.length;
    const modelDensity = data.models.size / 5;
    const rankScore = 1 / Math.max(avgRank, 1);
    const directRatio = data.totalMentions > 0 ? data.directCount / data.totalMentions : 0;

    const score = modelDensity * 0.5 + rankScore * 0.3 + directRatio * 0.2;

    results.push({
      ticker,
      company_name: data.company,
      theme_id: themeId,
      models_mentioning: data.models.size,
      total_mentions: data.totalMentions,
      avg_rank: Math.round(avgRank * 10) / 10,
      direct_recommendation_count: data.directCount,
      hedged_mention_count: data.hedgedCount,
      convergence_score: Math.round(score * 1000) / 1000,
      convergence_tier: score >= 0.6 ? "high" : score >= 0.3 ? "medium" : "low",
    });
  }

  return results.sort((a, b) => b.convergence_score - a.convergence_score);
}

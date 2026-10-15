-- STAGE 5.3  Prediction-market panel: external SIGNAL / validation benchmark only.
-- Objective : keep timestamped market observations with their limitations. They are NEVER treated as vote shares and are not
--             an input to the vote-share model; Stage 12/13 compare model probabilities with them.
-- Input     : ext_markets
-- Output    : {DS}.s5_market_panel
CREATE OR REPLACE TABLE `{DS}.s5_market_panel` AS
SELECT
  observation_id, observed_at, platform, market_id, market_question, outcome_label, price, bid, ask,
  volume_usd, liquidity_usd, resolution_criteria, source_url, notes,
  (bid IS NOT NULL AND ask IS NOT NULL) AS has_quote_spread,
  CASE WHEN volume_usd IS NULL AND liquidity_usd IS NULL THEN 'no_liquidity_information' ELSE 'liquidity_reported' END AS liquidity_flag,
  'validation_only_never_vote_share' AS permitted_use
FROM `{DS}.ext_markets`
ORDER BY observed_at, platform, outcome_label;

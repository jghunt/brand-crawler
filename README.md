# Activewear brand crawler (free)

Fills **product_list** for the brands that block the Google Apps Script
(brand_list › `scrape_method = crawl4ai`): DFYNE, Alphalete, FLEO, Gymshark, lululemon,
PUMA, adidas, NikeSKIMS, Under Armour, Fabletics.

Runs on GitHub Actions every night at 22:00 (Zurich), before the Apps Script (03:00),
which then rebuilds the **product_lines** from all products.

Edit `crawler/brands.yaml` to change start pages per brand.
Manual run: GitHub › Actions › brand-crawler › Run workflow (optionally one brand_id).

## shopify-v2 (26 Nov 2026)
`shopify/scrape.mjs` + `shopify/brands.json`: the v2 Shopify scraper (same as the laptop / NAS
version), run by `.github/workflows/shopify-v2.yml` on GitHub's network because Shopify
rate-limits the home connection. Output: `shopify/out/items_<brand>.tsv` in v2 collection_items
column order, committed back to the branch. It does not write to Google Sheets; the rebuild of
collections_list_v2 / product_list_v2 is done from these files.

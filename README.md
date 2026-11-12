# Activewear brand crawler (free)

Fills **product_list** for the brands that block the Google Apps Script
(brand_list › `scrape_method = crawl4ai`): DFYNE, Alphalete, FLEO, Gymshark, lululemon,
PUMA, adidas, NikeSKIMS, Under Armour, Fabletics.

Runs on GitHub Actions every night at 22:00 (Zurich), before the Apps Script (03:00),
which then rebuilds the **product_lines** from all products.

Edit `crawler/brands.yaml` to change start pages per brand.
Manual run: GitHub › Actions › brand-crawler › Run workflow (optionally one brand_id).

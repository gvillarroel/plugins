# Etsy-Aware POD Pricing

Use this reference before finalizing Printify products intended for Etsy or any marketplace with sales fees.

## Baseline Etsy Fee Model

For US Etsy Payments item-price estimates, use:

- Listing or sold-renewal fee: `USD 0.20` per sold quantity.
- Transaction fee: `6.5%` of order total. Etsy applies this to item price and to shipping/gift wrap when charged.
- Etsy Payments processing: assume US `3% + USD 0.25` per transaction unless the shop country says otherwise.
- Offsite Ads: exclude from the base case unless the shop/listing uses it. If included, add `15%` for shops under USD 10,000/year when opted in, or `12%` when mandatory/discounted for shops over the threshold. Apply only to attributed orders.

Formula for item-price-only baseline:

```text
etsy_fee = round(price * 0.065 + price * 0.03 + 20 + 25)
net_profit = price - printify_cost - etsy_fee
net_margin = net_profit / price
```

If shipping is charged separately:

```text
order_total = item_price + shipping_charged
etsy_fee = round(order_total * 0.065 + order_total * 0.03 + 20 + 25)
net_profit = item_price + shipping_charged - printify_cost - shipping_cost - etsy_fee
net_margin = net_profit / order_total
```

## Pricing Rule

Do not price from Printify gross margin alone. For Etsy-bound products:

1. Calculate Printify gross margin.
2. Calculate Etsy baseline net margin.
3. Calculate an Offsite Ads stress case when Offsite Ads may be enabled or mandatory.
4. Use the highest-cost enabled variant, usually 2XL/3XL, as the floor.
5. Prefer charm prices (`27.99`, `29.99`, `32.99`) only after the fee math passes.

Suggested guardrails:

- `>= 35%` estimated net margin after Etsy baseline fees for the highest-cost enabled variant.
- `>= 20%` estimated net margin under a 12%-15% Offsite Ads stress case, or document that Offsite Ads sales are lower-margin acquisition orders.
- If shipping is free to the buyer, include the actual shipping cost as a cost, not as hidden margin.

## Official Sources To Verify When Current Fees Matter

- Etsy Help fees article: `https://help.etsy.com/hc/en-us/articles/115014483627-What-are-the-Fees-and-Taxes-for-Selling-on-Etsy`
- Etsy Fees & Payments Policy: `https://www.etsy.com/legal/fees/`
- Etsy Offsite Ads Help: `https://help.etsy.com/hc/en-us/articles/360000338367-How-Etsy-s-Offsite-Ads-Work`

Etsy fees are temporally unstable. When publishing or repricing, verify current Etsy rates from official Etsy pages and update the product `RESOURCES.md` with the rate assumptions used.

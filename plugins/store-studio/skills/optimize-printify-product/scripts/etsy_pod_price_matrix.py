#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass


@dataclass
class PriceRow:
    size: str
    cost: float
    price: float
    recommended_price: float
    standard_etsy_fees: float
    offsite_ads_fee: float
    profit_standard: float
    profit_with_offsite_ads: float
    profit_margin_standard: float
    profit_margin_with_offsite_ads: float
    meets_standard_target: bool
    meets_standard_margin_target: bool
    meets_offsite_target: bool | None
    meets_offsite_margin_target: bool | None


def parse_money_pair(value: str) -> tuple[str, float]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Values must be SIZE=AMOUNT, e.g. XL=11.29")
    size, amount = value.split("=", 1)
    size = size.strip()
    if not size:
        raise argparse.ArgumentTypeError("Size cannot be empty")
    try:
        cost = float(amount)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid cost amount: {amount}") from exc
    if cost < 0:
        raise argparse.ArgumentTypeError("Cost cannot be negative")
    return size, cost


def parse_margin(value: str) -> float:
    raw = value.strip()
    if raw.endswith("%"):
        raw = raw[:-1].strip()
        scale = 100.0
    else:
        scale = 1.0
    try:
        margin = float(raw) / scale
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid margin: {value}") from exc
    if margin < 0:
        raise argparse.ArgumentTypeError("Margin cannot be negative")
    if margin > 1:
        margin = margin / 100.0
    if margin > 1:
        raise argparse.ArgumentTypeError("Margin must be <= 1.0 or <= 100%")
    return margin


def round_to_ending(price: float, ending: float) -> float:
    if not 0 <= ending < 1:
        raise ValueError("Price ending must be between 0 and 0.99")
    dollars = math.floor(price)
    candidate = dollars + ending
    if candidate + 1e-9 < price:
        candidate = dollars + 1 + ending
    return round(candidate, 2)


def standard_etsy_fees(
    price: float,
    listing_fee: float,
    transaction_rate: float,
    processing_rate: float,
    processing_flat: float,
) -> float:
    return listing_fee + price * transaction_rate + price * processing_rate + processing_flat


def profit(
    price: float,
    cost: float,
    listing_fee: float,
    transaction_rate: float,
    processing_rate: float,
    processing_flat: float,
    offsite_ads_rate: float = 0.0,
) -> float:
    return price - cost - standard_etsy_fees(price, listing_fee, transaction_rate, processing_rate, processing_flat) - price * offsite_ads_rate


def profit_margin(profit_value: float, price: float) -> float:
    return profit_value / price if price > 0 else 0.0


def find_price(
    cost: float,
    min_price: float,
    max_price: float,
    ending: float,
    target_standard_profit: float,
    target_standard_margin: float,
    target_offsite_profit: float | None,
    target_offsite_margin: float | None,
    listing_fee: float,
    transaction_rate: float,
    processing_rate: float,
    processing_flat: float,
    offsite_ads_rate: float,
) -> float:
    price = round_to_ending(min_price, ending)
    while price <= max_price + 1e-9:
        standard = profit(price, cost, listing_fee, transaction_rate, processing_rate, processing_flat)
        offsite = profit(price, cost, listing_fee, transaction_rate, processing_rate, processing_flat, offsite_ads_rate)
        standard_ok = standard >= target_standard_profit and profit_margin(standard, price) + 1e-9 >= target_standard_margin
        offsite_ok = (
            (target_offsite_profit is None or offsite >= target_offsite_profit)
            and (target_offsite_margin is None or profit_margin(offsite, price) + 1e-9 >= target_offsite_margin)
        )
        if standard_ok and offsite_ok:
            return price
        price = round(price + 1.0, 2)
    return round_to_ending(max_price, ending)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend Etsy-aware POD prices from Printify costs.")
    parser.add_argument("--cost", action="append", type=parse_money_pair, required=True, help="Size cost as SIZE=AMOUNT, e.g. XL=11.29")
    parser.add_argument("--price", action="append", type=parse_money_pair, default=[], help="Current or proposed size price as SIZE=AMOUNT.")
    parser.add_argument("--target-standard-profit", type=float, default=0.0)
    parser.add_argument("--target-standard-margin", type=parse_margin, default=0.55)
    parser.add_argument("--target-offsite-profit", type=float, default=None)
    parser.add_argument("--target-offsite-margin", type=parse_margin, default=None)
    parser.add_argument("--min-price", type=float, default=0.99)
    parser.add_argument("--max-price", type=float, default=49.99)
    parser.add_argument("--ending", type=float, default=0.99)
    parser.add_argument("--listing-fee", type=float, default=0.20)
    parser.add_argument("--transaction-rate", type=float, default=0.065)
    parser.add_argument("--processing-rate", type=float, default=0.03)
    parser.add_argument("--processing-flat", type=float, default=0.25)
    parser.add_argument("--offsite-ads-rate", type=float, default=0.15)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a Markdown table.")
    args = parser.parse_args()

    current_prices = dict(args.price)
    rows: list[PriceRow] = []
    for size, cost in args.cost:
        recommended = find_price(
            cost=cost,
            min_price=args.min_price,
            max_price=args.max_price,
            ending=args.ending,
            target_standard_profit=args.target_standard_profit,
            target_standard_margin=args.target_standard_margin,
            target_offsite_profit=args.target_offsite_profit,
            target_offsite_margin=args.target_offsite_margin,
            listing_fee=args.listing_fee,
            transaction_rate=args.transaction_rate,
            processing_rate=args.processing_rate,
            processing_flat=args.processing_flat,
            offsite_ads_rate=args.offsite_ads_rate,
        )
        evaluated_price = current_prices.get(size, recommended)
        standard_fees = standard_etsy_fees(
            evaluated_price,
            args.listing_fee,
            args.transaction_rate,
            args.processing_rate,
            args.processing_flat,
        )
        offsite_fee = evaluated_price * args.offsite_ads_rate
        profit_standard = evaluated_price - cost - standard_fees
        profit_with_offsite = profit_standard - offsite_fee
        margin_standard = profit_margin(profit_standard, evaluated_price)
        margin_with_offsite = profit_margin(profit_with_offsite, evaluated_price)
        rows.append(
            PriceRow(
                size=size,
                cost=round(cost, 2),
                price=round(evaluated_price, 2),
                recommended_price=round(recommended, 2),
                standard_etsy_fees=round(standard_fees, 2),
                offsite_ads_fee=round(offsite_fee, 2),
                profit_standard=round(profit_standard, 2),
                profit_with_offsite_ads=round(profit_with_offsite, 2),
                profit_margin_standard=round(margin_standard, 4),
                profit_margin_with_offsite_ads=round(margin_with_offsite, 4),
                meets_standard_target=profit_standard + 1e-9 >= args.target_standard_profit,
                meets_standard_margin_target=margin_standard + 1e-9 >= args.target_standard_margin,
                meets_offsite_target=None if args.target_offsite_profit is None else profit_with_offsite + 1e-9 >= args.target_offsite_profit,
                meets_offsite_margin_target=None if args.target_offsite_margin is None else margin_with_offsite + 1e-9 >= args.target_offsite_margin,
            )
        )

    output = {
        "fee_model": {
            "listing_fee": args.listing_fee,
            "transaction_rate": args.transaction_rate,
            "processing_rate": args.processing_rate,
            "processing_flat": args.processing_flat,
            "offsite_ads_rate": args.offsite_ads_rate,
            "excluded": [
                "shipping subsidy",
                "tax",
                "VAT",
                "currency conversion",
                "Etsy Ads",
                "discounts",
                "returns",
                "samples",
            ],
        },
        "targets": {
            "standard_profit": args.target_standard_profit,
            "standard_profit_margin": args.target_standard_margin,
            "offsite_profit": args.target_offsite_profit,
            "offsite_profit_margin": args.target_offsite_margin,
        },
        "rows": [asdict(row) for row in rows],
    }

    if args.json:
        print(json.dumps(output, indent=2))
        return

    print("| Size | Cost | Price | Recommended | Etsy fees | Offsite fee | Profit std | Std margin | Profit w/ offsite | Offsite margin | Status |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in rows:
        standard_status = "std ok" if row.meets_standard_target and row.meets_standard_margin_target else "std low"
        if row.meets_offsite_target is None and row.meets_offsite_margin_target is None:
            offsite_status = "offsite n/a"
        else:
            offsite_profit_ok = True if row.meets_offsite_target is None else row.meets_offsite_target
            offsite_margin_ok = True if row.meets_offsite_margin_target is None else row.meets_offsite_margin_target
            offsite_status = "offsite ok" if offsite_profit_ok and offsite_margin_ok else "offsite low"
        print(
            f"| {row.size} | ${row.cost:.2f} | ${row.price:.2f} | ${row.recommended_price:.2f} | "
            f"${row.standard_etsy_fees:.2f} | ${row.offsite_ads_fee:.2f} | "
            f"${row.profit_standard:.2f} | {row.profit_margin_standard:.2%} | "
            f"${row.profit_with_offsite_ads:.2f} | {row.profit_margin_with_offsite_ads:.2%} | "
            f"{standard_status}, {offsite_status} |"
        )


if __name__ == "__main__":
    main()

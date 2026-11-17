#!/usr/bin/env python3
"""Calculate POD margins with Printify costs and Etsy-style marketplace fees."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FeeModel:
    transaction_fee_pct: float
    payment_processing_pct: float
    listing_fee_cents: int
    payment_fixed_fee_cents: int
    offsite_ads_pct: float


def parse_cents_list(value: str) -> list[int]:
    parts = [part.strip() for part in value.replace(";", ",").split(",")]
    costs = [int(part) for part in parts if part]
    if not costs:
        raise argparse.ArgumentTypeError("Provide at least one cent value.")
    if any(cost < 0 for cost in costs):
        raise argparse.ArgumentTypeError("Cent values must be non-negative.")
    return costs


def money(cents: int) -> str:
    return f"{cents / 100:.2f}"


def marketplace_fee(order_total_cents: int, model: FeeModel) -> int:
    percentage = (model.transaction_fee_pct + model.payment_processing_pct + model.offsite_ads_pct) / 100
    return int(
        round(
            order_total_cents * percentage
            + model.listing_fee_cents
            + model.payment_fixed_fee_cents
        )
    )


def margin_row(
    *,
    price_cents: int,
    printify_cost_cents: int,
    shipping_charge_cents: int,
    shipping_cost_cents: int,
    model: FeeModel,
) -> dict[str, int | float | str]:
    order_total_cents = price_cents + shipping_charge_cents
    fee_cents = marketplace_fee(order_total_cents, model)
    gross_profit_cents = price_cents - printify_cost_cents
    net_profit_cents = order_total_cents - printify_cost_cents - shipping_cost_cents - fee_cents
    gross_margin_pct = round((gross_profit_cents / price_cents) * 100, 1) if price_cents else 0.0
    net_margin_pct = round((net_profit_cents / order_total_cents) * 100, 1) if order_total_cents else 0.0
    return {
        "price_cents": price_cents,
        "price_usd": money(price_cents),
        "printify_cost_cents": printify_cost_cents,
        "printify_cost_usd": money(printify_cost_cents),
        "shipping_charge_cents": shipping_charge_cents,
        "shipping_cost_cents": shipping_cost_cents,
        "order_total_cents": order_total_cents,
        "marketplace_fee_cents": fee_cents,
        "gross_profit_cents": gross_profit_cents,
        "gross_margin_pct": gross_margin_pct,
        "net_profit_cents": net_profit_cents,
        "net_margin_pct": net_margin_pct,
    }


def min_price_for_target(
    *,
    max_cost_cents: int,
    shipping_charge_cents: int,
    shipping_cost_cents: int,
    model: FeeModel,
    target_net_margin_pct: float,
    start_cents: int,
    max_price_cents: int,
) -> int | None:
    target = target_net_margin_pct / 100
    for price_cents in range(max(start_cents, 1), max_price_cents + 1):
        row = margin_row(
            price_cents=price_cents,
            printify_cost_cents=max_cost_cents,
            shipping_charge_cents=shipping_charge_cents,
            shipping_cost_cents=shipping_cost_cents,
            model=model,
        )
        if float(row["net_margin_pct"]) / 100 >= target:
            return price_cents
    return None


def charm_price_at_or_above(cents: int) -> int:
    dollars = max(1, math.floor(cents / 100))
    candidates = []
    for dollar in range(dollars, dollars + 20):
        for suffix in (99, 49, 00):
            candidate = dollar * 100 + suffix
            if candidate >= cents:
                candidates.append(candidate)
    return min(candidates)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-cents", type=int, required=True, help="Retail item price in cents.")
    parser.add_argument(
        "--cost-cents",
        type=parse_cents_list,
        required=True,
        help="Comma-separated Printify product costs in cents, e.g. 1129,1382,1612.",
    )
    parser.add_argument("--shipping-charge-cents", type=int, default=0, help="Shipping charged to buyer.")
    parser.add_argument("--shipping-cost-cents", type=int, default=0, help="Actual shipping cost if absorbed.")
    parser.add_argument("--transaction-fee-pct", type=float, default=6.5, help="Etsy transaction fee percent.")
    parser.add_argument("--payment-processing-pct", type=float, default=3.0, help="Payment processing percent.")
    parser.add_argument("--listing-fee-cents", type=int, default=20, help="Listing or renewal fee per sale.")
    parser.add_argument("--payment-fixed-fee-cents", type=int, default=25, help="Fixed payment fee per sale.")
    parser.add_argument("--offsite-ads-pct", type=float, default=0.0, help="Optional Offsite Ads stress percent.")
    parser.add_argument("--target-net-margin-pct", type=float, default=35.0)
    parser.add_argument("--max-search-price-cents", type=int, default=9999)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    model = FeeModel(
        transaction_fee_pct=args.transaction_fee_pct,
        payment_processing_pct=args.payment_processing_pct,
        listing_fee_cents=args.listing_fee_cents,
        payment_fixed_fee_cents=args.payment_fixed_fee_cents,
        offsite_ads_pct=args.offsite_ads_pct,
    )
    rows = [
        margin_row(
            price_cents=args.price_cents,
            printify_cost_cents=cost,
            shipping_charge_cents=args.shipping_charge_cents,
            shipping_cost_cents=args.shipping_cost_cents,
            model=model,
        )
        for cost in args.cost_cents
    ]
    net_margins = [float(row["net_margin_pct"]) for row in rows]
    gross_margins = [float(row["gross_margin_pct"]) for row in rows]
    min_required = min_price_for_target(
        max_cost_cents=max(args.cost_cents),
        shipping_charge_cents=args.shipping_charge_cents,
        shipping_cost_cents=args.shipping_cost_cents,
        model=model,
        target_net_margin_pct=args.target_net_margin_pct,
        start_cents=max(args.cost_cents),
        max_price_cents=args.max_search_price_cents,
    )
    output = {
        "assumptions": {
            "transaction_fee_pct": args.transaction_fee_pct,
            "payment_processing_pct": args.payment_processing_pct,
            "listing_fee_cents": args.listing_fee_cents,
            "payment_fixed_fee_cents": args.payment_fixed_fee_cents,
            "offsite_ads_pct": args.offsite_ads_pct,
            "shipping_charge_cents": args.shipping_charge_cents,
            "shipping_cost_cents": args.shipping_cost_cents,
            "fee_scope": "Etsy-style fee estimate; verify current official rates before publishing.",
        },
        "price": {"cents": args.price_cents, "usd": money(args.price_cents)},
        "gross_margin_range_pct": [min(gross_margins), max(gross_margins)],
        "net_margin_range_pct": [min(net_margins), max(net_margins)],
        "worst_case_cost_cents": max(args.cost_cents),
        "target_net_margin_pct": args.target_net_margin_pct,
        "minimum_price_for_target": None
        if min_required is None
        else {
            "cents": min_required,
            "usd": money(min_required),
            "charm_price_cents": charm_price_at_or_above(min_required),
            "charm_price_usd": money(charm_price_at_or_above(min_required)),
        },
        "variants": rows,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

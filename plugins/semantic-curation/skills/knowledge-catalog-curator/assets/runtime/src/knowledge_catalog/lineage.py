"""Reproducible synthetic retail lineage and local, human-reviewed revisions.

This is a small illustrative model inspired by PROV activities/entities and
OpenLineage datasets/jobs/runs, not an implementation of either exchange format.
Recipes below execute locally; simulation timestamps are explicitly not measured
execution times. Nothing in this module connects to or publishes into a cloud.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import math
import random
import re
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath

MAX_GRAPH_BYTES = 1_000_000
MAX_DATASETS = 100
MAX_PROCESSES = 100
MAX_EDGES = 1_000
_ID = re.compile(r"[a-z][a-z0-9-]{0,99}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_TYPES = {"string", "integer", "number", "boolean", "date", "datetime"}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _text(value, maximum=10_000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _seed(seed):
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer between 0 and 4294967295")
    return seed


def _csv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _tables(seed):
    """The only executable recipes: all keys come from this one seeded world."""
    rng = random.Random(seed)
    customers = [
        {"customer_id": f"C{i:03}", "region": ("North", "South", "West", "East")[(i - 1) % 4]}
        for i in range(1, 9)
    ]
    products = [
        {"product_id": f"P{i:03}", "category": category, "unit_price_cents": price}
        for i, (category, price) in enumerate(
            (("Books", 1250), ("Home", 2499), ("Food", 599), ("Sports", 4500)), 1
        )
    ]
    orders, items = [], []
    for i in range(1, 25):
        order = {
            "order_id": f"O{i:04}",
            "customer_id": rng.choice(customers)["customer_id"],
            "order_date": (date(2025, 1, 1) + timedelta(days=rng.randrange(14))).isoformat(),
            "status": "CANCELLED" if i % 7 == 0 else "PAID",
        }
        orders.append(order)
        for line in range(1, rng.randint(1, 3) + 1):
            items.append(
                {
                    "order_id": order["order_id"],
                    "line_id": line,
                    "product_id": rng.choice(products)["product_id"],
                    "quantity": rng.randint(1, 5),
                }
            )
    clean = [dict(row) for row in orders if row["status"] == "PAID"]
    clean_index = {row["order_id"]: row for row in clean}
    customer_index = {row["customer_id"]: row for row in customers}
    product_index = {row["product_id"]: row for row in products}
    sales = []
    for item in items:
        if item["order_id"] not in clean_index:
            continue
        order, product = clean_index[item["order_id"]], product_index[item["product_id"]]
        sales.append(
            {
                "order_id": item["order_id"],
                "line_id": item["line_id"],
                "customer_id": order["customer_id"],
                "order_date": order["order_date"],
                "region": customer_index[order["customer_id"]]["region"],
                "product_id": item["product_id"],
                "category": product["category"],
                "quantity": item["quantity"],
                "amount_cents": item["quantity"] * product["unit_price_cents"],
            }
        )
    daily, customer_totals = defaultdict(lambda: [0, 0]), defaultdict(lambda: [set(), 0])
    for row in sales:
        daily[(row["order_date"], row["category"])][0] += row["quantity"]
        daily[(row["order_date"], row["category"])][1] += row["amount_cents"]
        customer_totals[row["customer_id"]][0].add(row["order_id"])
        customer_totals[row["customer_id"]][1] += row["amount_cents"]
    return {
        "raw-customers": customers,
        "raw-products": products,
        "raw-orders": orders,
        "raw-order-items": items,
        "clean-orders": clean,
        "enriched-sales": sales,
        "daily-sales": [
            {"order_date": key[0], "category": key[1], "units": value[0], "amount_cents": value[1]}
            for key, value in sorted(daily.items())
        ],
        "customer-summary": [
            {"customer_id": key, "order_count": len(value[0]), "amount_cents": value[1]}
            for key, value in sorted(customer_totals.items())
        ],
    }


_DESCRIPTIONS = {
    "raw-customers": "Eight fictional customers with regions, generated in the same domain; no real names or contact details.",
    "raw-products": "Four fictional products. Prices use USD cents, excluding taxes and discounts in this simulation.",
    "raw-orders": "Twenty-four synthetic orders in the shared domain, including cancelled orders to demonstrate filtering.",
    "raw-order-items": "Order lines from the same generator; order_id and product_id reference this demo's source datasets.",
    "clean-orders": "PAID orders; exactly the CANCELLED orders are excluded without cleaning or altering their keys.",
    "enriched-sales": "Paid order lines enriched with customers and products from the same domain; amount_cents = quantity × unit_price_cents.",
    "daily-sales": "SUM of quantity and amount_cents grouped by date and category, retaining USD cents.",
    "customer-summary": "COUNT DISTINCT order_id and SUM amount_cents per customer; cancelled orders contribute no amounts.",
}
_COLUMN_DESCRIPTIONS = {
    "customer_id": "Fictional customer identifier; links only entities in this simulation.",
    "region": "Fictional categorical region; not a real person's location.",
    "product_id": "Product identifier created by this generator.",
    "category": "Product category from the demo's limited vocabulary.",
    "unit_price_cents": "Integer unit price in USD cents; no taxes or discounts are simulated.",
    "order_id": "Fictional order identifier shared by this demo's source datasets.",
    "order_date": "Simulated business date in January 2025; does not represent real activity.",
    "status": "Synthetic PAID or CANCELLED status; only PAID orders enter the outputs.",
    "line_id": "Line position within the order; its complete key is order_id + line_id.",
    "quantity": "Integer number of product units in an order line.",
    "amount_cents": "Integer amount in USD cents, derived or aggregated by the process; not real billing.",
    "units": "SUM of units from paid order lines in the group.",
    "order_count": "COUNT DISTINCT paid orders per customer, avoiding counting order lines as orders.",
}
_RECIPES = [
    (
        "filter-paid",
        "Filter paid orders",
        ["raw-orders"],
        ["clean-orders"],
        "SELECT * FROM raw_orders WHERE status = 'PAID'",
    ),
    (
        "enrich-lines",
        "Enrich paid order lines",
        ["clean-orders", "raw-order-items", "raw-products", "raw-customers"],
        ["enriched-sales"],
        "INNER JOIN order_items.order_id = clean_orders.order_id; JOIN products.product_id; JOIN customers.customer_id; amount_cents = quantity * unit_price_cents",
    ),
    (
        "aggregate-daily",
        "Summarize by date and category",
        ["enriched-sales"],
        ["daily-sales"],
        "GROUP BY order_date, category; SUM(quantity) AS units; SUM(amount_cents) AS amount_cents",
    ),
    (
        "aggregate-customers",
        "Summarize by customer",
        ["enriched-sales"],
        ["customer-summary"],
        "GROUP BY customer_id; COUNT(DISTINCT order_id) AS order_count; SUM(amount_cents) AS amount_cents",
    ),
]


def generate_demo(output_dir: Path, seed=42) -> dict:
    """Execute deterministic recipes and save original synthetic CSV evidence.

    The graph deliberately omits one observed dependency and adds one clearly
    asserted, unsupported hypothesis. Files and transformation facts stay correct;
    reviewers can repair the descriptive graph without modifying observations.
    Existing output directories with content are never overwritten.
    """
    seed = _seed(seed)
    directory = Path(output_dir).expanduser().resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError("Demo output must be a new or empty directory; existing evidence is preserved")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "files").mkdir()
    tables = _tables(seed)
    datasets = []
    for dataset_id, rows in tables.items():
        names = list(rows[0])
        data = _csv_bytes(rows, names)
        relative = f"files/{dataset_id}.csv"
        (directory / relative).write_bytes(data)
        columns = [
            {
                "name": name,
                "data_type": "integer"
                if isinstance(rows[0][name], int)
                else "date"
                if name == "order_date"
                else "string",
                "description": _COLUMN_DESCRIPTIONS[name],
            }
            for name in names
        ]
        datasets.append(
            {
                "id": dataset_id,
                "name": dataset_id.replace("-", " ").title(),
                "layer": "source"
                if dataset_id.startswith("raw-")
                else "curated"
                if dataset_id in {"clean-orders", "enriched-sales"}
                else "mart",
                "description": _DESCRIPTIONS[dataset_id],
                "synthetic": True,
                "namespace": f"synthetic-retail/seed-{seed}",
                "uri": f"synthetic://retail/seed-{seed}/{dataset_id}",
                "path": relative,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "row_count": len(rows),
                "columns": columns,
            }
        )
    by_id = {dataset["id"]: dataset for dataset in datasets}
    processes, runs, observed = [], [], []
    for number, (process_id, name, inputs, outputs, specification) in enumerate(_RECIPES):
        run_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"synthetic-retail/{seed}/{process_id}/v1"))
        process = {
            "id": process_id,
            "name": name,
            "description": specification,
            "inputs": inputs,
            "outputs": outputs,
            "transformation": specification,
            "specification_sha256": hashlib.sha256(specification.encode()).hexdigest(),
        }
        processes.append(process)
        started = datetime(2025, 2, 1, 9, number * 5)
        runs.append(
            {
                "id": run_id,
                "process_id": process_id,
                "status": "COMPLETED",
                "execution": "executed_locally",
                "clock_kind": "simulated",
                "started_at": started.isoformat() + "Z",
                "ended_at": (started + timedelta(seconds=30)).isoformat() + "Z",
                "input_rows": {key: len(tables[key]) for key in inputs},
                "output_rows": {key: len(tables[key]) for key in outputs},
            }
        )
        for input_id in inputs:
            for output_id in outputs:
                observed.append(
                    {
                        "id": f"edge-{process_id}-{input_id}",
                        "source": input_id,
                        "target": output_id,
                        "process_id": process_id,
                        "description": f"Executed dependency: {input_id} → {output_id} through {process_id}.",
                        "confidence": 1.0,
                        "evidence": {
                            "kind": "observed",
                            "origin": "synthetic_generator",
                            "run_id": run_id,
                            "source_sha256": by_id[input_id]["sha256"],
                            "target_sha256": by_id[output_id]["sha256"],
                            "specification_sha256": process["specification_sha256"],
                        },
                    }
                )
    column_lineage = []

    def link(source_id, source_column, target_id, target_column, process_id, transformation):
        column_lineage.append(
            {
                "source_dataset": source_id,
                "source_column": source_column,
                "target_dataset": target_id,
                "target_column": target_column,
                "process_id": process_id,
                "transformation": transformation,
                "evidence_kind": "observed",
                "origin": "synthetic_generator",
            }
        )

    for name in tables["clean-orders"][0]:
        link("raw-orders", name, "clean-orders", name, "filter-paid", "Identity after status = PAID filter")
    sale_sources = {
        "order_id": ("clean-orders", "order_id"),
        "line_id": ("raw-order-items", "line_id"),
        "customer_id": ("clean-orders", "customer_id"),
        "order_date": ("clean-orders", "order_date"),
        "region": ("raw-customers", "region"),
        "product_id": ("raw-order-items", "product_id"),
        "category": ("raw-products", "category"),
        "quantity": ("raw-order-items", "quantity"),
        "amount_cents": ("raw-order-items", "quantity"),
    }
    for target, (origin, field) in sale_sources.items():
        link(
            origin,
            field,
            "enriched-sales",
            target,
            "enrich-lines",
            "quantity * unit_price_cents"
            if target == "amount_cents"
            else "Identity through documented joins",
        )
    link(
        "raw-products",
        "unit_price_cents",
        "enriched-sales",
        "amount_cents",
        "enrich-lines",
        "quantity * unit_price_cents",
    )
    for target, field in (
        ("order_date", "order_date"),
        ("category", "category"),
        ("units", "quantity"),
        ("amount_cents", "amount_cents"),
    ):
        link(
            "enriched-sales",
            field,
            "daily-sales",
            target,
            "aggregate-daily",
            "GROUP BY" if target in {"order_date", "category"} else f"SUM({field})",
        )
    for target, field in (
        ("customer_id", "customer_id"),
        ("order_count", "order_id"),
        ("amount_cents", "amount_cents"),
    ):
        link(
            "enriched-sales",
            field,
            "customer-summary",
            target,
            "aggregate-customers",
            "GROUP BY"
            if target == "customer_id"
            else "COUNT DISTINCT(order_id)"
            if target == "order_count"
            else "SUM(amount_cents)",
        )
    missing = next(
        edge for edge in observed if edge["source"] == "clean-orders" and edge["target"] == "enriched-sales"
    )
    edges = [copy.deepcopy(edge) for edge in observed if edge["id"] != missing["id"]]
    edges.append(
        {
            "id": "edge-speculative",
            "source": "raw-products",
            "target": "daily-sales",
            "process_id": "aggregate-daily",
            "description": "Incorrect teaching hypothesis: a product catalog does not directly enter this aggregation.",
            "confidence": 0.35,
            "evidence": {
                "kind": "asserted",
                "note": "Intentional anomaly for review; this dependency was not observed.",
            },
        }
    )
    graph = {
        "version": 1,
        "id": f"retail-seed-{seed}",
        "title": "Synthetic retail sales lineage",
        "description": "Self-contained, reproducible domain; all joins executed between sources from the same generator. It does not use or link independent Kaggle datasets.",
        "synthetic": True,
        "seed": seed,
        "generated_at": "2025-02-01T09:00:00Z",
        "clock_kind": "simulated",
        "datasets": datasets,
        "processes": processes,
        "edges": edges,
        "column_lineage": column_lineage,
        "runs": runs,
        "observed_dependencies": observed,
        "correction_hints": [
            {
                "code": "MISSING_DEPENDENCY",
                "action": "add_documented_edge",
                "edge_id": missing["id"],
                "message": "Add the clean-orders → enriched-sales dependency recorded in observed_dependencies.",
            },
            {
                "code": "UNSUPPORTED_DEPENDENCY",
                "action": "remove_edge",
                "edge_id": "edge-speculative",
                "message": "Remove the unsupported edge-speculative hypothesis; it is not a process input.",
            },
        ],
        "notes": "Times use a fixed simulated clock for reproducibility; COMPLETED describes locally executed recipes, not GCP jobs. confidence is an evidence annotation, not a calibrated probability.",
        "references": ["https://www.w3.org/TR/prov-o/", "https://openlineage.io/docs/spec/object-model/"],
    }
    (directory / "manifest.json").write_text(_json(graph) + "\n", encoding="utf-8")
    return graph


def _validate_lineage(graph) -> dict:
    """Validate graph structure and evidence consistency without trusting claims.

    This does not read a network or execute transformation text. The store adds
    local file verification before approval; standalone results are structural.
    """
    findings = []

    def add(code, message, severity="error", **details):
        findings.append({"code": code, "severity": severity, "message": message, **details})

    def result():
        findings[:] = sorted(
            {_json(item): item for item in findings}.values(),
            key=lambda item: (item["severity"], item["code"], _json(item)),
        )
        errors = sum(item["severity"] == "error" for item in findings)
        warnings = sum(item["severity"] == "warning" for item in findings)
        return {
            "score": max(0, 100 - errors * 12 - warnings * 3),
            "conforms": errors == 0,
            "findings": findings,
            "scope": "structural and declared-evidence consistency; file verification is separate",
        }

    if not isinstance(graph, dict):
        add("INVALID_GRAPH", "Lineage must be a JSON object.")
        return result()
    try:
        if len(_json(graph).encode()) > MAX_GRAPH_BYTES:
            add("GRAPH_LIMIT", "The graph exceeds the 1 MB limit.")
            return result()
    except (ValueError, TypeError, RecursionError):
        add("INVALID_JSON", "The graph must contain finite, bounded JSON.")
        return result()
    if graph.get("version") != 1 or graph.get("synthetic") is not True:
        add("UNSUPPORTED_GRAPH", "This demo requires version=1 and synthetic=true.")
    if not _text(graph.get("title"), 200) or not _text(graph.get("description")):
        add("MISSING_DESCRIPTION", "Add a domain title and description.")
    collections = {}
    for key, limit in (
        ("datasets", MAX_DATASETS),
        ("processes", MAX_PROCESSES),
        ("edges", MAX_EDGES),
        ("runs", 500),
        ("column_lineage", 5000),
        ("observed_dependencies", MAX_EDGES),
    ):
        values = graph.get(key)
        if (
            not isinstance(values, list)
            or len(values) > limit
            or any(not isinstance(item, dict) for item in values)
        ):
            add(
                "INVALID_COLLECTION",
                f"{key} must be a list of objects within the {limit} item limit.",
                collection=key,
            )
            return result()
        collections[key] = values
    indexed = {}
    for kind in ("datasets", "processes", "edges", "runs"):
        values = collections[kind]
        identifiers = [item.get("id") for item in values]
        if any(not _text(value, 200) for value in identifiers) or len(set(map(str, identifiers))) != len(
            identifiers
        ):
            add("DUPLICATE_OR_INVALID_ID", f"{kind} IDs must be nonempty and unique.", collection=kind)
            return result()
        indexed[kind] = {item["id"]: item for item in values}
    datasets, processes, edges, runs = (indexed[key] for key in ("datasets", "processes", "edges", "runs"))
    if not datasets or not processes:
        add("EMPTY_GRAPH", "Include datasets and processes to describe the flow.")
    columns = {}
    for dataset_id, dataset in datasets.items():
        if dataset.get("synthetic") is not True or not _text(dataset.get("description")):
            add(
                "DATASET_DESCRIPTION",
                "Each dataset must declare its synthetic nature and description.",
                target_id=dataset_id,
            )
        schema = dataset.get("columns")
        if (
            not isinstance(schema, list)
            or len(schema) > 250
            or any(not isinstance(item, dict) for item in schema)
        ):
            add(
                "INVALID_SCHEMA",
                "Columns must be a list of up to 250 objects.",
                target_id=dataset_id,
            )
            columns[dataset_id] = set()
        else:
            names = [item.get("name") for item in schema]
            if any(not _text(name, 200) for name in names) or len(set(map(str, names))) != len(names):
                add("INVALID_SCHEMA", "Column names must be unique and nonempty.", target_id=dataset_id)
                columns[dataset_id] = set()
            else:
                columns[dataset_id] = set(names)
            for column in schema:
                if column.get("data_type") not in _TYPES or not _text(column.get("description")):
                    add(
                        "COLUMN_DESCRIPTION",
                        "Each column needs a known type and description.",
                        target_id=dataset_id,
                    )
        path = dataset.get("path")
        if (
            not isinstance(path, str)
            or not path
            or "\\" in path
            or PurePosixPath(path).is_absolute()
            or ".." in PurePosixPath(path).parts
            or ":" in path
        ):
            add(
                "UNSAFE_ARTIFACT_PATH",
                "Evidence paths must be relative to the demo directory.",
                target_id=dataset_id,
            )
        if not isinstance(dataset.get("sha256"), str) or not _SHA.fullmatch(dataset["sha256"]):
            add(
                "MISSING_FINGERPRINT",
                "Each dataset needs the SHA-256 fingerprint of its original CSV.",
                target_id=dataset_id,
            )
    expected = set()
    for process_id, process in processes.items():
        if not _text(process.get("description")) or not _text(process.get("transformation")):
            add("PROCESS_DESCRIPTION", "Describe the process and its transformation.", target_id=process_id)
        for direction in ("inputs", "outputs"):
            values = process.get(direction)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or value not in datasets for value in values)
                or len(set(map(str, values))) != len(values)
            ):
                add(
                    "PROCESS_REFERENCE",
                    f"{direction} must name existing, unique datasets.",
                    target_id=process_id,
                )
                break
        else:
            expected.update(
                (source, target, process_id) for source in process["inputs"] for target in process["outputs"]
            )
    actual, adjacency = set(), defaultdict(set)
    observed = {
        (edge.get("source"), edge.get("target"), edge.get("process_id")): edge
        for edge in collections["observed_dependencies"]
        if all(isinstance(edge.get(key), str) for key in ("source", "target", "process_id"))
    }
    for edge_id, edge in edges.items():
        key = tuple(edge.get(field) for field in ("source", "target", "process_id"))
        if any(not isinstance(value, str) for value in key):
            add(
                "EDGE_REFERENCE",
                "The relationship must name source, target and process_id.",
                target_id=edge_id,
            )
            continue
        if key in actual:
            add("DUPLICATE_DEPENDENCY", "The same dependency appears more than once.", target_id=edge_id)
        actual.add(key)
        if key not in expected:
            add(
                "UNSUPPORTED_DEPENDENCY",
                "The relationship does not match the process's declared inputs and outputs; correct or remove it.",
                target_id=edge_id,
                suggestion="remove_or_correct_edge",
            )
        if key[0] in datasets and key[1] in datasets:
            adjacency[key[0]].add(key[1])
        if not _text(edge.get("description")):
            add(
                "EDGE_DESCRIPTION",
                "Describe the relationship so another reviewer can understand it.",
                target_id=edge_id,
            )
        confidence = edge.get("confidence")
        if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            add(
                "INVALID_CONFIDENCE",
                "confidence must be finite and between zero and one; it is not a calibrated probability.",
                target_id=edge_id,
            )
        evidence = edge.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("kind") not in {"observed", "asserted"}:
            add(
                "MISSING_EDGE_EVIDENCE",
                "Distinguish observed evidence from a reviewer assertion.",
                target_id=edge_id,
            )
        elif evidence["kind"] == "observed":
            if key not in observed or evidence != observed[key].get("evidence"):
                add(
                    "UNVERIFIED_OBSERVATION",
                    "The relationship does not match the original executed evidence.",
                    target_id=edge_id,
                )
            elif evidence.get("run_id") not in runs or runs[evidence["run_id"]].get("process_id") != key[2]:
                add(
                    "RUN_REFERENCE",
                    "Evidence must link to a run of the same process.",
                    target_id=edge_id,
                )
        elif not _text(evidence.get("note")):
            add(
                "ASSERTION_NOTE_REQUIRED",
                "Document the rationale and uncertainties behind the human assertion.",
                target_id=edge_id,
            )
        else:
            add(
                "ASSERTED_DEPENDENCY",
                "This relationship is a reviewer assertion, not an automatic observation.",
                "warning",
                target_id=edge_id,
            )
    for source, target, process_id in sorted(expected - actual):
        add(
            "MISSING_DEPENDENCY",
            f"The documented {source} → {target} dependency of process {process_id} is missing.",
            source=source,
            target=target,
            process_id=process_id,
            suggestion="add_documented_edge",
        )
    indegree = {key: 0 for key in datasets}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1
    queue = deque(key for key, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for target in adjacency[node]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(datasets):
        add("LINEAGE_CYCLE", "The flow contains a cycle; review the relationships to restore a DAG.")
    coverage = set()
    for item in collections["column_lineage"]:
        source_id, target_id, process_id = (
            item.get(key) for key in ("source_dataset", "target_dataset", "process_id")
        )
        if not all(isinstance(value, str) for value in (source_id, target_id, process_id)):
            add("COLUMN_REFERENCE", "Column lineage requires valid dataset and process references.")
            continue
        source_column, target_column = item.get("source_column"), item.get("target_column")
        if (
            not isinstance(source_column, str)
            or not isinstance(target_column, str)
            or source_column not in columns.get(source_id, set())
            or target_column not in columns.get(target_id, set())
            or (source_id, target_id, process_id) not in expected
        ):
            add("COLUMN_REFERENCE", "The column or transformation path does not exist.", target_id=target_id)
        else:
            coverage.add((target_id, target_column))
        if not _text(item.get("transformation"), 2000):
            add(
                "COLUMN_TRANSFORMATION",
                "Explain the transformation of each derived column.",
                target_id=target_id,
            )
    for _, target_id, _ in expected:
        for column in columns.get(target_id, set()):
            if (target_id, column) not in coverage:
                add(
                    "COLUMN_LINEAGE_GAP",
                    "A derived column lacks a description of its provenance.",
                    target_id=target_id,
                    column=column,
                )
    for process_id in processes:
        if not any(run.get("process_id") == process_id for run in runs.values()):
            add("MISSING_RUN", "The process has no recorded run.", target_id=process_id)
    for run_id, run in runs.items():
        if (
            run.get("process_id") not in processes
            or run.get("status") != "COMPLETED"
            or run.get("execution") != "executed_locally"
            or run.get("clock_kind") != "simulated"
        ):
            add(
                "INVALID_RUN",
                "The demo distinguishes completed local execution from the simulated clock.",
                target_id=run_id,
            )
        try:
            start = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(run["ended_at"].replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None or end < start:
                raise ValueError("Invalid simulation interval")
        except (KeyError, TypeError, ValueError, AttributeError):
            add(
                "INVALID_RUN_TIME",
                "The run requires ordered ISO start and end times with explicit time zones; the clock is simulated.",
                target_id=run_id,
            )
    return result()


def validate_lineage(graph) -> dict:
    """Fail closed for malformed JSON shapes; never execute transformation text."""
    try:
        return _validate_lineage(graph)
    except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
        return {
            "score": 0,
            "conforms": False,
            "findings": [
                {
                    "code": "INVALID_GRAPH_SHAPE",
                    "severity": "error",
                    "message": "The graph contains malformed references or values; correct its JSON structure.",
                }
            ],
            "scope": "structural and declared-evidence consistency; file verification is separate",
        }


class LineageStore:
    """Local lineage revisions, immutable execution facts and explicit human decisions."""

    def __init__(self, home: Path):
        self.home = Path(home).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.db = self.home / "lineage.sqlite3"
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS lineage (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            con.execute(
                "CREATE TABLE IF NOT EXISTS lineage_revisions (id TEXT,revision INTEGER,body TEXT NOT NULL,PRIMARY KEY(id,revision))"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS lineage_events (sequence INTEGER PRIMARY KEY,at REAL,id TEXT,action TEXT,detail TEXT)"
            )
            if "revision" not in {row[1] for row in con.execute("PRAGMA table_info(lineage_events)")}:
                con.execute("ALTER TABLE lineage_events ADD COLUMN revision INTEGER")

    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.db, timeout=30)
        try:
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def _digest(record):
        return _hash(
            {key: record[key] for key in ("id", "graph", "revision", "quality", "observed_evidence")}
        )

    def _get(self, con, graph_id):
        if not isinstance(graph_id, str) or not _ID.fullmatch(graph_id):
            raise ValueError("Invalid lineage ID")
        row = con.execute("SELECT body FROM lineage WHERE id=?", (graph_id,)).fetchone()
        if row is None:
            raise ValueError("Lineage not found")
        return json.loads(row[0])

    def _check(self, record, expected_digest):
        if not isinstance(expected_digest, str) or not _SHA.fullmatch(expected_digest):
            raise ValueError("expected_digest must be the SHA-256 of the reviewed revision")
        if record.get("digest") != expected_digest:
            raise ValueError("Lineage changed; reload the current revision before editing or deciding")
        if self._digest(record) != record["digest"]:
            raise ValueError("Lineage integrity failed; do not approve modified local records")

    def _save(self, con, record, action, detail=""):
        prior = con.execute(
            "SELECT body FROM lineage_revisions WHERE id=? AND revision=?", (record["id"], record["revision"])
        ).fetchone()
        if prior and json.loads(prior[0])["digest"] != record["digest"]:
            raise ValueError("A stored lineage revision cannot be overwritten")
        con.execute(
            "INSERT OR IGNORE INTO lineage_revisions VALUES (?,?,?)",
            (record["id"], record["revision"], _json(record)),
        )
        con.execute("INSERT OR REPLACE INTO lineage VALUES (?,?)", (record["id"], _json(record)))
        con.execute(
            "INSERT INTO lineage_events(at,id,action,detail,revision) VALUES (?,?,?,?,?)",
            (time.time(), record["id"], action, detail, record["revision"]),
        )

    def _prepare(self, record):
        record["quality"] = validate_lineage(record["graph"])
        record["revision"] += 1
        record.update(status="draft", approval=None, updated_at=time.time())
        record["digest"] = self._digest(record)
        return record

    def create_demo(self, seed=42):
        graph_id = f"retail-seed-{_seed(seed)}"
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("SELECT body FROM lineage WHERE id=?", (graph_id,)).fetchone()
            if existing:
                return json.loads(existing[0])
            directory = (self.home / "lineage-data" / graph_id).resolve()
            if not directory.is_relative_to(self.home):
                raise ValueError("Demo directory resolves outside the lineage home")
            graph = generate_demo(directory, seed)
            observed = {
                key: copy.deepcopy(graph[key])
                for key in (
                    "datasets",
                    "processes",
                    "runs",
                    "column_lineage",
                    "observed_dependencies",
                    "seed",
                    "synthetic",
                    "version",
                )
            }
            record = self._prepare(
                {
                    "id": graph_id,
                    "graph": graph,
                    "revision": 0,
                    "created_at": time.time(),
                    "observed_evidence": observed,
                }
            )
            self._save(con, record, "created")
            return record

    def list(self):
        with self._connect() as con:
            values = [
                json.loads(row[0])
                for row in con.execute("SELECT body FROM lineage ORDER BY rowid DESC LIMIT 100")
            ]
        return [
            {
                key: value[key]
                for key in ("id", "revision", "digest", "status", "approval", "quality", "created_at")
            }
            | {"title": value["graph"]["title"], "seed": value["graph"]["seed"]}
            for value in values
        ]

    def get(self, graph_id):
        with self._connect() as con:
            return self._get(con, graph_id)

    def history(self, graph_id):
        with self._connect() as con:
            self._get(con, graph_id)
            values = [
                json.loads(row[0])
                for row in con.execute(
                    "SELECT body FROM lineage_revisions WHERE id=? ORDER BY revision DESC LIMIT 100",
                    (graph_id,),
                )
            ]
        events = self.events(graph_id)
        return [
            {key: value[key] for key in ("revision", "digest", "created_at", "status", "quality")}
            | {"events": [event for event in events if event["revision"] == value["revision"]]}
            for value in values
        ]

    def events(self, graph_id):
        """Return recent audit events, including human rejection reasons.

        Events migrated from the initial schema have revision=None because their
        original revision was not recorded and cannot safely be reconstructed.
        """
        with self._connect() as con:
            self._get(con, graph_id)
            rows = con.execute(
                "SELECT sequence,at,id,revision,action,detail FROM lineage_events WHERE id=? ORDER BY sequence DESC LIMIT 200",
                (graph_id,),
            ).fetchall()
        keys = ("sequence", "at", "id", "revision", "action", "detail")
        return [dict(zip(keys, row)) for row in rows]

    def get_revision(self, graph_id, revision):
        """Read the immutable snapshot created for a revision, without restoring."""
        if type(revision) is not int or revision < 1:
            raise ValueError("revision must be a positive integer")
        with self._connect() as con:
            self._get(con, graph_id)
            row = con.execute(
                "SELECT body FROM lineage_revisions WHERE id=? AND revision=?", (graph_id, revision)
            ).fetchone()
        if row is None:
            raise ValueError("Historical lineage revision not found")
        record = json.loads(row[0])
        if self._digest(record) != record["digest"]:
            raise ValueError("Historical lineage revision failed integrity validation")
        return record

    def diff(self, graph_id, from_revision, to_revision=None):
        """Compare graph/quality values with escaped JSON paths, at most 100 changes."""
        before = self.get_revision(graph_id, from_revision)
        after = self.get(graph_id) if to_revision is None else self.get_revision(graph_id, to_revision)
        changes = []

        def compare(left, right, path):
            if left == right or len(changes) > 100:
                return
            if isinstance(left, dict) and isinstance(right, dict):
                for key in sorted(set(left) | set(right)):
                    child = path + "/" + key.replace("~", "~0").replace("/", "~1")
                    if key not in left or key not in right:
                        changes.append({"path": child, "before": left.get(key), "after": right.get(key)})
                    else:
                        compare(left[key], right[key], child)
                    if len(changes) > 100:
                        break
            elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
                for index, (old, new) in enumerate(zip(left, right)):
                    compare(old, new, path + f"/{index}")
                    if len(changes) > 100:
                        break
            else:
                changes.append({"path": path, "before": left, "after": right})

        for key in ("graph", "quality"):
            compare(before[key], after[key], "/" + key)
        return {
            "id": graph_id,
            "from_revision": before["revision"],
            "to_revision": after["revision"],
            "changes": changes[:100],
            "truncated": len(changes) > 100,
        }

    def revise(self, graph_id, updates, expected_digest):
        if not isinstance(updates, dict) or set(updates) - {
            "title",
            "description",
            "notes",
            "dataset_descriptions",
            "process_descriptions",
            "column_descriptions",
            "edges",
        }:
            raise ValueError(
                "Only descriptions, notes and reviewed edges can be edited; execution facts are immutable"
            )
        if len(_json(updates).encode()) > MAX_GRAPH_BYTES:
            raise ValueError("Lineage edits exceed 1 MB")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            record = self._get(con, graph_id)
            self._check(record, expected_digest)
            graph = record["graph"]
            for field in ("title", "description", "notes"):
                if field in updates:
                    if not _text(updates[field], 200 if field == "title" else 10_000):
                        raise ValueError(f"{field} must be a nonempty bounded string")
                    graph[field] = updates[field]
            for field, collection in (
                ("dataset_descriptions", "datasets"),
                ("process_descriptions", "processes"),
            ):
                if field in updates:
                    values = updates[field]
                    indexed = {item["id"]: item for item in graph[collection]}
                    if not isinstance(values, dict) or any(
                        key not in indexed or not _text(value) for key, value in values.items()
                    ):
                        raise ValueError(f"{field} must map existing IDs to nonempty descriptions")
                    for key, value in values.items():
                        indexed[key]["description"] = value
            if "column_descriptions" in updates:
                values = updates["column_descriptions"]
                indexed = {
                    item["id"]: {column["name"]: column for column in item["columns"]}
                    for item in graph["datasets"]
                }
                if not isinstance(values, dict):
                    raise ValueError("column_descriptions must map dataset IDs to column descriptions")
                for dataset_id, descriptions in values.items():
                    if (
                        dataset_id not in indexed
                        or not isinstance(descriptions, dict)
                        or any(
                            key not in indexed[dataset_id] or not _text(value)
                            for key, value in descriptions.items()
                        )
                    ):
                        raise ValueError("Describe existing dataset columns only")
                    for key, value in descriptions.items():
                        indexed[dataset_id][key]["description"] = value
            if "edges" in updates:
                proposed = updates["edges"]
                if (
                    not isinstance(proposed, list)
                    or len(proposed) > MAX_EDGES
                    or any(not isinstance(edge, dict) for edge in proposed)
                ):
                    raise ValueError("edges must be a bounded list of edge objects")
                observed = record["observed_evidence"]["observed_dependencies"]
                for edge in proposed:
                    if set(edge) - {
                        "id",
                        "source",
                        "target",
                        "process_id",
                        "description",
                        "confidence",
                        "evidence",
                    }:
                        raise ValueError(
                            "Unsupported edge fields; observed facts cannot be embedded as edits"
                        )
                    evidence = edge.get("evidence")
                    if not isinstance(evidence, dict):
                        raise ValueError("Edge evidence must distinguish observed from asserted information")
                    if evidence.get("kind") == "observed" and not any(
                        all(
                            edge.get(key) == item.get(key)
                            for key in ("source", "target", "process_id", "evidence")
                        )
                        for item in observed
                    ):
                        raise ValueError(
                            "New observations cannot be fabricated; use kind=asserted with an honest note"
                        )
                graph["edges"] = copy.deepcopy(proposed)
            self._prepare(record)
            self._save(con, record, "revised")
            return record

    def _verify_files(self, record):
        root = self.home / "lineage-data" / record["id"]
        for dataset in record["observed_evidence"]["datasets"]:
            try:
                path = (root / dataset["path"]).resolve(strict=True)
            except OSError:
                raise ValueError(
                    "Synthetic evidence file is missing or inaccessible; restore the original evidence before review"
                ) from None
            if (
                not path.is_relative_to(root.resolve())
                or not path.is_file()
                or path.stat().st_size > 5_000_000
            ):
                raise ValueError("Synthetic evidence file is missing or outside its bounded demo directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != dataset["sha256"]:
                raise ValueError("Synthetic CSV evidence changed; do not approve this lineage")

    def approve(self, graph_id, expected_digest, reviewer):
        if not _text(reviewer, 200):
            raise ValueError("Reviewer name is required and must be under 201 characters")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            record = self._get(con, graph_id)
            self._check(record, expected_digest)
            if record["status"] not in {"draft", "rejected"}:
                raise ValueError("Lineage is not awaiting human approval")
            current = validate_lineage(record["graph"])
            if current != record["quality"] or not current["conforms"]:
                raise ValueError("Resolve lineage findings and prepare a current revision before approval")
            self._verify_files(record)
            record.update(
                status="approved",
                approval={"digest": record["digest"], "reviewer": reviewer.strip(), "at": time.time()},
            )
            self._save(con, record, "approved", reviewer.strip())
            return record

    def verified_approved(self, graph_id, expected_digest):
        """Read an approved snapshot only after current policy and CSV checks.

        This creates no approval and performs no cloud operations. Callers can
        attach this exact graph to another reviewable metadata proposal. File
        verification is a bounded point-in-time check, not an OS security wall.
        """
        with self._connect() as con:
            record = self._get(con, graph_id)
            self._check(record, expected_digest)
            approval = record.get("approval")
            if (
                record.get("status") != "approved"
                or not isinstance(approval, dict)
                or approval.get("digest") != record["digest"]
            ):
                raise ValueError("The current lineage revision needs human approval before attachment")
            if (
                not _text(approval.get("reviewer"), 200)
                or type(approval.get("at")) not in (int, float)
                or not math.isfinite(approval["at"])
                or not 0 <= approval["at"] <= time.time() + 60
            ):
                raise ValueError("Invalid lineage approval record; review and approve again")
            current = validate_lineage(record["graph"])
            if current != record["quality"] or not current["conforms"]:
                raise ValueError("Lineage validation changed; prepare and approve a current revision")
            self._verify_files(record)
            return record

    def reject(self, graph_id, expected_digest, reason):
        if not _text(reason, 2000):
            raise ValueError("A nonempty rejection reason is required")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            record = self._get(con, graph_id)
            self._check(record, expected_digest)
            record.update(status="rejected", approval=None)
            self._save(con, record, "rejected", reason.strip())
            return record

    def restore(self, graph_id, revision, expected_digest):
        if type(revision) is not int or revision < 1:
            raise ValueError("revision must be a positive integer")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            record = self._get(con, graph_id)
            self._check(record, expected_digest)
            row = con.execute(
                "SELECT body FROM lineage_revisions WHERE id=? AND revision=?", (graph_id, revision)
            ).fetchone()
            if row is None:
                raise ValueError("Historical lineage revision not found")
            previous = json.loads(row[0])
            if (
                self._digest(previous) != previous["digest"]
                or previous["observed_evidence"] != record["observed_evidence"]
            ):
                raise ValueError("Historical execution evidence failed integrity validation")
            record["graph"] = copy.deepcopy(previous["graph"])
            self._prepare(record)
            self._save(con, record, "restored", f"from_revision={revision}")
            return record

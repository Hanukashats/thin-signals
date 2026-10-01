"""Deterministic research triage. Python 3.8+, no third-party dependencies."""
import argparse
import csv
import copy
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def validate_model(model):
    weights = model["weights"]
    if not weights or any(isinstance(w,bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Weights must be finite and non-negative")
    if not math.isclose(sum(weights.values()), 100):
        raise ValueError("Weights must sum to 100")
    date.fromisoformat(model["as_of"])
    if model.get("stream","resurrection") not in {"resurrection","emergence"}:
        raise ValueError("Unknown signal stream")

def for_stream(model, stream):
    model = copy.deepcopy(model)
    model["stream"] = stream
    if stream == "emergence":
        # A new discovery need not have an old lineage. Expert starting weights.
        extra = model["weights"]["history"]
        model["weights"]["history"] = 0
        model["weights"]["bottleneck"] += extra/2
        model["weights"]["evidence"] += extra/2
    validate_model(model)
    return model

def evaluate(candidate, model, source_lookup=None):
    validate_model(model)
    if source_lookup is None:
        source_lookup = {s["id"]:s for s in read_json(ROOT/"sources.json")}
    scores = candidate["scores"]
    if set(scores) != set(model["weights"]):
        raise ValueError("Score dimensions must exactly match the model")
    lower, missing_weight = 0.0, 0.0
    missing = []
    for key, weight in model["weights"].items():
        value = scores[key]
        if weight == 0:
            continue
        if value is None:
            missing.append(key)
            missing_weight += weight
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 5:
                raise ValueError("Invalid score for " + key)
            lower += weight * value / 5
    as_of = date.fromisoformat(model["as_of"])
    checked = date.fromisoformat(candidate["as_of"])
    historical_year = candidate.get("historical_year")
    age = as_of.year - historical_year if isinstance(historical_year,int) else None
    failures, holds = [], []
    if checked > as_of:
        failures.append("future_information")
    if not candidate.get("source_ids"):
        failures.append("missing_sources")
    for source_id in candidate.get("source_ids",[]):
        source = source_lookup.get(source_id)
        if source is None:
            failures.append("unknown_source_id")
            continue
        published = source.get("published")
        if published:
            # Compare only known precision. A year is not fabricated into a day.
            try:
                parts = [int(p) for p in published.split("-")]
                cutoff = [as_of.year, as_of.month, as_of.day][:len(parts)]
                if parts > cutoff:
                    failures.append("future_publication")
            except ValueError:
                holds.append("publication_date_needs_review")
    if model.get("stream","resurrection") == "resurrection":
        if age is None:
            holds.append("missing_historical_date")
        elif age < model["thresholds"]["minimum_age"]:
            failures.append("too_young_for_resurrection_profile")
    if candidate.get("retracted") is True or candidate.get("science_status") == "refuted":
        failures.append("refuted_or_retracted")
    if candidate.get("commercial_status") in model["exclude_commercial_states"]:
        failures.append("commercially_occupied")
    if candidate.get("ip_status") == "unavailable":
        failures.append("rights_unavailable")
    if candidate.get("commercial_status") not in {"unoccupied_verified"}:
        holds.append("commercial_diligence")
    if candidate.get("ip_status") != "access_verified":
        holds.append("rights_diligence")
    if candidate.get("retraction_screen") != "screened_no_flag":
        holds.append("source_integrity_screen")
    if scores["evidence"] is None or scores["evidence"] < 3:
        holds.append("experimental_evidence")
    if model.get("stream","resurrection") == "resurrection" and (scores["history"] is None or scores["history"] < 3):
        holds.append("historical_fit")
    if scores["bottleneck"] is None or scores["bottleneck"] < 3:
        holds.append("bottleneck_not_yet_removed")
    if missing:
        holds.append("incomplete_scores")
    if candidate.get("system_comparison_status") != "validated":
        holds.append("system_comparison")
    if candidate.get("decisive_test_status") != "agreed":
        holds.append("test_protocol")
    if failures:
        decision = "exclude"
    elif lower >= model["thresholds"]["research_priority_lower"]:
        decision = "priority_diligence"
    elif lower >= model["thresholds"]["investigate_lower"]:
        decision = "investigate"
    else:
        decision = "watch"
    qualified = not failures and not holds
    return {"id":candidate["id"], "name":candidate["name"], "score_lower":round(lower, 2),
            "score_upper":round(lower + missing_weight, 2), "unknown_weight":missing_weight,
            "age_years_approx":age, "decision":decision, "fully_qualified":qualified,
            "partner_review_ready":qualified and lower >= model["thresholds"]["partner_review_lower"],
            "failures":failures, "holds":list(dict.fromkeys(holds)), "missing_dimensions":missing}

def rank(candidates, model):
    ids = [c["id"] for c in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate candidate IDs")
    sources = {s["id"]:s for s in read_json(ROOT/"sources.json")}
    results = [evaluate(c, model, sources) for c in candidates]
    results.sort(key=lambda r: (r["decision"] == "exclude", -r["score_lower"], r["id"]))
    for i, result in enumerate(results, 1):
        result["rank"] = i
    return results

def sensitivity(candidates, model):
    baseline = rank(candidates, model)
    ranks = {r["id"]:[r["rank"]] for r in baseline}
    scenarios = 0
    for key in model["weights"]:
        for factor in (0.8, 1.2):
            varied = dict(model)
            weights = dict(model["weights"])
            weights[key] *= factor
            total = sum(weights.values())
            varied["weights"] = {k:100*v/total for k,v in weights.items()}
            for result in rank(candidates, varied):
                ranks[result["id"]].append(result["rank"])
            scenarios += 1
    return {"method":"One weight at a time, +/-20%, renormalized; deterministic ties by ID. Not a probability model.",
            "scenarios":scenarios, "rank_ranges":{key:{"best":min(values),"worst":max(values)} for key,values in ranks.items()}}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=ROOT/"candidates.json")
    parser.add_argument("--model", type=Path, default=ROOT/"model.json")
    parser.add_argument("--stream",choices=["resurrection","emergence"],default=None)
    parser.add_argument("--out", type=Path, default=ROOT/"ranking.json")
    args = parser.parse_args()
    candidates, model = read_json(args.candidates), read_json(args.model)
    if args.stream:
        model = for_stream(model,args.stream)
    results = rank(candidates, model)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT/"sensitivity.json").write_text(json.dumps(sensitivity(candidates, model), ensure_ascii=False, indent=2), encoding="utf-8")
    with (ROOT/"ranking.csv").open("w",encoding="utf-8-sig",newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank","id","technology","score_lower","score_upper","decision","fully_qualified","holds"])
        for result in results:
            writer.writerow([result[k] for k in ("rank","id","name","score_lower","score_upper","decision","fully_qualified")]+["; ".join(result["holds"])])
    print(json.dumps({"candidates":len(results),"fully_qualified":sum(r["fully_qualified"] for r in results),"ranking":str(args.out)},ensure_ascii=False))

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Structural checks only; no source-truth or investment-quality certification."""
import argparse
import datetime as dt
import json
import sys

def validate(data):
    errors, warnings = [], []
    def err(msg): errors.append(msg)
    def date(value, field, required=True):
        if value is None and not required:
            return None
        try:
            return dt.date.fromisoformat(value)
        except (TypeError, ValueError):
            err(field + ": expected YYYY-MM-DD")
            return None
    cutoff = date(data.get("as_of"), "as_of")
    for key in ("sources", "claims", "edges", "gates", "forecasts"):
        if not isinstance(data.get(key), list):
            err(key + ": expected array")
    if errors:
        return errors, warnings
    sources = {}
    for s in data["sources"]:
        if not isinstance(s, dict):
            err("source must be an object")
            continue
        sid = s.get("id")
        if not sid or not isinstance(sid, str) or sid in sources:
            err("source id missing/duplicate/invalid")
            continue
        sources[sid] = s
        if not s.get("locator"): err(sid + ": missing locator")
        if s.get("access_status") not in ("read", "unavailable"):
            err(sid + ": invalid access_status")
        date(s.get("available_at"), sid + ".available_at", required=False)
        if not s.get("origin_group_id"):
            warnings.append(sid + ": independence unknown")
        if not s.get("event_id"):
            warnings.append(sid + ": event identity unknown")
    def refs(ids, field, require=False):
        if not isinstance(ids, list):
            err(field + ": expected array")
            return []
        if require and not ids: err(field + ": evidence required")
        found = []
        for sid in ids:
            if not isinstance(sid, str) or sid not in sources:
                err(field + ": unknown source " + str(sid))
                continue
            s = sources[sid]
            found.append(s)
            if s.get("access_status") != "read":
                err(field + ": unread source " + sid)
            av = date(s.get("available_at"), sid + ".available_at", required=False)
            if av is None: warnings.append(field + ": availability unknown for " + sid)
            elif cutoff and av > cutoff: err(field + ": future evidence " + sid)
        return found
    claimids = set()
    for c in data["claims"]:
        if not isinstance(c, dict):
            err("claim must be an object")
            continue
        cid = c.get("id")
        if not isinstance(cid, str) or not cid or cid in claimids:
            err("claim id missing/duplicate/invalid")
            continue
        claimids.add(cid)
        if not c.get("text"): err(cid + ": missing text")
        if c.get("kind") not in ("fact","inference","hypothesis","forecast"):
            err(cid + ": invalid kind")
        if c.get("status") not in ("verified","supported","unknown","disputed","refuted"):
            err(cid + ": invalid status")
        verified = c.get("kind") == "fact" and c.get("status") == "verified"
        ss = refs(c.get("evidence_for", []), cid + ".for", verified)
        refs(c.get("evidence_against", []), cid + ".against")
        if verified and any(not s.get("available_at") for s in ss):
            err(cid + ": verified fact needs evidence availability")
        if c.get("critical") and c.get("status") in ("unknown","disputed"):
            warnings.append(cid + ": unresolved critical claim")
    for i,e in enumerate(data["edges"]):
        if not isinstance(e, dict):
            err("edge must be an object")
            continue
        if not e.get("from") or not e.get("to"): err("edge endpoints required")
        if e.get("relation") not in ("supplier_of","capable_of","candidate_for","depends_on"):
            err("edge relation invalid")
        refs(e.get("evidence_refs",[]), "edge-" + str(i), e.get("relation")=="supplier_of")
    gates = []
    for g in data["gates"]:
        if not isinstance(g, dict):
            err("gate must be an object")
            continue
        gates.append(g)
        if g.get("state") not in ("PASS","UNKNOWN","FAIL"): err("gate state invalid")
        if g.get("confidence") not in ("verified","supported","weak"): err("gate confidence invalid")
        refs(g.get("evidence_refs",[]), "gate-" + str(g.get("id")),
             g.get("state")=="FAIL" and g.get("confidence") in ("verified","supported"))
    dec = data.get("decision", {})
    if not isinstance(dec, dict):
        err("decision must be an object")
        dec = {}
    action = dec.get("action")
    allowed = {"RESEARCH","VALIDATE","EXPERIMENTAL BUILD","PRODUCTION BUILD",
               "PARTNER DILIGENCE","INVESTMENT DILIGENCE","HOLD","PIVOT","KILL"}
    if action not in allowed: err("invalid action")
    if not dec.get("rationale"): err("decision rationale required")
    if action=="HOLD" and not dec.get("reentry_trigger"): err("HOLD requires reentry_trigger")
    date(dec.get("review_at"), "review_at")
    if action=="PRODUCTION BUILD":
        if dec.get("readiness")!="R4": err("production requires R4 in this structural contract")
        if not gates or any(g.get("state")!="PASS" for g in gates):
            err("production requires explicit passing gates")
        if any(c.get("critical") and c.get("status") in ("unknown","disputed","refuted")
               for c in data["claims"] if isinstance(c,dict)):
            err("production has unresolved/refuted critical claims")
    inv = data.get("investment", {})
    if not isinstance(inv, dict):
        err("investment must be an object")
        inv = {}
    if inv.get("assessed"):
        for key in ("instrument","price_as_of","financials_as_of","valuation_status","access_status"):
            if not inv.get(key): err("investment missing " + key)
        for key in ("price_as_of","financials_as_of"):
            value = date(inv.get(key), "investment." + key)
            if value and cutoff and value>cutoff: err("investment uses future data")
        refs(inv.get("evidence_refs",[]), "investment", True)
        if inv.get("valuation_status")!="complete" or inv.get("access_status")!="verified":
            warnings.append("investment incomplete: no positive entry conclusion")
    for i,f in enumerate(data["forecasts"]):
        if not isinstance(f,dict):
            err("forecast must be object")
            continue
        for key in ("question","outcome_rule"):
            if not f.get(key): err("forecast missing " + key)
        issued = date(f.get("issued_at"), "forecast.issued_at")
        resolved = date(f.get("resolve_by"), "forecast.resolve_by")
        if issued and resolved and resolved<=issued: err("forecast horizon must be positive")
        if issued and cutoff and issued>cutoff: err("forecast issued after as_of")
        p = f.get("probability")
        if p is not None and (isinstance(p,bool) or not isinstance(p,(int,float)) or not 0<=p<=1):
            err("forecast probability outside [0,1]")
    if not data["claims"]: warnings.append("empty claim ledger; this is only a template")
    return errors, warnings

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file")
    args = p.parse_args()
    try:
        with open(args.file,encoding="utf-8") as stream:
            data = json.load(stream)
        if not isinstance(data,dict): raise ValueError("root must be object")
        errors,warnings = validate(data)
    except (OSError,ValueError,TypeError) as ex:
        print(json.dumps({"errors":[str(ex)],"warnings":[]},ensure_ascii=False))
        return 2
    print(json.dumps({"structural_status":"FAIL" if errors else "PASS",
                      "errors":errors,"warnings":warnings,
                      "semantic_review_required":True},ensure_ascii=False,indent=2))
    return 1 if errors else 0
if __name__=="__main__":
    sys.exit(main())

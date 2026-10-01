"""Small, read-only discovery connector. Does not turn abstracts into validated claims."""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent":"ThinSignalsResearch/0.1 (public metadata research)","Accept":"application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429,500,502,503,504) or attempt == 2:
                raise
            time.sleep(1+attempt*2)

def metadata_record(item):
    return {"doi":item.get("DOI"), "title":item.get("title"), "published":item.get("published"),
            "published_online":item.get("published-online"), "type":item.get("type"),
            "url":item.get("URL"), "publisher":item.get("publisher"),
            "update_to":item.get("update-to",[]), "relation":item.get("relation",{}),
            "funders":item.get("funder",[]), "license":item.get("license",[])}

def check_doi(source):
    url = "https://api.crossref.org/works/"+urllib.parse.quote(source["doi"],safe="")
    try:
        item = get_json(url)["message"]
        # Corrections/retractions are not always attached to the original record.
        # An empty update-to must never be interpreted as proof of no retraction.
        return {"source_id":source["id"],"status":"retrieved","record":metadata_record(item)}
    except Exception as error:
        return {"source_id":source["id"],"status":"error","error":str(error)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query",action="append",default=[])
    parser.add_argument("--check-dois",action="store_true")
    parser.add_argument("--rows",type=int,default=3)
    parser.add_argument("--until",default="2026-09-29")
    parser.add_argument("--output",type=Path,default=ROOT/"metadata_snapshot.json")
    args = parser.parse_args()
    if not 1 <= args.rows <= 25:
        parser.error("rows must be 1..25")
    snapshot = {"retrieved_at":datetime.now(timezone.utc).isoformat(),"cutoff":args.until,
                "limitations":"Read-only metadata. Not a complete retraction, ownership, funding or patent search.",
                "crossref_dois":[],"queries":[]}
    if args.check_dois:
        sources = json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
        with ThreadPoolExecutor(max_workers=3) as pool:
            snapshot["crossref_dois"] = list(pool.map(check_doi,[s for s in sources if s.get("doi")]))
    for query in args.query:
        params = urllib.parse.urlencode({"query":query,"rows":args.rows,"filter":"until-pub-date:"+args.until})
        try:
            records = get_json("https://api.crossref.org/works?"+params)["message"]["items"]
            snapshot["queries"].append({"provider":"Crossref","query":query,"status":"retrieved","records":[metadata_record(r) for r in records]})
        except Exception as error:
            snapshot["queries"].append({"provider":"Crossref","query":query,"status":"error","error":str(error)})
        params = urllib.parse.urlencode({"query":"("+query+") AND FIRST_PDATE:[1900-01-01 TO "+args.until+"]","format":"json","pageSize":args.rows,"resultType":"lite"})
        try:
            result = get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"+params)
            snapshot["queries"].append({"provider":"Europe PMC","query":query,"status":"retrieved","hit_count":result.get("hitCount"),"records":result.get("resultList",{}).get("result",[])})
        except Exception as error:
            snapshot["queries"].append({"provider":"Europe PMC","query":query,"status":"error","error":str(error)})
    args.output.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"dois":len(snapshot["crossref_dois"]),"doi_errors":sum(r["status"]=="error" for r in snapshot["crossref_dois"]),"queries":len(snapshot["queries"]),"query_errors":sum(r["status"]=="error" for r in snapshot["queries"]),"output":str(args.output)},ensure_ascii=False))

if __name__ == "__main__":
    main()

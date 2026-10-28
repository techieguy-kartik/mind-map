"""Build Atlas's attributed candidate-company catalog from Wikidata.

The catalog establishes identity and sector discovery only. It does not verify
valuation, revenue, ownership, leadership, or active strategy.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ENDPOINT = "https://query.wikidata.org/sparql"
TARGET_PER_SECTOR = 100
OUTPUT = Path(__file__).resolve().parents[1] / "server/data/company_registry.json"

# Broad portfolios are intentional: a company may belong to several sectors.
# Niche labels such as quantum and spatial intelligence do not have 100 verified
# $500m companies, so their discovery portfolios include adjacent industries and
# remain explicitly unqualified until financial evidence is attached.
SECTORS = {
    "AI & Machine Learning": ["Q11660"],
    "Energy & Green Infrastructure": ["Q48767813", "Q2316331", "Q8024050"],
    "Automotive & Mobility": ["Q190117", "Q122198663"],
    "Spatial & Space Intelligence": ["Q2729047", "Q483130", "Q121535865", "Q2944004"],
    "Aerospace & Defence": ["Q3477363"],
    "Quantum & Advanced Compute": ["Q17995793", "Q2986369"],
    "Life Sciences & Bioengineering": ["Q12303494", "Q507443"],
    "Telecom & 6G": ["Q418", "Q2401742"],
    "Semiconductors": ["Q2986369"],
    "Robotics & Industrial Automation": ["Q170978", "Q5086032"],
    "Cybersecurity": ["Q124102257", "Q3510521"],
    "Fintech & Digital Payments": ["Q16319025"],
    "Critical Materials & Batteries": ["Q99529212", "Q1945600"],
    "Cloud & Enterprise Software": ["Q483639"],
    "Logistics & Supply Chain": ["Q177777"],
}

COMPANY_TYPES = [
    "Q18388277",  # technology company
    "Q6881511",   # enterprise
    "Q4830453",   # business
    "Q783794",    # company
    "Q891723",    # public company
    "Q1058914",   # software company
    "Q658255",    # subsidiary company
    "Q1589009",   # privately held company
    "Q1326624",   # electricity supply company
]

PALETTE = ["#6573bc", "#3b8b72", "#9a5c5c", "#427b9b", "#6d81a7", "#82649f", "#75934b", "#4c8985"]


def _query(sector: str, industries: list[str]) -> str:
    values = " ".join(f"wd:{value}" for value in industries)
    return f"SELECT DISTINCT ?item WHERE {{ VALUES ?industry {{ {values} }} ?item wdt:P452 ?industry. }} LIMIT 500"


def _ids(item, prop):
    values=[]
    for claim in item.get("claims",{}).get(prop,[]):
        if claim.get("rank")=="deprecated":
            continue
        value=claim.get("mainsnak",{}).get("datavalue",{}).get("value")
        if isinstance(value,dict) and value.get("id"):
            values.append(value["id"])
    return values


def _entities(client, ids):
    result={}
    for offset in range(0,len(ids),50):
        response=client.get("https://www.wikidata.org/w/api.php",params={
            "action":"wbgetentities","ids":"|".join(ids[offset:offset+50]),
            "props":"labels|aliases|claims|descriptions","languages":"en","format":"json",
        })
        response.raise_for_status()
        result.update(response.json().get("entities",{}))
        time.sleep(.15)
    return result


def _initials(name: str) -> str:
    words = [word for word in name.replace("&", " ").split() if word]
    return "".join(word[0] for word in words[:2]).upper() or "C"


def build() -> dict:
    companies={}
    coverage={}
    errors={}
    headers={"User-Agent":"AtlasIntelligence/0.3 (https://github.com/techieguy-kartik/mind-map)"}
    cache_path=OUTPUT.with_name("registry_fetch_cache.json")
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    with httpx.Client(headers=headers,timeout=30) as client:
        for index,(sector,industries) in enumerate(SECTORS.items()):
            try:
                if sector in cache:
                    data=cache[sector]
                else:
                    response=client.get(ENDPOINT,params={"query":_query(sector,industries),"format":"json"})
                    response.raise_for_status()
                    ids=[x["item"]["value"].rsplit("/",1)[-1] for x in response.json()["results"]["bindings"]]
                    data=_entities(client,ids)
                    cache[sector]=data
                    cache_path.write_text(json.dumps(cache))
                selected=[]
                for qid,item in data.items():
                    name=item.get("labels",{}).get("en",{}).get("value","")
                    if not name or not set(_ids(item,"P31")) & set(COMPANY_TYPES):
                        continue
                    selected.append((qid,item,name))
                selected.sort(key=lambda value:(-len(value[1].get("claims",{})),value[2].casefold()))
                selected=selected[:TARGET_PER_SECTOR]
                country_ids=list({qid for _,item,_ in selected for qid in _ids(item,"P17")})
                countries=_entities(client,country_ids)
                for qid,item,name in selected:
                    country_names=[countries.get(x,{}).get("labels",{}).get("en",{}).get("value") for x in _ids(item,"P17")]
                    row=companies.setdefault(qid,{
                        "id":f"wd-{qid.casefold()}","wikidata_id":qid,"name":name,
                        "initials":_initials(name),"country":next((x for x in country_names if x),"Country pending"),
                        "sector":sector,"sectors":[],"group":"Group attribution pending",
                        "color":PALETTE[index%len(PALETTE)],"aliases":[name]+[x['value'] for x in item.get('aliases',{}).get('en',[])][:8],
                        "type":"company","qualification":"Not yet verified",
                        "description":item.get("descriptions",{}).get("en",{}).get("value",f"Candidate in the {sector} discovery portfolio.")+". Financial threshold and current status require primary verification.",
                        "demo":False,"registry_status":"candidate","registry_source":"Wikidata industry classification",
                        "source_url":f"https://www.wikidata.org/wiki/{qid}","source_revision":item.get("lastrevid"),
                    })
                    if sector not in row['sectors']:
                        row['sectors'].append(sector)
                coverage[sector]=len(selected)
                print(f"{sector}: {len(selected)}/{TARGET_PER_SECTOR}",flush=True)
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                errors[sector]=type(exc).__name__
                coverage[sector]=0
                print(f"{sector}: source unavailable ({type(exc).__name__})",flush=True)
            time.sleep(.5)
    return {"version":"registry-v1","generated_at":datetime.now(timezone.utc).isoformat(),
        "source":"Wikidata Query Service and Entity API","source_url":ENDPOINT,"license":"CC0-1.0",
        "target_per_sector":TARGET_PER_SECTOR,"sector_coverage":coverage,"source_errors":errors,
        "companies":sorted(companies.values(),key=lambda row:(row['name'].casefold(),row['wikidata_id']))}


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    catalog=build()
    if not catalog['companies']:
        raise SystemExit('No valid companies retrieved; existing catalog was preserved')
    OUTPUT.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n")
    print(f"wrote {len(catalog['companies'])} unique candidates")

import os
import gzip
import json
import urllib.request
import urllib.error

os.makedirs("docs/probes", exist_ok=True)

# Select 5 companies from universe
selected = []
with gzip.open("data/signalpost-universe.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        # Grab a mix: with employees, with website, without
        if len(selected) == 0 and row.get("employees", 0) and row.get("employees") > 5:
            selected.append(row)
        elif len(selected) == 1 and not row.get("employees"):
            selected.append(row)
        elif len(selected) == 2 and row.get("website"):
            selected.append(row)
        elif len(selected) == 3 and row.get("legal_form") == "AS":
            selected.append(row)
        elif len(selected) == 4:
            selected.append(row)
            break

print(f"Selected {len(selected)} companies from universe:")
for s in selected:
    print(f"  {s['organisation_number']}: {s['name']} (emp: {s.get('employees')}, web: {s.get('website')})")

HEADERS = {"User-Agent": "signalpost-research-agent/1.0", "Accept": "application/json"}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return resp.status, json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e), "raw": body.decode("utf-8", errors="replace")}
    except Exception as e:
        return 0, {"error": str(e)}

KEYS_TO_CHECK = [
    "hjemmeside", "epostadresse", "telefon", "mobil",
    "vedtektsfestetFormaal", "aktivitet",
    "naeringskode1", "naeringskode2", "naeringskode3",
    "antallAnsatte", "forretningsadresse", "postadresse",
    "institusjonellSektorkode", "registreringsdatoEnhetsregisteret",
    "stiftelsesdato", "konkurs", "underAvvikling", "overordnetEnhet"
]

report_rows = []

for comp in selected:
    orgnr = comp["organisation_number"]
    print(f"\n--- Probing {orgnr} ({comp['name']}) ---")
    
    # 1. Enhet
    url_enhet = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}"
    code, data_enhet = fetch_json(url_enhet)
    with open(f"docs/probes/{orgnr}_enhet.json", "w", encoding="utf-8") as out:
        json.dump(data_enhet, out, indent=2, ensure_ascii=False)
    print(f"  Enhet: HTTP {code}")
    
    # Check keys
    present_keys = {k: (k in data_enhet) for k in KEYS_TO_CHECK}
    
    # 2. Underenheter
    url_sub = f"https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={orgnr}&size=1000"
    code_sub, data_sub = fetch_json(url_sub)
    with open(f"docs/probes/{orgnr}_underenheter.json", "w", encoding="utf-8") as out:
        json.dump(data_sub, out, indent=2, ensure_ascii=False)
    sub_units = (data_sub.get("_embedded") or {}).get("underenheter") or []
    sub_has_web = any("hjemmeside" in u for u in sub_units)
    sub_has_email = any("epostadresse" in u for u in sub_units)
    print(f"  Underenheter: HTTP {code_sub}, count={len(sub_units)}, sub_has_web={sub_has_web}, sub_has_email={sub_has_email}")
    
    # 3. Roller
    url_roller = f"https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
    code_roller, data_roller = fetch_json(url_roller)
    with open(f"docs/probes/{orgnr}_roller.json", "w", encoding="utf-8") as out:
        json.dump(data_roller, out, indent=2, ensure_ascii=False)
    rollegrupper = data_roller.get("rollegrupper") or []
    print(f"  Roller: HTTP {code_roller}, rollegrupper={len(rollegrupper)}")
    
    # 4. Konsernstruktur
    url_konsern = f"https://data.brreg.no/enhetsregisteret/api/konsernstruktur/{orgnr}"
    code_konsern, data_konsern = fetch_json(url_konsern)
    with open(f"docs/probes/{orgnr}_konsern.json", "w", encoding="utf-8") as out:
        json.dump(data_konsern, out, indent=2, ensure_ascii=False)
    print(f"  Konsernstruktur: HTTP {code_konsern}")
    
    # 5. Regnskap
    url_regnskap = f"https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
    code_regnskap, data_regnskap = fetch_json(url_regnskap)
    with open(f"docs/probes/{orgnr}_regnskap.json", "w", encoding="utf-8") as out:
        json.dump(data_regnskap, out, indent=2, ensure_ascii=False)
    years_count = len(data_regnskap) if isinstance(data_regnskap, list) else 0
    print(f"  Regnskap: HTTP {code_regnskap}, accounting_years={years_count}")
    
    report_rows.append({
        "orgnr": orgnr,
        "name": comp["name"],
        "keys": present_keys,
        "subunits_count": len(sub_units),
        "sub_has_web": sub_has_web,
        "sub_has_email": sub_has_email,
        "accounting_years": years_count,
        "konsern_code": code_konsern
    })

with open("docs/probes/summary.json", "w", encoding="utf-8") as f:
    json.dump(report_rows, f, indent=2, ensure_ascii=False)

print("\n=== SUMMARY OF KEY PRESENCE ACROSS 5 COMPANIES ===")
for k in KEYS_TO_CHECK:
    found = [r["orgnr"] for r in report_rows if r["keys"].get(k)]
    print(f"{k}: present in {len(found)}/5 ({', '.join(found) if found else 'none'})")

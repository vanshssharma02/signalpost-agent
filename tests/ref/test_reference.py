from signalpost.ref.orgnr import normalize, is_valid, find_orgnrs, assess_page
from signalpost.ref.domains import candidate_hosts, email_domain_candidate, name_tokens
from signalpost.ref.claims import claim_key, merge_claims, canonical

NORID = "985821585"      # Norid AS (public example in Norid's own docs)
OTHER = "988077917"      # valid example from python-stdnum docs


def test_mod11():
    assert is_valid(NORID) and is_valid(OTHER)
    assert not is_valid("988077918") and not is_valid("12345678") and not is_valid(None)
    assert normalize("985 821 585") == NORID and normalize("NO 985.821.585 MVA") == NORID


def test_find_formats_and_labels():
    for text in (f"Org.nr. {NORID}", "Org.nr: 985 821 585", "Organisasjonsnummer 985.821.585", "NO 985 821 585 MVA"):
        hits = [h for h in find_orgnrs(text) if h.orgnr == NORID]
        assert hits and hits[0].valid, text
    assert [h for h in find_orgnrs("Ring 73 55 73 55 eller 4773557355") if h.orgnr == NORID] == []


def test_phone_and_long_digit_runs_are_not_orgnrs():
    assert find_orgnrs("konto 1234 56 78901, tlf +47 912 34 567") == []


def test_page_verdicts():
    assert assess_page(f"Norid AS, org.nr. {NORID}", NORID)["verdict"] == "exact"
    assert assess_page("Hjem – ingen nummer her", NORID)["verdict"] == "none"
    # agency / group page: someone else's labelled number, ours unlabelled -> conflict
    assert assess_page(f"Våre kunder: {NORID}. Byrå: Org.nr {OTHER}", NORID)["verdict"] == "conflict"
    # same page but the other number belongs to our own family (subunit / parent) -> exact
    assert assess_page(f"Org.nr {NORID} ... Org.nr {OTHER}", NORID, family={OTHER})["verdict"] == "exact"
    assert assess_page(f"Org.nr {OTHER}", NORID)["verdict"] == "conflict"


def test_domain_candidates():
    hosts = candidate_hosts("Bjørn & Sønner Rør AS")
    assert "bjornsonnerror.no" in hosts and "bjorn-sonner-ror.no" in hosts
    assert "bjoernsoennerroer.no" in hosts or any(h.startswith("bjoern") for h in hosts)
    assert candidate_hosts("AS") == []
    assert len(candidate_hosts("Acme Consulting Group AS")) <= 12
    assert name_tokens("Fjord Invest Holding AS") == ["fjord"]


def test_email_domain():
    assert email_domain_candidate("post@acme.no") == "acme.no"
    assert email_domain_candidate("ola@gmail.com") is None
    assert email_domain_candidate("bad") is None


def _claim(org, field, disc, value):
    return {"key": claim_key(org, field, disc), "field": field, "value": value}


def test_merge_is_idempotent_and_detects_real_change():
    t1, t2, t3 = "2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "2026-10-03T00:00:00Z"
    crawl = [_claim(NORID, "job_posting", "uuid-1", {"title": "Utvikler"}), _claim(NORID, "website", "", "https://norid.no/")]
    store, ch = merge_claims({}, crawl, t1, rechecked_fields={"job_posting", "website"})
    assert {c["type"] for c in ch} == {"added"} and len(store) == 2
    store2, ch2 = merge_claims(store, crawl, t2, rechecked_fields={"job_posting", "website"})
    assert ch2 == [] and len(store2) == 2                                  # no duplicates, no false changes
    assert all(v["first_observed_at"] == t1 and v["last_verified_at"] == t2 for v in store2.values())
    # unrelated key order / whitespace must not look like a change
    reordered = [_claim(NORID, "job_posting", "uuid-1", {"title": " Utvikler "}), crawl[1]]
    _, ch3 = merge_claims(store2, reordered, t3, rechecked_fields={"job_posting", "website"})
    assert ch3 == []
    # failed refresh of the jobs source must NOT erase the last supported value
    store4, ch4 = merge_claims(store2, [crawl[1]], t3, rechecked_fields={"website"})
    assert ch4 == [] and "removed_at" not in store4[claim_key(NORID, "job_posting", "uuid-1")]
    # successful re-check that no longer lists the job => removed (history preserved)
    store5, ch5 = merge_claims(store2, [crawl[1]], t3, rechecked_fields={"website", "job_posting"})
    assert [c["type"] for c in ch5] == ["removed"]
    # a changed value is a change, with the old value preserved
    changed = [_claim(NORID, "job_posting", "uuid-1", {"title": "Senior utvikler"}), crawl[1]]
    store6, ch6 = merge_claims(store2, changed, t3, rechecked_fields={"website", "job_posting"})
    assert [c["type"] for c in ch6] == ["changed"]
    assert store6[claim_key(NORID, "job_posting", "uuid-1")]["history"][0]["value"] == {"title": "Utvikler"}


def test_canonical_is_stable():
    assert canonical({"b": 1, "a": "x "}) == canonical({"a": "x", "b": 1})

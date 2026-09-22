"""Reference routing policy; not a production service or a truth verifier.

The caller supplies adjudicated facts, never free-form LLM confidence.
State is written transactionally by the application, outside this example.
"""
from datetime import date
from math import log2

STATUSES = {'verified', 'supported', 'unknown', 'disputed', 'refuted'}

def route(s):
    """Always apply evidence gates before budget or deadline shortcuts."""
    required = {'as_of','novelty','maturity','critical_claims','fatal_finding',
                'evidence_events','independent_origins','countersearch_done',
                'source_availability_valid','budget_exhausted',
                'branches_complete','transition_verified'}
    if not required <= s.keys():
        return {'action':'HOLD','reason':'invalid_contract','trigger':'complete_required_fields'}
    try: date.fromisoformat(s['as_of'])
    except (ValueError, TypeError):
        return {'action':'HOLD','reason':'invalid_as_of','trigger':'correct_date'}
    if (s['novelty'] not in {'new','known','unclear'} or
        s['maturity'] not in {'emerging','established','unclear'} or
        s['fatal_finding'] not in {'verified','weak','none'} or
        not isinstance(s['critical_claims'],list) or
        any(x not in STATUSES for x in s['critical_claims']) or
        any(type(s[k]) is not bool for k in ['countersearch_done','source_availability_valid','budget_exhausted','branches_complete','transition_verified']) or
        any(type(s[k]) is not int or s[k]<0 for k in ['evidence_events','independent_origins'])):
        return {'action':'HOLD','reason':'invalid_contract','trigger':'correct_types_and_enums'}
    if not s['source_availability_valid']:
        return {'action':'HOLD','reason':'unresolved_availability','trigger':'dated_accessible_evidence'}
    if s['fatal_finding']=='verified' or 'refuted' in s['critical_claims']:
        return {'action':'REJECT_OR_REFRAME','reason':'verified_fatal_claim','trigger':'materially_new_evidence'}
    if s['fatal_finding']=='weak':
        return {'action':'HOLD' if s['budget_exhausted'] else 'VERIFY_COUNTEREVIDENCE','reason':'weak_negative_not_terminal','trigger':'verify_scope_and_origin'}
    if not s['critical_claims'] or any(x in {'unknown','disputed'} for x in s['critical_claims']):
        return {'action':'HOLD' if s['budget_exhausted'] else 'TARGETED_RESEARCH','reason':'critical_unknown','trigger':'resolve_critical_claim'}
    if s['maturity']=='established' or s['novelty']=='known':
        return {'action':'REFRAME_CHILD','reason':'mature_parent','trigger':'new_application_or_mechanism'}
    if s['maturity']=='unclear' or s['novelty']=='unclear':
        return {'action':'HOLD' if s['budget_exhausted'] else 'MATURITY_RESEARCH','reason':'maturity_unclear','trigger':'prior_art_and_adoption_evidence'}
    if not s['countersearch_done']:
        return {'action':'HOLD' if s['budget_exhausted'] else 'COUNTERSEARCH','reason':'missing_falsification','trigger':'counterevidence_pass'}
    if s['evidence_events']==1 and s['independent_origins']>=1:
        return {'action':'WATCHLIST_SINGLETON','reason':'one_origin_result','trigger':'independent_replication_or_new_event'}
    if s['evidence_events']<3 or s['independent_origins']<2:
        return {'action':'WATCHLIST','reason':'insufficient_independence','trigger':'independent_evidence'}
    if not s['branches_complete']:
        return {'action':'HOLD' if s['budget_exhausted'] else 'EXECUTE_BRANCH','reason':'incomplete_relevant_checks','trigger':'complete_selected_branch'}
    if not s['transition_verified']:
        return {'action':'WATCHLIST','reason':'no_verified_change','trigger':'verified_technical_or_adoption_change'}
    return {'action':'RANK_ELIGIBLE','reason':'evidence_gates_passed','trigger':None}

def normalized_growth(recent, previous):
    """Windows are pre-aggregated independent events from a fixed cohort.

    Not a p-value or probability of future success. Requires two complete,
    equally long, non-overlapping periods and an unchanged collection protocol.
    """
    for w in (recent,previous):
        if w.get('coverage')!='complete_for_query' or w.get('complete_period') is not True:
            return None
        if not isinstance(w.get('protocol'),str) or not w['protocol']:
            return None
        if any(type(w.get(k)) is not int for k in ('n','N','days')):
            return None
        if not 0<=w['n']<=w['N'] or w['N']<=0 or w['days']<=0:
            return None
        try:
            start,end=date.fromisoformat(w['start']),date.fromisoformat(w['end'])
        except (KeyError,ValueError,TypeError):return None
        if (end-start).days+1 != w['days']:return None
    if recent['protocol']!=previous['protocol'] or recent['days']!=previous['days']:
        return None
    if previous['end']>=recent['start']:return None
    return log2(((recent['n']+.5)/(recent['N']+1))/((previous['n']+.5)/(previous['N']+1)))

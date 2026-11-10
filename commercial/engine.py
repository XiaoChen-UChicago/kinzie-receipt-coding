"""Conservative, deterministic generic expense-review policy.

This is deliberately NOT the Kinzie PRD v3 implementation. Each workspace supplies
its own rule configuration. Ambiguity always requires human review.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from datetime import date
import re

VERDICTS = ('coded', 'sent_back', 'needs_review')
CENTS = Decimal('0.01')


def money(value) -> Decimal:
    if value is None or str(value).strip() == '':
        raise ValueError('Missing amount')
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError('Invalid amount') from None
    if not d.is_finite() or d < 0 or d > Decimal('1000000000000'):
        raise ValueError('Amount is out of supported bounds')
    try:
        if d != d.quantize(CENTS):
            raise ValueError('Amount must have at most two decimals')
    except InvalidOperation:
        raise ValueError('Invalid amount precision') from None
    return d


def normalize(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().casefold())


def default_policy():
    return {
        'currency': 'USD', 'approval_threshold': '500.00',
        'require_job_match': True, 'require_card_match': True,
        'vendor_aliases': {}, 'item_codes': {}, 'nonbillable_codes': [],
        'personal_keywords': ['snack', 'soda', 'cigarette', 'personal'],
        'approved_jobs': [], 'card_owners': {},
        'approval_required_above_threshold': True,
    }


def validate_policy(policy):
    if not isinstance(policy, dict): raise ValueError('Policy must be an object')
    p = default_policy()
    unknown = set(policy) - set(p)
    if unknown: raise ValueError('Unknown policy fields: ' + ', '.join(sorted(unknown)))
    p.update(policy)
    if p['currency'] not in ('USD','EUR','GBP','KRW'): raise ValueError('Unsupported currency')
    money(p['approval_threshold'])
    for key in ('require_job_match','require_card_match','approval_required_above_threshold'):
        if not isinstance(p[key], bool): raise ValueError(key+' must be boolean')
    for key in ('vendor_aliases','item_codes','card_owners'):
        if not isinstance(p[key], dict): raise ValueError(key+' must be an object')
    for key in ('personal_keywords','approved_jobs','nonbillable_codes'):
        if not isinstance(p[key],list): raise ValueError(key+' must be a list')
    if any(not isinstance(x,str) for k in ('personal_keywords','approved_jobs','nonbillable_codes') for x in p[k]):
        raise ValueError('Policy list entries must be strings')
    if any(not isinstance(k,str) or not isinstance(v,str) for n in ('vendor_aliases','item_codes','card_owners') for k,v in p[n].items()):
        raise ValueError('Policy mapping keys and values must be strings')
    if len(str(p))>100000: raise ValueError('Policy too large')
    return p


def decide(receipt: dict, policy: dict, seen: set | None = None):
    """One receipt, one result. No external actions. Never guess a job/code."""
    p = validate_policy(policy)
    evidence=[]
    result={'verdict':'needs_review','reason':'', 'evidence':evidence,'form_rows':[], 'requires_approval':False}
    def end(verdict, reason):
        result['verdict']=verdict; result['reason']=reason
        return result
    rid=str(receipt.get('receipt_id') or '').strip()
    vendor=str(receipt.get('vendor') or '').strip()
    technician=str(receipt.get('technician') or '').strip()
    job=str(receipt.get('job_number') or '').strip()
    card=str(receipt.get('card_last4') or '').strip()
    day=str(receipt.get('date') or '').strip()
    lines=receipt.get('lines')
    if not rid or not vendor or not technician or not day:
        return end('needs_review','Missing receipt identity, date, vendor, or technician')
    try:
        date.fromisoformat(day)
    except ValueError:
        return end('needs_review','Receipt date is invalid; do not substitute arrival date')
    if not isinstance(lines,list) or not lines:
        return end('needs_review','Missing itemized lines; request original receipt')
    if len(lines)>250: return end('needs_review','Too many lines for automatic review')
    try:
        amounts=[(str(x['description']).strip(),money(x['amount']),money(x.get('tax','0'))) for x in lines]
        total=money(receipt.get('total'))
    except (KeyError,TypeError,ValueError) as exc:
        evidence.append(str(exc))
        return end('sent_back','Missing or invalid amount; request a readable receipt')
    if any(not desc for desc,_,_ in amounts):
        return end('needs_review','Line description missing; cannot assign a cost code')
    calculated=sum((a+t for _,a,t in amounts),Decimal('0'))
    if abs(calculated-total)>CENTS:
        evidence.append(f'Line totals {calculated:.2f} vs stated total {total:.2f}')
        return end('sent_back','Amounts do not reconcile; request the original receipt')
    evidence.append(f'Amounts reconciled: {total:.2f} {p["currency"]}')
    base=sum((a for _,a,_ in amounts),Decimal('0'))
    normalized_vendor=normalize(vendor)
    canonical=p['vendor_aliases'].get(normalized_vendor,vendor)
    evidence.append('Vendor: '+canonical)
    fingerprint=(normalize(technician),normalize(canonical),day,str(total))
    if seen is not None:
        if fingerprint in seen:
            return end('sent_back','Potential duplicate: same technician, vendor, date, and total; manual verification required')
        seen.add(fingerprint)
    if p['require_card_match']:
        if len(card)!=4 or not card.isdigit():
            return end('needs_review','Card last four missing or invalid')
        card_owner=p['card_owners'].get(card)
        if not card_owner:
            return end('needs_review','Card holder not verified in workspace mapping')
        if normalize(card_owner)!=normalize(technician):
            return end('needs_review','Card holder and submitted technician disagree')
        evidence.append('Card holder confirmed')
    if not job:
        return end('needs_review','No job number; human confirmation required')
    if p['require_job_match'] and job not in p['approved_jobs']:
        return end('needs_review','Job number not verified in approved workspace jobs')
    evidence.append('Job verified: '+job)
    if p['approval_required_above_threshold'] and base>money(p['approval_threshold']):
        result['requires_approval']=True
        return end('needs_review',f'Above approval threshold ({p["approval_threshold"]} {p["currency"]}); authorized approver must review')
    keywords=[normalize(x) for x in p['personal_keywords'] if normalize(x)]
    if any(any(k in normalize(desc) for k in keywords) for desc,_,_ in amounts):
        return end('needs_review','Possible personal purchase; human review required')
    groups={}
    for desc,amount,tax in amounts:
        code=p['item_codes'].get(normalize(desc))
        if not code:
            evidence.append('Unmapped item: '+desc)
            return end('needs_review','Item cost code unknown; human mapping required')
        groups.setdefault(code,[]).append((desc,amount,tax))
    for code,ls in sorted(groups.items()):
        result['form_rows'].append({
            'date':day,'vendor':canonical,'job_number':job,'technician':technician,
            'card_last4':card,'amount_before_tax':str(sum((x[1] for x in ls),Decimal(0))),
            'tax':str(sum((x[2] for x in ls),Decimal(0))), 'cost_code':code,
            'description':', '.join(x[0] for x in ls),
            'billable':'no' if code in p['nonbillable_codes'] else 'yes',
        })
    evidence.append('Codes matched exactly to workspace item mapping')
    return end('coded','All fields verified; ready for human-controlled export')

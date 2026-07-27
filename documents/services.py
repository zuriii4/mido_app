"""
Viditelnost dokumentov (PLAN.md sekcia F).

Semantika:
1. bazova brana: required_bu / required_pc na dokumente (null = bez obmedzenia),
2. ak dokument ma inclusion pravidla (v platnom casovom okne), aspon jedno musi sediet,
3. akekolvek matchujuce exclusion pravidlo dokument odoberie.
"""
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from documents.models import Document, DocumentVersion, DocumentVisibilityRule


def _time_window_q(now):
    """Pravidlo je ucinne, ak now spada do [valid_from, valid_to] (null = bez hranice)."""
    return (
        (Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        & (Q(valid_to__isnull=True) | Q(valid_to__gte=now))
    )


def _rule_matches_user_q(user):
    """Q nad DocumentVisibilityRule: pravidlo sa vztahuje na tohto pouzivatela."""
    match = Q(rule_type=DocumentVisibilityRule.RULE_ALL)
    match |= Q(rule_type=DocumentVisibilityRule.RULE_USER_EXPLICIT, user=user)
    if user.business_unit_id is not None:
        match |= Q(
            rule_type=DocumentVisibilityRule.RULE_BUSINESS_UNIT,
            business_unit_id=user.business_unit_id,
        )
    if user.profession_code_id is not None:
        match |= Q(
            rule_type=DocumentVisibilityRule.RULE_PROFESSION_CATEGORY,
            profession_category_id=user.profession_code_id,
        )
    if user.business_unit_id is not None and user.profession_code_id is not None:
        match |= Q(
            rule_type=DocumentVisibilityRule.RULE_BOTH,
            business_unit_id=user.business_unit_id,
            profession_category_id=user.profession_code_id,
        )
    return match


def get_visible_documents(user):
    """Aktivne dokumenty, ktore ma dany pouzivatel vidiet (jeden SQL dotaz)."""
    now = timezone.now()

    base_bu = Q(required_bu__isnull=True)
    if user.business_unit_id is not None:
        base_bu |= Q(required_bu_id=user.business_unit_id)
    base_pc = Q(required_pc__isnull=True)
    if user.profession_code_id is not None:
        base_pc |= Q(required_pc_id=user.profession_code_id)

    effective_rules = DocumentVisibilityRule.objects.filter(
        document=OuterRef('pk')
    ).filter(_time_window_q(now))
    matching_rules = effective_rules.filter(_rule_matches_user_q(user))

    return (
        Document.objects
        .filter(is_active=True)
        .filter(base_bu & base_pc)
        .annotate(
            _has_inclusion_rules=Exists(effective_rules.filter(is_exclusion=False)),
            _matches_inclusion=Exists(matching_rules.filter(is_exclusion=False)),
            _matches_exclusion=Exists(matching_rules.filter(is_exclusion=True)),
        )
        .filter(Q(_has_inclusion_rules=False) | Q(_matches_inclusion=True))
        .filter(_matches_exclusion=False)
    )


def get_unsigned_documents(user):
    """Viditelne dokumenty, ktorych aktualnu verziu pouzivatel este nepodpisal.
    Vylucuje dokumenty, ktorych aktualna verzia este nema stiahnuty subor
    (kiosk nikdy neukaze neotvoritelny dokument)."""
    from signatures.models import Signature

    current_with_file = DocumentVersion.objects.filter(
        document=OuterRef('pk'), is_current=True
    ).exclude(file_path='')
    signed_current = Signature.objects.filter(
        user=user,
        document_version__document=OuterRef('pk'),
        document_version__is_current=True,
    )
    return (
        get_visible_documents(user)
        .annotate(
            _has_file=Exists(current_with_file),
            _signed=Exists(signed_current),
        )
        .filter(_has_file=True, _signed=False)
    )


def get_required_users(document):
    """Aktivni pouzivatelia, ktori maju dany dokument vidiet (pre reporty
    'kto este nepodpisal'). Inverzia get_visible_documents."""
    from users.models import User

    now = timezone.now()
    users = User.objects.filter(is_active=True).order_by('lastname', 'firstname')

    if document.required_bu_id is not None:
        users = users.filter(business_unit_id=document.required_bu_id)
    if document.required_pc_id is not None:
        users = users.filter(profession_code_id=document.required_pc_id)

    rules = list(document.visibility_rules.filter(_time_window_q(now)))
    inclusions = [r for r in rules if not r.is_exclusion]
    exclusions = [r for r in rules if r.is_exclusion]

    if inclusions:
        include_q = Q(pk__in=[])  # vzdy False; ALL pravidlo ho prepne na "vsetci"
        for rule in inclusions:
            rule_q = _user_q_for_rule(rule)
            include_q = Q() if rule_q is None else (include_q | rule_q)
            if rule_q is None:
                break
        users = users.filter(include_q)

    for rule in exclusions:
        rule_q = _user_q_for_rule(rule)
        if rule_q is None:  # exclusion ALL = nikto
            return users.none()
        users = users.exclude(rule_q)

    return users


def _user_q_for_rule(rule):
    """Q nad User: na koho sa pravidlo vztahuje. None = vsetci (RULE_ALL)."""
    if rule.rule_type == DocumentVisibilityRule.RULE_ALL:
        return None
    if rule.rule_type == DocumentVisibilityRule.RULE_BUSINESS_UNIT:
        return Q(business_unit_id=rule.business_unit_id)
    if rule.rule_type == DocumentVisibilityRule.RULE_PROFESSION_CATEGORY:
        return Q(profession_code_id=rule.profession_category_id)
    if rule.rule_type == DocumentVisibilityRule.RULE_BOTH:
        return Q(
            business_unit_id=rule.business_unit_id,
            profession_code_id=rule.profession_category_id,
        )
    if rule.rule_type == DocumentVisibilityRule.RULE_USER_EXPLICIT:
        return Q(pk=rule.user_id)
    return Q(pk__in=[])  # neznamy typ pravidla -> nikto
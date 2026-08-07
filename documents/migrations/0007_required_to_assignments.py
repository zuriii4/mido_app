"""Konverzia historickych poli required_bu/required_pc na DocumentAssignment.

Logika viditelnosti/priradenia uz pouziva tabulku DocumentAssignment
(viazanu na aktualnu verziu dokumentu). Tato migracia pre dokumenty,
ktore maju nastavene required_bu/required_pc, vytvori ekvivalentne
priradenie na ich aktualnu verziu.
"""
from django.db import migrations


def create_assignments_from_required(apps, schema_editor):
    Document = apps.get_model('documents', 'Document')
    DocumentVersion = apps.get_model('documents', 'DocumentVersion')
    DocumentAssignment = apps.get_model('documents', 'DocumentAssignment')

    docs = Document.objects.exclude(required_bu=None, required_pc=None)
    for doc in docs:
        version = DocumentVersion.objects.filter(
            document=doc, is_current=True).first()
        if version is None:
            continue

        if doc.required_bu_id and doc.required_pc_id:
            target_type = 'BOTH'
        elif doc.required_bu_id:
            target_type = 'BUSINESS_UNIT'
        else:
            target_type = 'PROFESSION_CATEGORY'

        assignment = DocumentAssignment.objects.create(
            document_version=version,
            target_type=target_type,
        )
        if doc.required_bu_id:
            assignment.business_units.add(doc.required_bu_id)
        if doc.required_pc_id:
            assignment.profession_categories.add(doc.required_pc_id)


def noop(apps, schema_editor):
    # Vytvorene priradenia nemozno spolahlivo odlisit od rucne vytvorenych.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0006_documentassignment'),
    ]

    operations = [
        migrations.RunPython(create_assignments_from_required, noop),
    ]

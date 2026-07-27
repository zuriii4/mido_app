"""Vycisti dev dokumenty pred prechodom na identitu podla Cisla dokumentu.

Stara schema kluccovala Document podla sharepoint_id; nova podla document_number
(acColCisloDokumentu), ktore sme predtym vobec neukladali. Preto sa existujuce
(dev) zaznamy nedaju spolahlivo migrovat - zmazu sa a nasledny sync ich natiahne
znovu spravne. Bezpecne: v tomto stave neexistuju ziadne podpisy (Signature).
"""
from django.db import migrations


def clear_documents(apps, schema_editor):
    Attachment = apps.get_model('documents', 'Attachment')
    DocumentVersion = apps.get_model('documents', 'DocumentVersion')
    Document = apps.get_model('documents', 'Document')
    Attachment.objects.all().delete()
    DocumentVersion.objects.all().delete()
    Document.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_attachment_converted_to_pdf'),
    ]

    operations = [
        migrations.RunPython(clear_documents, migrations.RunPython.noop),
    ]

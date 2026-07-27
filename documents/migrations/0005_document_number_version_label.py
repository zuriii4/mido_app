"""Prechod na identitu dokumentu podla Cisla dokumentu + verzia podla acColVerzia.

Document: sharepoint_id/etag (per-list-item) presunute na uroven verzie; pribuda
document_number (unikatna identita). DocumentVersion: version_number -> version_label,
sp_version_label -> sp_ui_version, pribuda sharepoint_id (per polozka), title,
effective_date. Tabulky su po migracii 0004 prazdne, takze zmeny su bezpecne.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0004_clear_documents_for_reidentity'),
    ]

    operations = [
        # --- DocumentVersion: najprv uvolnit stare unique_together (referuje version_number) ---
        migrations.AlterUniqueTogether(
            name='documentversion',
            unique_together=set(),
        ),
        migrations.RemoveField(model_name='documentversion', name='version_number'),
        migrations.RemoveField(model_name='documentversion', name='sp_version_label'),
        migrations.AddField(
            model_name='documentversion',
            name='version_label',
            field=models.CharField(default='-', max_length=10),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='sp_ui_version',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='title',
            field=models.CharField(blank=True, default='', max_length=250),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='sharepoint_id',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='documentversion',
            name='effective_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name='documentversion',
            options={'ordering': ['version_label']},
        ),
        migrations.AlterUniqueTogether(
            name='documentversion',
            unique_together={('document', 'version_label')},
        ),
        # --- Document: presun identity na document_number ---
        migrations.RemoveField(model_name='document', name='sharepoint_id'),
        migrations.RemoveField(model_name='document', name='etag'),
        migrations.AddField(
            model_name='document',
            name='document_number',
            field=models.CharField(db_index=True, default='', max_length=100, unique=True),
            preserve_default=False,
        ),
    ]

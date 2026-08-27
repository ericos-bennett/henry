from django.db import migrations, models
import django.db.models.deletion


def flush_companies_and_jobs(apps, schema_editor):
    """The Company primary key is changing from a name-slug string to an
    auto-incrementing integer, so existing rows can't be carried across. Job
    postings are dropped too: their job_key embeds the old string company id and
    their company FK can't be remapped, so keeping them would corrupt the
    reappearance/lifetime tracking in save_job_postings(). Both tables re-seed on
    the next scrape.
    """
    apps.get_model("app", "JobPosting").objects.all().delete()
    apps.get_model("app", "Company").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_remove_jobposting_source_url"),
    ]

    operations = [
        migrations.RunPython(flush_companies_and_jobs, migrations.RunPython.noop),
        migrations.RemoveIndex(model_name="jobposting", name="jp_company_latest_idx"),
        migrations.RemoveIndex(model_name="jobposting", name="jp_company_jobkey_idx"),
        migrations.RemoveField(model_name="jobposting", name="source_company"),
        # The old string PK left a `varchar_pattern_ops` LIKE index on
        # app_company.id (named from the table's original `app_site` name, before
        # the 0002 rename). Postgres won't retype the column to bigint while that
        # index depends on it, and Django doesn't recognize the stale name to drop
        # it automatically — so drop it explicitly first.
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS "app_site_id_76ba7ff9_like";',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="company",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
        migrations.AddField(
            model_name="jobposting",
            name="company",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="job_postings",
                to="app.company",
            ),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="jobposting",
            index=models.Index(
                fields=["company", "latest_scrape_timestamp"], name="jp_company_latest_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="jobposting",
            index=models.Index(
                fields=["company", "job_key"], name="jp_company_jobkey_idx"
            ),
        ),
    ]

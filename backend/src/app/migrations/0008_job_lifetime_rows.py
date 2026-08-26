import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_remove_jobposting_salary_raw"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="jobposting",
            name="unique_job_per_run",
        ),
        migrations.RemoveIndex(
            model_name="jobposting",
            name="app_jobpost_source__60dec2_idx",
        ),
        migrations.RemoveField(
            model_name="jobposting",
            name="is_new",
        ),
        migrations.RemoveField(
            model_name="jobposting",
            name="scraped_at",
        ),
        migrations.AddField(
            model_name="jobposting",
            name="job_key",
            field=models.CharField(db_index=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="jobposting",
            name="first_scrape_timestamp",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="jobposting",
            name="latest_scrape_timestamp",
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name="jobposting",
            name="job_id",
        ),
        migrations.AddIndex(
            model_name="jobposting",
            index=models.Index(
                fields=["source_company", "latest_scrape_timestamp"],
                name="jp_company_latest_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobposting",
            index=models.Index(
                fields=["source_company", "job_key"],
                name="jp_company_jobkey_idx",
            ),
        ),
    ]

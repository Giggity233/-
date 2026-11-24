from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import migrations


def calculated_timeout_count(consultation_count, three_minute_reply_rate):
    try:
        total = max(Decimal(str(consultation_count or 0)), Decimal("0"))
        reply_rate = Decimal(str(three_minute_reply_rate))
    except (InvalidOperation, TypeError, ValueError):
        return None
    reply_rate = min(max(reply_rate, Decimal("0")), Decimal("100"))
    return int(
        (total * (Decimal("100") - reply_rate) / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def backfill_pdd_timeout_counts(apps, schema_editor):
    StoreMetric = apps.get_model("core", "StoreMetric")
    for metric in StoreMetric.objects.filter(store__platform="pdd").iterator():
        timeout_count = calculated_timeout_count(
            metric.consultation_count, metric.three_minute_reply_rate
        )
        StoreMetric.objects.filter(pk=metric.pk).update(
            timeout_count=timeout_count,
            robot_timeout_count=timeout_count,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_specialist_shift_summary_labels"),
    ]

    operations = [
        migrations.RunPython(backfill_pdd_timeout_counts, migrations.RunPython.noop),
    ]

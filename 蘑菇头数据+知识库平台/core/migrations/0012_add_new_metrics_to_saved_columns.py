from django.db import migrations


NEW_METRIC_COLUMNS = [
    "specialist_reply_count",
    "robot_timeout_count",
    "robot_three_minute_reply_rate",
]


def add_new_columns_to_saved_preferences(apps, schema_editor):
    user_model = apps.get_model("core", "User")
    for user in user_model.objects.exclude(store_data_visible_fields__isnull=True).iterator():
        columns = list(user.store_data_visible_fields or [])
        for column in NEW_METRIC_COLUMNS:
            if column not in columns:
                columns.append(column)
        user.store_data_visible_fields = columns
        user.save(update_fields=["store_data_visible_fields"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_specialist_and_robot_metrics"),
    ]

    operations = [
        migrations.RunPython(add_new_columns_to_saved_preferences, migrations.RunPython.noop),
    ]

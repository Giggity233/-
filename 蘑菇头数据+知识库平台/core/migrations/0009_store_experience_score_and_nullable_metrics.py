from django.core.validators import MinValueValidator
from django.db import migrations, models


METRIC_FIELD_OPTIONS = {
    "consultation_count": (models.PositiveIntegerField, {}),
    "three_minute_reply_rate": (models.DecimalField, {"max_digits": 6, "decimal_places": 2}),
    "timeout_count": (models.PositiveIntegerField, {}),
    "average_response_seconds": (models.DecimalField, {"max_digits": 10, "decimal_places": 2}),
    "pending_after_sales": (models.PositiveIntegerField, {}),
    "pending_tickets": (models.PositiveIntegerField, {}),
    "today_order_count": (models.PositiveIntegerField, {}),
    "today_turnover": (models.DecimalField, {"max_digits": 14, "decimal_places": 2}),
    "today_ad_spend": (models.DecimalField, {"max_digits": 14, "decimal_places": 2}),
    "robot_completed_reply_count": (models.PositiveIntegerField, {}),
    "robot_completed_reply_rate": (models.DecimalField, {"max_digits": 6, "decimal_places": 2}),
    "robot_transferred_count": (models.PositiveIntegerField, {}),
}

METRIC_LABELS = {
    "consultation_count": "咨询数",
    "three_minute_reply_rate": "3分钟回复率",
    "timeout_count": "超时数量",
    "average_response_seconds": "平均响应速度（秒）",
    "pending_after_sales": "待处理售后数量",
    "pending_tickets": "待处理工单数量",
    "today_order_count": "今日订单数",
    "today_turnover": "今日营业金额",
    "today_ad_spend": "今日广告金额",
    "robot_completed_reply_count": "机器人完结回复数量",
    "robot_completed_reply_rate": "机器人完结回复率",
    "robot_transferred_count": "机器人转出数量",
}


def nullable_metric_field(name, label, with_validator=False):
    field_class, options = METRIC_FIELD_OPTIONS[name]
    options = {**options, "verbose_name": label, "default": 0, "null": True, "blank": True}
    if with_validator and name == "three_minute_reply_rate":
        options["validators"] = [MinValueValidator(0)]
    return field_class(**options)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_storeaccount_corresponding_port"),
    ]

    operations = [
        migrations.RemoveField(model_name="shiftdailysummary", name="today_refund"),
        migrations.RemoveField(model_name="storemetric", name="today_refund"),
        migrations.RemoveField(model_name="storemetricsnapshot", name="today_refund"),
        migrations.AddField(
            model_name="shiftdailysummary",
            name="store_experience_score",
            field=models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="storemetric",
            name="store_experience_score",
            field=models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="storemetricsnapshot",
            name="store_experience_score",
            field=models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="store_data_visible_fields",
            field=models.JSONField("店铺数据中心可见字段", null=True, blank=True, default=None),
        ),
        *[
            migrations.AlterField(
                model_name="shiftdailysummary",
                name=name,
                field=nullable_metric_field(name, "回复数量" if name == "consultation_count" else METRIC_LABELS[name]),
            )
            for name in METRIC_FIELD_OPTIONS
        ],
        *[
            migrations.AlterField(
                model_name="storemetric",
                name=name,
                field=nullable_metric_field(name, METRIC_LABELS[name], with_validator=True),
            )
            for name in METRIC_FIELD_OPTIONS
        ],
        *[
            migrations.AlterField(
                model_name="storemetricsnapshot",
                name=name,
                field=nullable_metric_field(name, METRIC_LABELS[name]),
            )
            for name in METRIC_FIELD_OPTIONS
        ],
    ]

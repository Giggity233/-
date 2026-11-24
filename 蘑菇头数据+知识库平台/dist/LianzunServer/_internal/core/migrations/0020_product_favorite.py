from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0019_backfill_specialist_account_ids_from_cookies"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductFavorite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")),
                ("product", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="favorite_records", to="core.product", verbose_name="收藏商品")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="product_favorites", to=settings.AUTH_USER_MODEL, verbose_name="收藏账号")),
            ],
            options={
                "verbose_name": "商品收藏",
                "verbose_name_plural": "商品收藏",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="productfavorite",
            constraint=models.UniqueConstraint(fields=("user", "product"), name="unique_user_product_favorite"),
        ),
    ]

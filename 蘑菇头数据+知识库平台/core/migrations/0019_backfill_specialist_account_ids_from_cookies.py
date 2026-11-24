import re
from urllib.parse import unquote

from django.db import migrations


def cookie_value(cookie, name):
    match = re.search(
        rf"(?:^|;\s*){re.escape(name)}\s*=\s*([^;]*)",
        str(cookie or ""),
        flags=re.IGNORECASE,
    )
    return unquote(match.group(1).strip().strip('"')) if match else ""


def backfill_specialist_account_ids(apps, schema_editor):
    Store = apps.get_model("core", "Store")
    StoreAccount = apps.get_model("core", "StoreAccount")

    for store in Store.objects.filter(platform__in=("pdd", "douyin")).exclude(cookie="").iterator():
        accounts = StoreAccount.objects.filter(
            store_id=store.pk, account_type="human", external_id=""
        )
        if accounts.count() != 1:
            continue
        account = accounts.first()
        if store.platform == "pdd":
            match = re.search(r"_(\d+)$", cookie_value(store.cookie, "PASS_ID"))
            account_id = match.group(1) if match else ""
        else:
            account_id = cookie_value(store.cookie, "PIGEON_CID")
            if not re.fullmatch(r"\d+", account_id):
                account_id = ""
        if account_id:
            StoreAccount.objects.filter(pk=account.pk, external_id="").update(external_id=account_id)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_ai_keyword_answer"),
    ]

    operations = [
        migrations.RunPython(backfill_specialist_account_ids, migrations.RunPython.noop),
    ]

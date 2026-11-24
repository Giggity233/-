from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from .models import (
    AccountPasswordRegistration,
    AIKnowledgeKeyword,
    AIKnowledgeKeywordBlock,
    AIKnowledgePrompt,
    AIKnowledgePromptBlock,
    AIKnowledgeQA,
    AIKnowledgeQABlock,
    Customer,
    CustomerMaterial,
    ImageTextRegistration,
    InvoiceRecord,
    MessageTask,
    OrderUrgingScript,
    PendingTask,
    Product,
    ProductFavorite,
    ProductMaterialInheritanceBlock,
    QuickReply,
    RemoteRegistration,
    ShiftDailySummary,
    Store,
    StoreAccount,
    StoreAfterSalesStrategy,
    StoreMetric,
    StoreMetricSnapshot,
    StoreShiftClaim,
    User,
    WeChatPendingGroup,
)


class PlatformFlowTests(TestCase):
    def setUp(self):
        self.headers = {}
        self.manager = User.objects.create_user(username="manager", password="strong-pass-123", responsible_name="王主管")
        permission = Permission.objects.get(content_type__app_label="core", codename="can_manage_clients")
        self.manager.user_permissions.add(permission)
        self.customer = Customer.objects.create(name="华东客户")

    def test_cookie_metrics_account_and_claim_flow(self):
        response = self.client.post(reverse("api_cookie_upsert"), data={
            "platform": "拼多多", "shop_id": "pdd-001", "shop_name": "蘑菇头旗舰店", "cookie": "cookie-value", "customer": "华东客户"
        }, content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 201)
        store = Store.objects.get(external_id="pdd-001")
        self.assertEqual(store.main_category, "notfind")
        self.assertIsNone(store.customer)
        response = self.client.post(reverse("api_cookie_upsert"), data={"shop_id": "pdd-001", "cookie": "new-cookie-value"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        store.refresh_from_db()
        self.assertEqual(store.cookie, "new-cookie-value")

        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": "pdd-001", "platform": "pdd", "time": 10, "specialist_reply_count": 44,
            "specialist_three_minute_reply_rate": "98.50", "specialist_timeout_count": 2, "today_turnover": "1234.56"
        }, content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StoreMetric.objects.get(store=store).consultation_count, 44)
        response = self.client.post(reverse("api_robot_metrics_upsert"), data={
            "shop_id": "pdd-001", "platform": "pdd", "time": 10, "robot_completed_reply_count": 12,
        }, content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StoreMetric.objects.get(store=store).consultation_count, 56)
        self.assertTrue(StoreMetricSnapshot.objects.filter(store=store, report_hour=10, robot_completed_reply_count=12).exists())

        StoreAccount.objects.create(store=store, name="客服A", login_account="a", login_password="secret", corresponding_port="19001", account_type="human")
        response = self.client.post(reverse("api_account_id_upsert"), data={"account_name": "客服A", "account_id": "acc-11", "shop_id": "pdd-001"}, content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("api_cookies"), {"platform": "pdd"}, **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["cookie"], "new-cookie-value")
        human_account = response.json()["data"][0]["human_accounts"][0]
        self.assertEqual(human_account["account_id"], "acc-11")
        self.assertEqual(human_account["account_type"], "human")
        self.assertEqual(human_account["account_type_name"], "专员账号")
        self.assertEqual(human_account["login_account"], "a")
        self.assertEqual(human_account["login_password"], "secret")
        bot_account = StoreAccount.objects.create(
            store=store, name="机器人A", login_account="bot-a", login_password="bot-secret", account_type="bot"
        )
        response = self.client.get(reverse("api_cookies"), {"platform": "pdd"}, **self.headers)
        self.assertEqual(response.status_code, 200)
        returned_bot_account = response.json()["data"][0]["bot_accounts"][0]
        self.assertEqual(returned_bot_account["account_name"], bot_account.name)
        self.assertEqual(returned_bot_account["account_type"], "bot")
        self.assertEqual(returned_bot_account["login_account"], "bot-a")
        self.assertEqual(returned_bot_account["login_password"], "bot-secret")

        claimant = User.objects.create_user(username="operator", password="strong-pass-123", responsible_name="李专员")
        self.client.force_login(claimant)
        response = self.client.post(reverse("claim_store_shift", args=[store.pk, "morning"]), {"customer_id": self.customer.pk})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StoreShiftClaim.objects.filter(store=store, shift="morning", user=claimant).exists())
        store.refresh_from_db()
        self.assertEqual(store.customer, self.customer)
        response = self.client.post(reverse("api_shift_daily_summary_upsert"), data={"shop_id": "pdd-001", "shift": "morning", "year": 2026, "month": 9, "day": 15, "specialist_reply_count": 56, "specialist_timeout_count": 2}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ShiftDailySummary.objects.filter(store=store, user=claimant, summary_date="2026-09-15").exists())
        response = self.client.get(reverse("api_morning_baseline"), {"id": "pdd-001"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["specialist_reply_count"], 56)
        response = self.client.get(reverse("api_account_stores"), {"account_name": "operator"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["responsible_slots"], ["负责人 1"])
        account = StoreAccount.objects.get(store=store, name="客服A")
        response = self.client.post(reverse("account_edit", args=[account.pk]), {
            "store": store.pk, "name": "客服A", "login_account": "a", "login_password": "updated-secret",
            "corresponding_port": "19002", "phone": "", "account_type": "human", "external_id": "manually-edited-id",
        })
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.login_password, "updated-secret")
        self.assertEqual(account.corresponding_port, "19002")
        self.assertEqual(account.external_id, "manually-edited-id")
        claimant.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename="can_view_customer_performance"))
        response = self.client.get(reverse("customer_performance"), {"date": "2026-09-15"})
        self.assertContains(response, "56")

    def test_jingdong_platform_is_available_to_cookie_metrics_and_product_apis(self):
        response = self.client.post(
            reverse("api_cookie_upsert"),
            data={
                "platform": "京东",
                "shop_id": "jd-001",
                "shop_name": "京东测试店",
                "cookie": "jd-cookie",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        store = Store.objects.get(external_id="jd-001")
        self.assertEqual(store.platform, "jingdong")
        self.assertEqual(store.get_platform_display(), "京东")

        response = self.client.get(reverse("api_cookies"), {"platform": "jingdong"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["platform"], "jingdong")

        response = self.client.post(
            reverse("api_store_metrics_upsert"),
            data={
                "platform": "jingdong",
                "shop_id": store.external_id,
                "time": 10,
                "specialist_reply_count": 5,
                "specialist_timeout_count": 2,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StoreMetric.objects.get(store=store).timeout_count, 2)

        response = self.client.post(
            reverse("api_ai_product_upsert"),
            data={
                "platform": "jingdong",
                "zl": {
                    "shopSN": store.external_id,
                    "goods_id": "jd-goods-001",
                    "goods_name": "京东商品",
                },
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse("api_ai_product_get"),
            {"platform": "京东", "shopid": store.external_id, "goods_id": "jd-goods-001"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["platform"], "jingdong")

    def test_robot_cookie_endpoints_use_separate_storage_with_legacy_shape(self):
        store = Store.objects.create(
            platform="pdd",
            external_id="robot-cookie-store",
            name="机器人 Cookie 店铺",
            cookie="human-cookie",
        )

        response = self.client.post(
            reverse("api_robot_cookie_upsert"),
            data={"shop_id": store.external_id, "cookie": "robot-cookie"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["created"])
        self.assertIn("cookie_updated_at", response.json()["data"])
        self.assertNotIn("cookie", response.json()["data"])

        store.refresh_from_db()
        self.assertEqual(store.cookie, "human-cookie")
        self.assertEqual(store.robot_cookie, "robot-cookie")

        response = self.client.get(reverse("api_robot_cookies"), {"platform": "pdd"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["data"][0]["cookie"], "robot-cookie")

        response = self.client.post(
            reverse("api_robot_cookie_upsert"),
            data={
                "platform": "douyin",
                "shop_id": "new-robot-cookie-store",
                "shop_name": "新机器人 Cookie 店铺",
                "cookie": "new-robot-cookie",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        created_store = Store.objects.get(external_id="new-robot-cookie-store")
        self.assertEqual(created_store.cookie, "")
        self.assertEqual(created_store.robot_cookie, "new-robot-cookie")

    def test_customer_deletion_cascades_store_data(self):
        store = Store.objects.create(platform="pdd", external_id="pdd-002", name="待删除店铺", customer=self.customer)
        StoreAccount.objects.create(store=store, name="客服B", login_account="b", login_password="x", account_type="bot")
        StoreShiftClaim.objects.create(store=store, shift="morning", user=self.manager, customer=self.customer)
        self.client.force_login(self.manager)
        response = self.client.post(reverse("customer_delete", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Store.objects.filter(pk=store.pk).exists())
        self.assertFalse(StoreAccount.objects.filter(name="客服B").exists())

    def test_api_without_key_and_invalidate_does_not_cross_platform(self):
        self.assertEqual(self.client.get(reverse("api_customers")).status_code, 200)
        Store.objects.create(platform="pdd", external_id="same-id", name="P店")
        douyin = Store.objects.create(platform="douyin", external_id="same-id", name="抖店")
        response = self.client.post(reverse("api_cookie_invalidate"), data={"shop_id": "same-id"}, content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 409)
        douyin.refresh_from_db()
        self.assertEqual(douyin.cookie_status, "valid")

    def test_management_pages_render_for_superuser(self):
        admin = User.objects.create_superuser(username="admin", password="strong-pass-123", responsible_name="平台主管")
        store = Store.objects.create(platform="pdd", external_id="pdd-003", name="页面验收店", customer=self.customer)
        StoreMetric.objects.create(store=store, consultation_count=5)
        self.client.force_login(admin)
        for name in ["dashboard", "customer_list", "cookie_center", "unowned_store_center", "store_data_center", "customer_performance", "monthly_replies", "account_center", "account_password_center", "permission_center"]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_only_admin_can_delete_an_unowned_store(self):
        store = Store.objects.create(platform="pdd", external_id="unowned-delete", name="待删除无主店")
        admin = User.objects.create_superuser(username="delete-admin", password="strong-pass-123", responsible_name="删除管理员")
        self.client.force_login(admin)
        response = self.client.get(reverse("unowned_store_center"))
        self.assertContains(response, "删除店铺")
        response = self.client.post(reverse("unowned_store_delete", args=[store.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Store.objects.filter(pk=store.pk).exists())

        regular_user = User.objects.create_user(username="regular-delete", password="strong-pass-123", responsible_name="普通用户")
        another_store = Store.objects.create(platform="douyin", external_id="unowned-keep", name="保留无主店")
        self.client.force_login(regular_user)
        response = self.client.post(reverse("unowned_store_delete", args=[another_store.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Store.objects.filter(pk=another_store.pk).exists())

    def test_pending_tasks_are_limited_to_the_responsible_user_and_can_be_completed(self):
        owner = User.objects.create_user(username="task-owner", password="strong-pass-123", responsible_name="待办负责人")
        other_owner = User.objects.create_user(username="other-owner", password="strong-pass-123", responsible_name="另一负责人")
        store = Store.objects.create(platform="pdd", external_id="todo-001", name="待办店铺", customer=self.customer)
        other_store = Store.objects.create(platform="douyin", external_id="todo-002", name="另一待办店铺", customer=self.customer)
        StoreShiftClaim.objects.create(store=store, shift="morning", user=owner, customer=self.customer)
        StoreShiftClaim.objects.create(store=other_store, shift="morning", user=other_owner, customer=self.customer)

        response = self.client.post(
            reverse("api_pending_task_create"),
            data={"shop_id": "todo-001", "time_type": "urgent", "handling_item": "尽快联系客户处理退款"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["data"]["is_urgent"])
        self.assertEqual(response.json()["data"]["shop_name"], "待办店铺")
        second_task = PendingTask.objects.create(store=other_store, time_type="normal", handling_item="检查发货信息")

        self.client.force_login(owner)
        response = self.client.get(reverse("api_pending_tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        task = PendingTask.objects.get(store=store)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "尽快联系客户处理退款")
        self.assertContains(response, "标记已处理")
        self.assertEqual(self.client.post(reverse("pending_task_complete", args=[task.pk])).status_code, 302)
        task.refresh_from_db()
        self.assertTrue(task.is_processed)
        self.assertEqual(task.processed_by, owner)

        self.client.force_login(other_owner)
        response = self.client.get(reverse("api_pending_tasks"))
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["data"][0]["id"], second_task.pk)

        admin = User.objects.create_user(username="task-admin", password="strong-pass-123", responsible_name="待办管理员", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("api_pending_tasks"))
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["data"][0]["id"], second_task.pk)

    def test_missing_page_uses_friendly_random_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "这个还没有喵~", status_code=404)

    def test_releasing_my_claim_returns_store_to_unowned(self):
        operator = User.objects.create_user(username="releaser", password="strong-pass-123", responsible_name="陈专员")
        store = Store.objects.create(platform="douyin", external_id="dy-release", name="可释放店", customer=self.customer, responsible=operator)
        StoreShiftClaim.objects.create(store=store, shift="morning", user=operator, customer=self.customer)
        self.client.force_login(operator)
        response = self.client.post(reverse("release_store_responsibility", args=[store.pk]))
        self.assertEqual(response.status_code, 302)
        store.refresh_from_db()
        self.assertFalse(StoreShiftClaim.objects.filter(store=store).exists())
        self.assertIsNone(store.customer)
        self.assertIsNone(store.responsible)

    def test_accounts_survive_responsibility_release_and_are_reused_by_next_owner(self):
        original_owner = User.objects.create_user(username="original-owner", password="strong-pass-123", responsible_name="原负责人")
        next_owner = User.objects.create_user(username="next-owner", password="strong-pass-123", responsible_name="新负责人")
        admin = User.objects.create_superuser(username="account-auditor", password="strong-pass-123", responsible_name="账号管理员")
        store = Store.objects.create(platform="pdd", external_id="retain-account-store", name="账号保留店", customer=self.customer, responsible=original_owner)
        StoreShiftClaim.objects.create(store=store, shift="morning", user=original_owner, customer=self.customer)
        account = StoreAccount.objects.create(
            store=store, name="保留专员", login_account="retain-specialist",
            login_password="retained-password", account_type="human", external_id="retained-id",
        )

        self.client.force_login(original_owner)
        self.assertEqual(self.client.post(reverse("release_store_responsibility", args=[store.pk])).status_code, 302)
        account.refresh_from_db()
        self.assertEqual(account.external_id, "retained-id")
        self.assertTrue(StoreAccount.objects.filter(pk=account.pk).exists())

        self.client.force_login(next_owner)
        self.assertEqual(
            self.client.post(
                reverse("claim_store_shift", args=[store.pk, "morning"]),
                {"customer_id": self.customer.pk},
            ).status_code,
            302,
        )
        self.assertContains(self.client.get(reverse("account_center")), "retain-specialist")

        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse("account_password_center")), "retained-password")

    def test_specialist_id_is_automatically_captured_from_pdd_and_douyin_cookies(self):
        pdd_store = Store.objects.create(platform="pdd", external_id="pdd-account-id", name="拼多多账号店")
        douyin_store = Store.objects.create(platform="douyin", external_id="douyin-account-id", name="抖音账号店")
        pdd_account = StoreAccount.objects.create(
            store=pdd_store, name="拼多多专员", login_account="pdd-specialist",
            login_password="secret", account_type="human",
        )
        douyin_account = StoreAccount.objects.create(
            store=douyin_store, name="抖音专员", login_account="douyin-specialist",
            login_password="secret", account_type="human",
        )

        pdd_cookie = "a=1; PASS_ID=1-sYStl70Qmziuz7Yg0g1eFxZfVA9TDmCT4sPea3ryfhWbzVLwnSjsI3IE8nEX30Fqtle9QFq6lfpf2HI3jZ9r5A_735291215_156012866; b=2"
        response = self.client.post(
            reverse("api_cookie_upsert"),
            data={"shop_id": pdd_store.external_id, "cookie": pdd_cookie},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["captured_account_id"], "156012866")
        pdd_account.refresh_from_db()
        self.assertEqual(pdd_account.external_id, "156012866")

        response = self.client.post(
            reverse("api_account_id_upsert"),
            data={
                "shop_id": pdd_store.external_id,
                "account_name": "pdd-specialist",
                "cookie": "PASS_ID=1-new-value_735291215_999999999",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["skipped"])
        pdd_account.refresh_from_db()
        self.assertEqual(pdd_account.external_id, "156012866")

        response = self.client.post(
            reverse("api_account_id_upsert"),
            data={
                "shop_id": douyin_store.external_id,
                "account_name": "douyin-specialist",
                "cookie": "PIGEON_CID=7401371213337026099; passport_csrf_token=example",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["account_id"], "7401371213337026099")
        douyin_account.refresh_from_db()
        self.assertEqual(douyin_account.external_id, "7401371213337026099")

    def test_account_center_backfills_a_historical_blank_specialist_id_from_saved_cookie(self):
        owner = User.objects.create_user(username="historical-id-owner", password="strong-pass-123", responsible_name="历史账号负责人")
        store = Store.objects.create(
            platform="pdd", external_id="historical-id-store", name="历史 ID 店",
            customer=self.customer,
            cookie="a=1; PASS_ID=1-saved-cookie_735291215_123456789; b=2",
        )
        StoreShiftClaim.objects.create(store=store, shift="morning", user=owner, customer=self.customer)
        account = StoreAccount.objects.create(
            store=store, name="历史专员", login_account="historical-specialist",
            login_password="secret", account_type="human",
        )

        self.client.force_login(owner)
        response = self.client.get(reverse("account_center"))
        self.assertContains(response, "自动补齐 1 个专员账号 ID")
        account.refresh_from_db()
        self.assertEqual(account.external_id, "123456789")

    def test_store_metrics_accept_none_and_show_nan_with_experience_score(self):
        store = Store.objects.create(platform="pdd", external_id="none-metric", name="空值指标店", customer=self.customer)
        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 9,
            "specialist_reply_count": None,
            "today_turnover": None,
            "store_experience_score": "4.82",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric = StoreMetric.objects.get(store=store)
        self.assertEqual(metric.consultation_count, 0)
        self.assertIsNone(metric.specialist_reply_count)
        self.assertIsNone(metric.today_turnover)
        self.assertEqual(str(metric.store_experience_score), "4.82")
        snapshot = StoreMetricSnapshot.objects.get(store=store, report_hour=9)
        self.assertEqual(snapshot.consultation_count, 0)

        admin = User.objects.create_superuser(username="nan-admin", password="strong-pass-123", responsible_name="数据主管")
        self.client.force_login(admin)
        response = self.client.get(reverse("store_data_center"))
        self.assertContains(response, "店铺体验分")
        self.assertContains(response, "NaN")

    def test_store_metrics_accept_text_and_service_experience_score(self):
        store = Store.objects.create(platform="pdd", external_id="text-metric", name="文字指标店", customer=self.customer)
        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 10,
            "specialist_reply_count": "无权限",
            "specialist_yesterday_average_response_seconds": "接口维护中",
            "store_experience_score": "4.82",
            "service_experience_score": "4.70",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric = StoreMetric.objects.get(store=store)
        self.assertEqual(metric.consultation_count, 0)
        self.assertEqual(metric.metric_display_values["specialist_reply_count"], "无权限")
        self.assertEqual(metric.metric_display_values["average_response_seconds"], "接口维护中")
        self.assertEqual(str(metric.service_experience_score), "4.70")
        snapshot = StoreMetricSnapshot.objects.get(store=store, report_hour=10)
        self.assertEqual(snapshot.metric_display_values["specialist_reply_count"], "无权限")

        admin = User.objects.create_superuser(username="text-admin", password="strong-pass-123", responsible_name="数据主管")
        self.client.force_login(admin)
        response = self.client.get(reverse("store_data_center"))
        self.assertContains(response, "无权限")
        self.assertContains(response, "平均响应")
        self.assertContains(response, "服务体验分")

    def test_robot_metrics_are_independent_and_text_status_counts_as_zero(self):
        store = Store.objects.create(platform="pdd", external_id="robot-metric", name="机器人指标店", customer=self.customer)
        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id, "platform": "pdd", "time": 11, "specialist_reply_count": 7,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("api_robot_metrics_upsert"), data={
            "shop_id": store.external_id, "platform": "pdd", "time": 11,
            "robot_completed_reply_count": "接口维护中", "robot_timeout_count": 3,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric = StoreMetric.objects.get(store=store)
        self.assertEqual(metric.consultation_count, 7)
        self.assertIsNone(metric.robot_completed_reply_count)
        self.assertEqual(metric.metric_display_values["robot_completed_reply_count"], "接口维护中")
        self.assertEqual(metric.robot_timeout_count, 7)

        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id, "platform": "pdd", "time": 11, "robot_completed_reply_count": 9,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("robot-metrics", response.json()["message"])

    def test_pdd_real_time_reply_data_maps_to_specialist_metrics(self):
        store = Store.objects.create(platform="pdd", external_id="pdd-realtime", name="拼多多实时回复店", customer=self.customer)
        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 12,
            "success": True,
            "result": {"recv_user": 59, "reply_rate": 1.0},
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric = StoreMetric.objects.get(store=store)
        self.assertEqual(metric.specialist_reply_count, 59)
        self.assertEqual(metric.consultation_count, 59)
        self.assertEqual(str(metric.three_minute_reply_rate), "100.00")

        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 13,
            "specialist_reply_count": 60,
            "specialist_three_minute_reply_rate": "0.985",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric.refresh_from_db()
        self.assertEqual(str(metric.three_minute_reply_rate), "98.50")

    def test_store_data_center_paginates_fifty_rows_and_uses_new_column_labels(self):
        for index in range(55):
            store = Store.objects.create(platform="pdd", external_id=f"page-{index}", name=f"分页店铺{index}")
            StoreMetric.objects.create(store=store, specialist_reply_count=index, consultation_count=index)
        admin = User.objects.create_superuser(username="page-admin", password="strong-pass-123", responsible_name="分页管理员")
        self.client.force_login(admin)

        first_page = self.client.get(reverse("store_data_center"))
        self.assertEqual(first_page.context["page_obj"].paginator.per_page, 50)
        self.assertEqual(len(first_page.context["stores"]), 50)
        self.assertContains(first_page, "今日售后数量")
        self.assertContains(first_page, "今日工单数量")

        second_page = self.client.get(reverse("store_data_center"), {"page": 2})
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["stores"]), 5)
        self.assertContains(second_page, "第 2 / 2 页")

        json_page = self.client.get(reverse("store_data_api"), {"page": 2})
        self.assertEqual(json_page.status_code, 200)
        payload = json_page.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["pagination"]["count"], 55)
        self.assertEqual(payload["data"]["pagination"]["number"], 2)
        self.assertEqual(len(payload["data"]["rows"]), 5)
        self.assertIn("specialist_reply_count", payload["data"]["rows"][0]["values"])

    def test_store_data_center_sorts_numeric_columns_in_both_directions(self):
        lower_store = Store.objects.create(platform="pdd", external_id="sort-low", name="排序小值店")
        higher_store = Store.objects.create(platform="pdd", external_id="sort-high", name="排序大值店")
        StoreMetric.objects.create(store=lower_store, consultation_count=2, today_turnover="20.00")
        StoreMetric.objects.create(store=higher_store, consultation_count=9, today_turnover="90.00")
        admin = User.objects.create_superuser(username="sort-admin", password="strong-pass-123", responsible_name="排序管理员")
        self.client.force_login(admin)

        ascending = self.client.get(reverse("store_data_center"), {"sort": "consultation_count", "direction": "asc"})
        self.assertEqual([store.pk for store in ascending.context["stores"]], [lower_store.pk, higher_store.pk])
        self.assertContains(ascending, "sort=consultation_count&amp;direction=asc")
        self.assertContains(ascending, "▲")
        self.assertContains(ascending, "▼")

        descending = self.client.get(reverse("store_data_center"), {"sort": "consultation_count", "direction": "desc"})
        self.assertEqual([store.pk for store in descending.context["stores"]], [higher_store.pk, lower_store.pk])

    def test_admin_can_add_accounts_for_any_store(self):
        manager = User.objects.create_superuser(username="account-admin", password="strong-pass-123", responsible_name="账号管理员")
        other_user = User.objects.create_user(username="other-account-owner", password="strong-pass-123", responsible_name="其他负责人")
        own_store = Store.objects.create(platform="pdd", external_id="account-own", name="本人认领店")
        other_store = Store.objects.create(platform="pdd", external_id="account-other", name="他人认领店")
        StoreShiftClaim.objects.create(store=own_store, shift="morning", user=manager, customer=self.customer)
        StoreShiftClaim.objects.create(store=other_store, shift="morning", user=other_user, customer=self.customer)
        self.client.force_login(manager)

        response = self.client.get(reverse("account_center"))
        selectable_store_ids = set(response.context["form"].fields["store"].queryset.values_list("pk", flat=True))
        self.assertEqual(selectable_store_ids, {own_store.pk, other_store.pk})

        response = self.client.post(reverse("account_center"), {
            "store": other_store.pk,
            "name": "管理员新增账号",
            "login_account": "admin-added",
            "login_password": "secret",
            "account_type": "human",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StoreAccount.objects.filter(store=other_store, name="管理员新增账号").exists())

    def test_unowned_store_center_paginates_thirty_five_rows(self):
        for index in range(41):
            Store.objects.create(platform="pdd", external_id=f"unowned-page-{index}", name=f"无主分页店铺{index}")
        admin = User.objects.create_superuser(username="unowned-page-admin", password="strong-pass-123", responsible_name="分页管理员")
        self.client.force_login(admin)

        first_page = self.client.get(reverse("unowned_store_center"))
        self.assertEqual(first_page.context["page_obj"].paginator.per_page, 35)
        self.assertEqual(len(first_page.context["stores"]), 35)
        self.assertContains(first_page, "第 1 / 2 页")

        second_page = self.client.get(reverse("unowned_store_center"), {"page": 2})
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["stores"]), 6)
        json_page = self.client.get(reverse("unowned_store_center_api"), {"page": 2})
        self.assertEqual(json_page.status_code, 200)
        self.assertEqual(len(json_page.json()["data"]["rows"]), 6)

    def test_management_center_json_pages_limit_results_to_thirty_five(self):
        admin = User.objects.create_superuser(username="json-page-admin", password="strong-pass-123", responsible_name="分页管理员")
        for index in range(36):
            store = Store.objects.create(platform="pdd", external_id=f"json-page-{index}", name=f"JSON 分页店铺{index}")
            StoreAccount.objects.create(
                store=store, name=f"客服{index}", login_account=f"json-{index}",
                login_password="secret", account_type="human", created_by=admin,
            )
        self.client.force_login(admin)

        for name in ["cookie_center_api", "account_center_api", "account_password_center_api"]:
            with self.subTest(page=name):
                first_page = self.client.get(reverse(name))
                self.assertEqual(first_page.status_code, 200)
                self.assertEqual(first_page.json()["data"]["pagination"]["count"], 36)
                self.assertEqual(len(first_page.json()["data"]["rows"]), 35)
                second_page = self.client.get(reverse(name), {"page": 2})
                self.assertEqual(len(second_page.json()["data"]["rows"]), 1)

    def test_account_password_center_is_admin_only_and_filters_fuzzily(self):
        owner = User.objects.create_user(username="manager-lee", password="strong-pass-123", responsible_name="李负责人")
        store = Store.objects.create(platform="douyin", external_id="password-store", name="密码测试店", customer=self.customer)
        StoreShiftClaim.objects.create(store=store, shift="morning", user=owner, customer=self.customer)
        StoreAccount.objects.create(store=store, name="客服密码", login_account="login-001", login_password="secret-001", account_type="human")

        self.client.force_login(owner)
        self.assertEqual(self.client.get(reverse("account_password_center")).status_code, 403)

        admin = User.objects.create_superuser(username="password-admin", password="strong-pass-123", responsible_name="平台主管")
        self.client.force_login(admin)
        response = self.client.get(reverse("account_password_center"), {
            "store": "密码测试", "customer": "华东", "responsible": "李负",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "secret-001")
        self.assertContains(response, "账号密码管理中心")

    def test_store_and_monthly_filters_and_admin_can_release_one_responsible(self):
        first_owner = User.objects.create_user(username="first-owner", password="strong-pass-123", responsible_name="负责人甲")
        second_owner = User.objects.create_user(username="second-owner", password="strong-pass-123", responsible_name="负责人乙")
        other_owner = User.objects.create_user(username="other-owner-filter", password="strong-pass-123", responsible_name="负责人丙")
        second_customer = Customer.objects.create(name="华南客户")
        store = Store.objects.create(platform="pdd", external_id="filter-store", name="筛选店铺", customer=self.customer)
        other_store = Store.objects.create(platform="douyin", external_id="other-filter-store", name="另一筛选店铺", customer=second_customer)
        morning_claim = StoreShiftClaim.objects.create(store=store, shift="morning", user=first_owner, customer=self.customer)
        StoreShiftClaim.objects.create(store=store, shift="evening", user=second_owner, customer=self.customer)
        StoreShiftClaim.objects.create(store=other_store, shift="morning", user=other_owner, customer=second_customer)
        StoreMetric.objects.create(store=store, consultation_count=11)
        StoreMetric.objects.create(store=other_store, consultation_count=22)
        ShiftDailySummary.objects.create(store=store, user=first_owner, shift="morning", summary_date="2026-09-01", consultation_count=11)
        ShiftDailySummary.objects.create(store=other_store, user=other_owner, shift="morning", summary_date="2026-09-01", consultation_count=22)

        admin = User.objects.create_superuser(username="filter-admin", password="strong-pass-123", responsible_name="数据管理员")
        self.client.force_login(admin)
        response = self.client.get(reverse("store_data_center"), {"customer": self.customer.pk, "responsible": first_owner.pk})
        self.assertContains(response, "筛选店铺")
        self.assertNotContains(response, "另一筛选店铺")
        self.assertContains(response, "负责人 1：负责人甲")
        self.assertContains(response, "负责人 2：负责人乙")

        response = self.client.get(reverse("monthly_replies"), {"month": "2026-09", "customer": self.customer.pk, "responsible": first_owner.pk})
        self.assertContains(response, "负责人甲")
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["user__username"], first_owner.username)

        response = self.client.post(reverse("release_store_responsibility", args=[store.pk]), {"claim_id": morning_claim.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(StoreShiftClaim.objects.filter(pk=morning_claim.pk).exists())
        self.assertTrue(StoreShiftClaim.objects.filter(store=store, user=second_owner).exists())

    def test_cookie_scope_and_account_store_search_for_regular_user(self):
        owner = User.objects.create_user(username="cookie-owner", password="strong-pass-123", responsible_name="Cookie负责人")
        other_owner = User.objects.create_user(username="cookie-other", password="strong-pass-123", responsible_name="其他负责人")
        own_store = Store.objects.create(platform="pdd", external_id="own-cookie-store", name="我的 Cookie 店")
        other_store = Store.objects.create(platform="pdd", external_id="other-cookie-store", name="别人的 Cookie 店")
        StoreShiftClaim.objects.create(store=own_store, shift="morning", user=owner, customer=self.customer)
        StoreShiftClaim.objects.create(store=other_store, shift="morning", user=other_owner, customer=self.customer)
        self.client.force_login(owner)
        response = self.client.get(reverse("cookie_center"))
        self.assertContains(response, "我的 Cookie 店")
        self.assertNotContains(response, "别人的 Cookie 店")
        response = self.client.get(reverse("account_center"))
        self.assertContains(response, "store-search")
        response = self.client.get(reverse("store_data_api"))
        self.assertEqual(response.status_code, 200)
        api_store_names = [row["name"] for row in response.json()["data"]["rows"]]
        self.assertEqual(api_store_names, [own_store.name])

    def test_pdd_timeout_counts_are_derived_from_total_consultations_and_reply_rate(self):
        store = Store.objects.create(platform="pdd", external_id="pdd-timeout", name="超时计算店")
        response = self.client.post(reverse("api_store_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 11,
            "specialist_reply_count": 8,
            "specialist_three_minute_reply_rate": "80",
            "specialist_timeout_count": 99,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("api_robot_metrics_upsert"), data={
            "shop_id": store.external_id,
            "platform": "pdd",
            "time": 11,
            "robot_completed_reply_count": 2,
            "robot_timeout_count": 88,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        metric = StoreMetric.objects.get(store=store)
        self.assertEqual(metric.consultation_count, 10)
        self.assertEqual(metric.timeout_count, 2)
        self.assertEqual(metric.robot_timeout_count, 2)
        snapshot = StoreMetricSnapshot.objects.get(store=store, report_hour=11)
        self.assertEqual(snapshot.timeout_count, 2)
        self.assertEqual(snapshot.robot_timeout_count, 2)

    def test_admin_can_set_cookie_status_and_delete_another_user_from_permission_center(self):
        admin = User.objects.create_superuser(username="control-admin", password="strong-pass-123", responsible_name="平台管理员")
        target = User.objects.create_user(username="delete-target", password="strong-pass-123", responsible_name="待删除账号")
        store = Store.objects.create(platform="pdd", external_id="manual-cookie", name="手动 Cookie 店")
        self.client.force_login(admin)

        response = self.client.get(reverse("permission_center"))
        self.assertContains(response, "删除账号")
        self.assertContains(response, "user-delete-dialog")
        response = self.client.post(reverse("permission_user_delete", args=[target.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=target.pk).exists())

        response = self.client.post(reverse("cookie_status_update", args=[store.pk]), {"cookie_status": "invalid"})
        self.assertEqual(response.status_code, 302)
        store.refresh_from_db()
        self.assertEqual(store.cookie_status, "invalid")
        response = self.client.post(reverse("cookie_status_update", args=[store.pk]), {"cookie_status": "valid"})
        self.assertEqual(response.status_code, 302)
        store.refresh_from_db()
        self.assertEqual(store.cookie_status, "valid")

    def test_admin_can_update_responsible_name_and_password_from_permission_center(self):
        admin = User.objects.create_superuser(username="profile-admin", password="strong-pass-123", responsible_name="平台管理员")
        target = User.objects.create_user(username="profile-target", password="old-strong-pass-123", responsible_name="原负责人")
        self.client.force_login(admin)

        response = self.client.get(reverse("permission_center"))
        self.assertContains(response, "user-password-dialog")
        self.assertContains(response, "修改密码")
        response = self.client.post(reverse("permission_center"), {
            "user_id": target.pk,
            "responsible_name": "新负责人",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertEqual(target.responsible_name, "新负责人")

        response = self.client.post(reverse("permission_center"), {
            "action": "change_password",
            "user_id": target.pk,
            "new_password": "new-strong-pass-456",
        })
        self.assertEqual(response.status_code, 302)
        target.refresh_from_db()
        self.assertTrue(target.check_password("new-strong-pass-456"))

    def test_only_admin_can_clear_all_pending_tasks(self):
        owner = User.objects.create_user(username="clear-owner", password="strong-pass-123", responsible_name="待办负责人")
        admin = User.objects.create_superuser(username="clear-admin", password="strong-pass-123", responsible_name="待办管理员")
        store = Store.objects.create(platform="pdd", external_id="clear-todo", name="清理待办店", customer=self.customer)
        StoreShiftClaim.objects.create(store=store, shift="morning", user=owner, customer=self.customer)
        task = PendingTask.objects.create(store=store, handling_item="需要清理的待办")

        self.client.force_login(owner)
        self.assertEqual(self.client.post(reverse("pending_tasks_clear_all")).status_code, 403)
        task.refresh_from_db()
        self.assertFalse(task.is_processed)

        self.client.force_login(admin)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "清除全部待处理事务")
        self.assertEqual(self.client.post(reverse("pending_tasks_clear_all")).status_code, 302)
        task.refresh_from_db()
        self.assertTrue(task.is_processed)
        self.assertEqual(task.processed_by, admin)

    def test_store_data_headers_are_click_sortable_and_explain_average_response(self):
        Store.objects.create(platform="pdd", external_id="header-b", name="B店")
        Store.objects.create(platform="douyin", external_id="header-a", name="A店")
        admin = User.objects.create_superuser(username="header-admin", password="strong-pass-123", responsible_name="数据管理员")
        self.client.force_login(admin)
        response = self.client.get(reverse("store_data_center"), {"sort": "store_name", "direction": "asc"})
        self.assertEqual([store.name for store in response.context["stores"]], ["A店", "B店"])
        self.assertContains(response, "sort=store_name&amp;direction=desc")
        self.assertContains(response, "平均响应")
        self.assertContains(response, "拼多多是昨日平均响应时间，抖音是今日实时平均响应时间")
        self.assertContains(response, "超时人数 = 总咨询人数")
        self.assertContains(response, "统计时点")

    def test_store_data_center_can_show_an_exact_date_and_hour_snapshot(self):
        store = Store.objects.create(platform="pdd", external_id="hourly-store", name="小时查询店")
        for hour, count, rate in ((9, 10, "90"), (11, 20, "80")):
            response = self.client.post(reverse("api_store_metrics_upsert"), data={
                "shop_id": store.external_id,
                "platform": "pdd",
                "report_date": "2026-09-20",
                "time": hour,
                "specialist_reply_count": count,
                "specialist_three_minute_reply_rate": rate,
            }, content_type="application/json")
            self.assertEqual(response.status_code, 200)

        admin = User.objects.create_superuser(username="hour-admin", password="strong-pass-123", responsible_name="数据管理员")
        self.client.force_login(admin)
        response = self.client.get(reverse("store_data_center"), {"date": "2026-09-20", "hour": 9})
        display_metric = response.context["stores"][0].display_metric
        self.assertEqual(display_metric.consultation_count, 10)
        self.assertEqual(display_metric.timeout_count, 1)


class AIKnowledgeTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="知识库客户")
        self.owner = User.objects.create_user(username="knowledge-owner", password="strong-pass-123", responsible_name="知识库负责人")
        self.viewer = User.objects.create_user(username="knowledge-viewer", password="strong-pass-123", responsible_name="只读查看人")
        self.store = Store.objects.create(platform="pdd", external_id="ai-shop-001", name="AI 测试店", customer=self.customer)
        StoreShiftClaim.objects.create(store=self.store, shift="morning", user=self.owner, customer=self.customer)
        self.material = CustomerMaterial.objects.create(customer=self.customer, name="纯棉", created_by=self.owner)

    def test_product_upload_and_knowledge_resolve_include_all_layers(self):
        upload = self.client.post(
            reverse("api_ai_product_upsert"),
            data={
                "platform": "拼多多",
                "zl": {
                    "shopSN": self.store.external_id,
                    "goods_id": "goods-ai-1",
                    "goods_name": "纯棉短袖",
                    "mainimgurls": ["https://img.example.com/main.jpg"],
                    "detailimgurls": ["https://img.example.com/detail.jpg"],
                    "values": [{"name": "版型", "value": "宽松"}],
                    "skudetails": [{"skuname": "白色/L", "sku_id": "sku-ai-1", "quantity": 5000, "price": 2380}],
                },
            },
            content_type="application/json",
        )
        self.assertEqual(upload.status_code, 200)
        product = Product.objects.get(store=self.store, goods_id="goods-ai-1")
        product.material = self.material
        product.save()

        AIKnowledgePrompt.objects.create(customer=self.customer, scene="general", content="客户通用提示")
        AIKnowledgePrompt.objects.create(store=self.store, scene="presale", content="店铺售前提示")
        AIKnowledgePrompt.objects.create(material=self.material, scene="general", content="纯棉材质提示")
        AIKnowledgePrompt.objects.create(product=product, scene="presale", content="商品售前提示")
        AIKnowledgeQA.objects.create(customer=self.customer, scene="general", question="客户问题", answer="客户回答")
        AIKnowledgeQA.objects.create(store=self.store, scene="presale", question="店铺问题", answer="店铺回答")
        AIKnowledgeQA.objects.create(material=self.material, scene="presale", question="材质问题", answer="材质回答")
        AIKnowledgeQA.objects.create(product=product, scene="presale", question="商品问题", answer="商品回答")
        AIKnowledgeKeyword.objects.create(customer=self.customer, scene="general", keyword="客户词", answer="客户关键词回答", match_type="exact")
        AIKnowledgeKeyword.objects.create(store=self.store, scene="presale", keyword="店铺词", answer="店铺关键词回答", match_type="contains")
        AIKnowledgeKeyword.objects.create(material=self.material, scene="presale", keyword="纯棉", answer="材质关键词回答", match_type="contains")
        AIKnowledgeKeyword.objects.create(product=product, scene="presale", keyword="短袖", answer="商品关键词回答", match_type="exact")

        response = self.client.post(
            reverse("api_ai_knowledge_resolve"),
            data={"platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "售前"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.knowledge_heat, 1)
        data = response.json()["data"]
        self.assertEqual(data["product"]["title"], "纯棉短袖")
        self.assertEqual(data["product"]["attributes"], [{"name": "版型", "value": "宽松"}])
        self.assertEqual(data["product"]["sku"], [{"skuname": "白色/L", "sku_id": "sku-ai-1", "quantity": 5000, "price": 2380}])
        self.assertEqual(data["product"]["sku_details"], [{"sku_id": "sku-ai-1", "sku_name": "白色/L", "stock": 5000, "price": 2380, "price_yuan": "23.80", "raw": {"skuname": "白色/L", "sku_id": "sku-ai-1", "quantity": 5000, "price": 2380}}])
        self.assertEqual(data["product"]["mainimgurls"], ["https://img.example.com/main.jpg"])
        self.assertEqual(data["product"]["detailimgurls"], ["https://img.example.com/detail.jpg"])
        self.assertEqual(data["product"]["material"]["name"], "纯棉")
        self.assertEqual({row["source"] for row in data["knowledge"]["special_prompts"]}, {"customer", "store", "material", "product"})
        self.assertEqual({row["source"] for row in data["knowledge"]["qas"]}, {"customer", "store", "material", "product"})
        self.assertEqual({row["source"] for row in data["knowledge"]["keywords"]}, {"customer", "store", "material", "product"})
        self.assertIn({"match_type": "exact", "match_type_name": "完全一样"}, [{"match_type": row["match_type"], "match_type_name": row["match_type_name"]} for row in data["knowledge"]["keywords"]])
        self.assertEqual({row["answer"] for row in data["knowledge"]["keywords"]}, {"客户关键词回答", "店铺关键词回答", "材质关键词回答", "商品关键词回答"})

        self.store.block_customer_prompts = True
        self.store.block_customer_qas = True
        self.store.block_customer_keywords = True
        self.store.save()
        response = self.client.get(
            reverse("api_ai_knowledge_resolve"),
            {"platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "presale"},
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.knowledge_heat, 2)
        data = response.json()["data"]
        self.assertNotIn("customer", {row["source"] for row in data["knowledge"]["special_prompts"]})
        self.assertNotIn("customer", {row["source"] for row in data["knowledge"]["qas"]})
        self.assertNotIn("customer", {row["source"] for row in data["knowledge"]["keywords"]})
        self.assertIn("material", {row["source"] for row in data["knowledge"]["special_prompts"]})

    def test_product_automatically_inherits_matching_material_prompts_qas_and_keywords(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="goods-ai-auto-material",
            payload={
                "goods_name": "标题命中自动继承商品",
                "values": [{"name": "面料", "value": "属性命中"}],
                "skudetails": [{"skuname": "SKU命中 / L", "sku_id": "sku-auto-1"}],
            },
        )
        title_material = CustomerMaterial.objects.create(customer=self.customer, name="标题命中", created_by=self.owner)
        sku_material = CustomerMaterial.objects.create(customer=self.customer, name="SKU命中", created_by=self.owner)
        attribute_material = CustomerMaterial.objects.create(customer=self.customer, name="属性命中", created_by=self.owner)
        case_mismatch_material = CustomerMaterial.objects.create(customer=self.customer, name="sku命中", created_by=self.owner)
        materials = (title_material, sku_material, attribute_material, case_mismatch_material)
        for material in materials:
            AIKnowledgePrompt.objects.create(material=material, scene="general", content=f"{material.name}提示词")
            AIKnowledgeQA.objects.create(material=material, scene="general", question=f"{material.name}问题", answer=f"{material.name}回答")
            AIKnowledgeKeyword.objects.create(material=material, scene="general", keyword=material.name, answer=f"{material.name}关键词回答")

        resolve_url = reverse("api_ai_knowledge_resolve")
        resolve_data = {"platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "presale"}
        response = self.client.get(resolve_url, resolve_data)
        self.assertEqual(response.status_code, 200)
        knowledge = response.json()["data"]["knowledge"]
        self.assertEqual(
            {item["content"] for item in knowledge["special_prompts"]},
            {"标题命中提示词", "SKU命中提示词", "属性命中提示词"},
        )
        self.assertEqual(
            {item["question"] for item in knowledge["qas"]},
            {"标题命中问题", "SKU命中问题", "属性命中问题"},
        )
        self.assertEqual(
            {item["answer"] for item in knowledge["keywords"]},
            {"标题命中关键词回答", "SKU命中关键词回答", "属性命中关键词回答"},
        )
        self.assertEqual(
            {item["source_name"] for item in knowledge["special_prompts"]},
            {"客户素材：标题命中", "客户素材：SKU命中", "客户素材：属性命中"},
        )

        self.client.force_login(self.owner)
        product_url = reverse("ai_knowledge_detail", args=["product", product.pk])
        page = self.client.get(product_url)
        self.assertContains(page, "客户素材：标题命中")
        self.assertContains(page, "SKU命中提示词")

        sku_prompt = AIKnowledgePrompt.objects.get(material=sku_material)
        response = self.client.post(product_url, {
            "action": "set_inheritance_block",
            "entry_type": "prompt",
            "entry_id": sku_prompt.pk,
            "is_blocked": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AIKnowledgePromptBlock.objects.filter(product=product, prompt=sku_prompt).exists())
        response = self.client.get(resolve_url, resolve_data)
        self.assertNotIn("SKU命中提示词", [item["content"] for item in response.json()["data"]["knowledge"]["special_prompts"]])

        product.payload = {"goods_name": "已经取消自动匹配", "values": [{"name": "面料", "value": "普通"}]}
        product.save(update_fields=["payload", "updated_at"])
        response = self.client.get(resolve_url, resolve_data)
        knowledge = response.json()["data"]["knowledge"]
        self.assertEqual(knowledge["special_prompts"], [])
        self.assertEqual(knowledge["qas"], [])
        self.assertEqual(knowledge["keywords"], [])

    def test_material_detail_lists_inheriting_products_and_can_block_all_material_content(self):
        manual_product = Product.objects.create(
            store=self.store,
            goods_id="goods-material-manual-block",
            payload={"goods_name": "手动标注商品"},
            material=self.material,
        )
        auto_product = Product.objects.create(
            store=self.store,
            goods_id="goods-material-auto-block",
            payload={"goods_name": "纯棉自动命中商品"},
        )
        prompt = AIKnowledgePrompt.objects.create(
            material=self.material, scene="general", content="纯棉整项屏蔽提示词"
        )
        AIKnowledgeQA.objects.create(
            material=self.material, scene="general", question="纯棉整项屏蔽问题", answer="纯棉整项屏蔽回答"
        )
        AIKnowledgeKeyword.objects.create(
            material=self.material, scene="general", keyword="纯棉整项屏蔽词", answer="纯棉整项屏蔽关键词回答"
        )
        self.client.force_login(self.owner)
        material_url = reverse("ai_knowledge_detail", args=["material", self.material.pk])
        page = self.client.get(material_url)
        self.assertContains(page, "继承该素材的商品")
        self.assertContains(page, manual_product.goods_id)
        self.assertContains(page, auto_product.goods_id)
        self.assertContains(page, "手动标注")
        self.assertContains(page, "自动匹配")

        response = self.client.post(material_url, {
            "action": "set_product_material_inheritance_block",
            "product_id": auto_product.pk,
            "is_blocked": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProductMaterialInheritanceBlock.objects.filter(product=auto_product, material=self.material).exists()
        )
        resolve_url = reverse("api_ai_knowledge_resolve")
        response = self.client.get(resolve_url, {
            "platform": "pdd", "shopid": self.store.external_id,
            "goods_id": auto_product.goods_id, "scene": "presale",
        })
        self.assertEqual(response.status_code, 200)
        knowledge = response.json()["data"]["knowledge"]
        self.assertNotIn(prompt.content, [item["content"] for item in knowledge["special_prompts"]])
        self.assertNotIn("纯棉整项屏蔽问题", [item["question"] for item in knowledge["qas"]])
        self.assertNotIn("纯棉整项屏蔽词", [item["keyword"] for item in knowledge["keywords"]])

        response = self.client.post(
            reverse("api_ai_knowledge_keyword_match"),
            data={"product_pk": auto_product.pk, "text": "纯棉整项屏蔽词"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "无匹配")

        response = self.client.post(material_url, {
            "action": "set_product_material_inheritance_block",
            "product_id": auto_product.pk,
            "is_blocked": "0",
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProductMaterialInheritanceBlock.objects.filter(product=auto_product, material=self.material).exists()
        )
        response = self.client.get(resolve_url, {
            "platform": "pdd", "shopid": self.store.external_id,
            "goods_id": auto_product.goods_id, "scene": "presale",
        })
        self.assertIn(prompt.content, [item["content"] for item in response.json()["data"]["knowledge"]["special_prompts"]])

    def test_material_list_can_filter_paginate_and_delete_material(self):
        another_customer = Customer.objects.create(name="素材筛选客户")
        for index in range(36):
            CustomerMaterial.objects.create(customer=self.customer, name=f"分页素材{index:02d}")
        target = CustomerMaterial.objects.create(customer=another_customer, name="待删除素材")
        target_product = Product.objects.create(
            store=Store.objects.create(
                platform="pdd", external_id="material-delete-store", name="素材删除店铺", customer=another_customer
            ),
            goods_id="material-delete-product",
            payload={"goods_name": "素材删除商品"},
            material=target,
        )
        StoreShiftClaim.objects.create(store=target_product.store, shift="morning", user=self.owner, customer=another_customer)
        self.client.force_login(self.owner)
        list_url = reverse("ai_knowledge_list", args=["material"])
        response = self.client.get(list_url, {"customer": self.customer.pk, "page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="customer"')
        self.assertEqual(response.context["page_obj"].paginator.count, 37)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertNotContains(response, target.name)

        api_response = self.client.get(
            reverse("ai_knowledge_list_api", args=["material"]), {"customer": self.customer.pk, "page": 2}
        )
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(api_response.json()["data"]["pagination"]["count"], 37)
        self.assertEqual(len(api_response.json()["data"]["rows"]), 2)

        delete_response = self.client.post(reverse("ai_material_delete", args=[target.pk]))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(CustomerMaterial.objects.filter(pk=target.pk).exists())
        target_product.refresh_from_db()
        self.assertIsNone(target_product.material_id)

    def test_keyword_match_api_uses_effective_product_keywords_and_returns_answers(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="goods-ai-keyword-match",
            payload={"goods_name": "自动素材命中商品"},
        )
        material = CustomerMaterial.objects.create(customer=self.customer, name="自动素材", created_by=self.owner)
        material_keyword = AIKnowledgeKeyword.objects.create(
            material=material,
            scene="general",
            keyword="自动词",
            answer="自动素材关键词回答",
            match_type="contains",
        )
        AIKnowledgeKeyword.objects.create(
            store=self.store,
            scene="general",
            keyword="店铺词",
            answer="店铺关键词回答",
            match_type="contains",
        )
        AIKnowledgeKeyword.objects.create(
            product=product,
            scene="presale",
            keyword="精确问题",
            answer="商品精确回答",
            match_type="exact",
        )
        match_url = reverse("api_ai_knowledge_keyword_match")

        response = self.client.post(
            match_url,
            data={"product_id": product.goods_id, "shopid": self.store.external_id, "text": "包含自动词和店铺词的句子"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.knowledge_heat, 1)
        payload = response.json()
        self.assertTrue(payload["matched"])
        self.assertEqual(payload["answer"], "店铺关键词回答\n自动素材关键词回答")
        self.assertEqual(
            {item["answer"] for item in payload["data"]["matches"]},
            {"店铺关键词回答", "自动素材关键词回答"},
        )

        response = self.client.post(
            match_url,
            data={"product_pk": product.pk, "text": "精确问题", "scene": "售前"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.knowledge_heat, 2)
        self.assertEqual(response.json()["answer"], "商品精确回答")

        self.client.force_login(self.owner)
        product_url = reverse("ai_knowledge_detail", args=["product", product.pk])
        response = self.client.post(product_url, {
            "action": "set_inheritance_block",
            "entry_type": "keyword",
            "entry_id": material_keyword.pk,
            "is_blocked": "on",
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            match_url,
            data={"product_pk": product.pk, "text": "自动词"},
            content_type="application/json",
        )
        self.assertFalse(response.json()["matched"])
        self.assertEqual(response.json()["answer"], "无匹配")
        product.refresh_from_db()
        self.assertEqual(product.knowledge_heat, 3)

    def test_store_order_urging_script_api_reads_effective_store_scripts(self):
        OrderUrgingScript.objects.create(
            customer=self.customer,
            pending_payment="客户待支付话术",
            unplaced_order="客户未下单话术",
        )
        endpoint = reverse("api_order_urging_store_script")

        response = self.client.get(endpoint, {"store_id": self.store.external_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {
            "store_id": self.store.external_id,
            "store_pk": self.store.pk,
            "platform": self.store.platform,
            "pending_payment": "客户待支付话术",
            "unplaced_order": "客户未下单话术",
        })

        OrderUrgingScript.objects.create(
            store=self.store,
            pending_payment="店铺待支付话术",
            block_parent_unplaced_order=True,
        )
        response = self.client.post(
            endpoint,
            data={"shopid": self.store.external_id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pending_payment"], "店铺待支付话术")
        self.assertEqual(response.json()["data"]["unplaced_order"], "无")

        self.assertEqual(self.client.get(endpoint).status_code, 400)
        self.assertEqual(self.client.get(endpoint, {"store_id": "missing-store"}).status_code, 404)

    def test_product_knowledge_apis_add_scene_qas_and_append_prompt(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="goods-ai-api-write",
            payload={"goods_name": "接口商品"},
        )
        qa_response = self.client.post(
            reverse("api_ai_product_qa_add"),
            data={
                "shopid": self.store.external_id,
                "goods_id": product.goods_id,
                "scene": "presale",
                "qas": [
                    {"question": "售前问题一", "answer": "售前回答一"},
                    {"question": "售前问题二", "answer": "售前回答二"},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(qa_response.status_code, 201)
        self.assertEqual(qa_response.json()["created_count"], 2)
        self.assertEqual(
            AIKnowledgeQA.objects.filter(product=product, scene="presale").count(),
            2,
        )
        missing_scene_response = self.client.post(
            reverse("api_ai_product_qa_add"),
            data={"shopid": self.store.external_id, "goods_id": product.goods_id, "qas": [{"question": "缺少场景", "answer": "不会写入"}]},
            content_type="application/json",
        )
        self.assertEqual(missing_scene_response.status_code, 400)

        first_prompt_response = self.client.post(
            reverse("api_ai_product_prompt_append"),
            data={"shop_id": self.store.external_id, "goods_id": product.goods_id, "scene": "general", "prompt": "第一句通用提示词"},
            content_type="application/json",
        )
        self.assertEqual(first_prompt_response.status_code, 200)
        self.assertTrue(first_prompt_response.json()["created"])
        second_prompt_response = self.client.post(
            reverse("api_ai_product_prompt_append"),
            data={"shop_id": self.store.external_id, "goods_id": product.goods_id, "scene": "通用", "prompt": "第二句通用提示词"},
            content_type="application/json",
        )
        self.assertEqual(second_prompt_response.status_code, 200)
        self.assertFalse(second_prompt_response.json()["created"])
        self.assertEqual(second_prompt_response.json()["data"]["content"], "第一句通用提示词\n第二句通用提示词")
        aftersale_prompt_response = self.client.post(
            reverse("api_ai_product_prompt_append"),
            data={"shop_id": self.store.external_id, "goods_id": product.goods_id, "scene": "aftersale", "prompt": "售后提示词"},
            content_type="application/json",
        )
        self.assertEqual(aftersale_prompt_response.status_code, 200)

        presale_response = self.client.get(reverse("api_ai_knowledge_resolve"), {
            "platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "presale",
        })
        self.assertEqual(presale_response.status_code, 200)
        presale_knowledge = presale_response.json()["data"]["knowledge"]
        self.assertTrue({"售前问题一", "售前问题二"}.issubset({item["question"] for item in presale_knowledge["qas"]}))
        self.assertIn("第一句通用提示词\n第二句通用提示词", [item["content"] for item in presale_knowledge["special_prompts"]])
        self.assertNotIn("售后提示词", [item["content"] for item in presale_knowledge["special_prompts"]])

        aftersale_response = self.client.get(reverse("api_ai_knowledge_resolve"), {
            "platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "aftersale",
        })
        self.assertEqual(aftersale_response.status_code, 200)
        aftersale_knowledge = aftersale_response.json()["data"]["knowledge"]
        self.assertNotIn("售前问题一", [item["question"] for item in aftersale_knowledge["qas"]])
        self.assertIn("第一句通用提示词\n第二句通用提示词", [item["content"] for item in aftersale_knowledge["special_prompts"]])
        self.assertIn("售后提示词", [item["content"] for item in aftersale_knowledge["special_prompts"]])

    def test_knowledge_pages_are_visible_to_all_but_editable_only_by_responsible_user(self):
        product = Product.objects.create(store=self.store, goods_id="goods-ai-2", payload={"goods_name": "测试商品", "mainimgurls": ["https://img.example.com/list-main.jpg"], "skudetails": [{"skuname": "黑色/L", "quantity": 5000, "price": 2380}]})
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("ai_knowledge_list", args=["product"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "测试商品")
        response = self.client.get(reverse("ai_knowledge_detail", args=["product", product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "商品材质标注")
        self.assertContains(response, "特殊提示词")
        self.assertContains(response, "https://img.example.com/list-main.jpg")
        self.assertContains(response, "SKU、库存与价格")
        self.assertContains(response, "5000")
        self.assertContains(response, "¥23.80")
        response = self.client.post(
            reverse("ai_knowledge_detail", args=["product", product.pk]),
            {"action": "add_qa", "scene": "general", "question": "只读用户", "answer": "不应写入"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AIKnowledgeQA.objects.filter(question="只读用户").exists())

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("ai_knowledge_detail", args=["product", product.pk]),
            {"action": "add_qa", "scene": "general", "question": "负责人问题", "answer": "负责人回答"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AIKnowledgeQA.objects.filter(product=product, question="负责人问题").exists())
        response = self.client.get(reverse("ai_knowledge_list", args=["product"]), {"only_mine": "1"})
        self.assertContains(response, "测试商品")

    def test_store_and_product_knowledge_lists_support_platform_customer_and_store_filters(self):
        other_customer = Customer.objects.create(name="另一知识库客户")
        other_store = Store.objects.create(
            platform="douyin", external_id="ai-shop-002", name="抖音 AI 测试店", customer=other_customer
        )
        other_owner = User.objects.create_user(username="other-knowledge-owner", password="strong-pass-123", responsible_name="另一负责人")
        StoreShiftClaim.objects.create(store=other_store, shift="morning", user=other_owner, customer=other_customer)
        own_product = Product.objects.create(
            store=self.store, goods_id="filter-product-pdd", payload={"goods_name": "拼多多筛选商品"}
        )
        other_product = Product.objects.create(
            store=other_store, goods_id="filter-product-douyin", payload={"goods_name": "抖音筛选商品"}
        )
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("ai_knowledge_list", args=["store"]),
            {"platform": "pdd", "customer": self.customer.pk},
        )
        self.assertContains(response, self.store.name)
        self.assertNotContains(response, other_store.name)
        self.assertContains(response, 'name="platform"')
        self.assertContains(response, 'name="customer"')

        response = self.client.get(reverse("ai_knowledge_list", args=["product"]), {"platform": "douyin"})
        self.assertContains(response, "抖音筛选商品")
        self.assertNotContains(response, "拼多多筛选商品")

        response = self.client.get(reverse("ai_knowledge_list", args=["product"]), {"customer": other_customer.pk})
        self.assertContains(response, "抖音筛选商品")
        self.assertNotContains(response, "拼多多筛选商品")

        response = self.client.get(reverse("ai_knowledge_list", args=["product"]), {"store": self.store.pk})
        self.assertContains(response, own_product.goods_id)
        self.assertNotContains(response, other_product.goods_id)
        self.assertContains(response, 'name="store"')

        admin = User.objects.create_superuser(username="knowledge-filter-admin", password="strong-pass-123", responsible_name="知识库管理员")
        self.client.force_login(admin)
        response = self.client.get(
            reverse("ai_knowledge_list", args=["store"]), {"responsible": self.owner.pk}
        )
        self.assertContains(response, self.store.name)
        self.assertNotContains(response, other_store.name)
        self.assertContains(response, 'name="responsible"')

        response = self.client.get(
            reverse("ai_knowledge_list", args=["product"]), {"responsible": other_owner.pk}
        )
        self.assertContains(response, other_product.goods_id)
        self.assertNotContains(response, own_product.goods_id)

    def test_management_centers_filter_by_customer_and_store_name_or_id(self):
        other_customer = Customer.objects.create(name="另一筛选客户")
        other_store = Store.objects.create(
            platform="douyin", external_id="filter-shop-other", name="另一筛选店", customer=other_customer
        )
        own_account = StoreAccount.objects.create(
            store=self.store, name="筛选专员", login_account="filter-owner",
            login_password="filter-secret", account_type="human",
        )
        StoreAccount.objects.create(
            store=other_store, name="另一筛选专员", login_account="filter-other",
            login_password="other-secret", account_type="human",
        )
        StoreAccount.objects.create(
            store=self.store, name="筛选机器人", login_account="filter-bot",
            login_password="bot-secret", account_type="bot",
        )
        admin = User.objects.create_superuser(
            username="center-filter-admin", password="strong-pass-123", responsible_name="筛选管理员"
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("cookie_center"), {"customer": self.customer.pk})
        self.assertContains(response, self.store.name)
        self.assertNotContains(response, other_store.name)
        self.assertContains(response, 'name="customer"')
        self.assertContains(response, f'value="{self.customer.pk}" selected')

        response = self.client.get(reverse("cookie_center_api"), {"store": other_store.external_id})
        rows = response.json()["data"]["rows"]
        self.assertEqual([row["external_id"] for row in rows], [other_store.external_id])

        response = self.client.get(reverse("account_center"), {"store": self.store.name})
        self.assertContains(response, own_account.login_account)
        self.assertNotContains(response, "filter-other")
        self.assertContains(response, 'name="customer"')

        response = self.client.get(reverse("account_center"), {"has_robot_account": "on"})
        self.assertContains(response, own_account.login_account)
        self.assertContains(response, "filter-bot")
        self.assertNotContains(response, "filter-other")
        self.assertContains(response, 'name="has_robot_account"')
        filtered_rows = self.client.get(
            reverse("account_center_api"), {"has_robot_account": "on"}
        ).json()["data"]["rows"]
        self.assertEqual({row["store_external_id"] for row in filtered_rows}, {self.store.external_id})

        response = self.client.get(reverse("account_password_center"), {"customer": other_customer.pk})
        self.assertContains(response, "filter-other")
        self.assertNotContains(response, own_account.login_account)
        self.assertContains(response, '<select name="customer">', html=False)

    def test_each_user_can_toggle_product_favorites_and_view_only_their_favorites(self):
        product = Product.objects.create(
            store=self.store, goods_id="favorite-product", payload={"goods_name": "我的收藏商品"}
        )
        other_product = Product.objects.create(
            store=self.store, goods_id="not-favorite-product", payload={"goods_name": "未收藏商品"}
        )
        self.client.force_login(self.viewer)

        product_list = self.client.get(reverse("ai_knowledge_list", args=["product"]))
        self.assertContains(product_list, 'data-product-favorite-url')

        toggle_url = reverse("ai_product_favorite_toggle", args=[product.pk])
        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["favorite"])
        self.assertTrue(ProductFavorite.objects.filter(user=self.viewer, product=product).exists())

        response = self.client.get(reverse("ai_knowledge_list_api", args=["product"]))
        favorite_row = next(row for row in response.json()["data"]["rows"] if row["id"] == product.pk)
        self.assertTrue(favorite_row["is_favorite"])
        self.assertEqual(favorite_row["favorite_url"], toggle_url)

        favorite_page = self.client.get(reverse("ai_favorite_product_list"))
        self.assertContains(favorite_page, "收藏的商品")
        self.assertContains(favorite_page, product.goods_id)
        self.assertNotContains(favorite_page, other_product.goods_id)
        self.assertContains(favorite_page, reverse("ai_favorite_product_list_api"))

        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["favorite"])
        self.assertFalse(ProductFavorite.objects.filter(user=self.viewer, product=product).exists())

    def test_ai_knowledge_list_api_uses_json_pagination_and_orders_products_by_heat(self):
        for index in range(36):
            Product.objects.create(
                store=self.store,
                goods_id=f"json-page-product-{index}",
                payload={
                    "goods_name": f"JSON 渲染商品 {index}",
                    "values": [{"AttributeName": "品牌", "AttributeValue": "测试品牌"}],
                },
            )

        self.client.force_login(self.viewer)
        page = self.client.get(reverse("ai_knowledge_list", args=["product"]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-json-page-type="ai-knowledge"')
        self.assertContains(page, "热度")
        self.assertNotContains(page, "商品属性")

        hottest = Product.objects.get(store=self.store, goods_id="json-page-product-1")
        hottest.knowledge_heat = 12
        hottest.save(update_fields=["knowledge_heat"])
        warm = Product.objects.get(store=self.store, goods_id="json-page-product-0")
        warm.knowledge_heat = 5
        warm.save(update_fields=["knowledge_heat"])

        response = self.client.get(reverse("ai_knowledge_list_api", args=["product"]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["pagination"]["count"], 36)
        self.assertEqual(len(payload["data"]["rows"]), 35)
        self.assertEqual(payload["data"]["rows"][0]["id"], hottest.pk)
        self.assertEqual(payload["data"]["rows"][0]["knowledge_heat"], 12)
        self.assertEqual(payload["data"]["rows"][1]["id"], warm.pk)
        self.assertEqual(payload["data"]["rows"][1]["knowledge_heat"], 5)
        self.assertNotIn("attributes", payload["data"]["rows"][0])

        second_page = self.client.get(reverse("ai_knowledge_list_api", args=["product"]), {"page": 2})
        self.assertEqual(len(second_page.json()["data"]["rows"]), 1)

    def test_only_superusers_or_authorized_users_can_delete_product_from_knowledge_list(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="admin-delete-product",
            payload={"goods_name": "待删除商品"},
        )
        AIKnowledgeQA.objects.create(product=product, question="待删除问题", answer="待删除回答")
        delete_url = reverse("ai_product_delete", args=[product.pk])

        self.client.force_login(self.owner)
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

        staff_user = User.objects.create_user(
            username="knowledge-product-delete-staff",
            password="strong-pass-123",
            responsible_name="普通后台人员",
            is_staff=True,
        )
        self.client.force_login(staff_user)
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

        admin = User.objects.create_superuser(username="knowledge-product-delete-admin", password="strong-pass-123", responsible_name="知识库管理员")
        self.client.force_login(admin)
        response = self.client.get(reverse("ai_knowledge_list_api", args=["product"]))
        row = response.json()["data"]["rows"][0]
        self.assertTrue(row["can_delete"])
        self.assertEqual(row["delete_url"], delete_url)
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(AIKnowledgeQA.objects.filter(question="待删除问题").exists())

        delegated_product = Product.objects.create(
            store=self.store,
            goods_id="delegated-delete-product",
            payload={"goods_name": "授权删除商品"},
        )
        self.owner.groups.add(Group.objects.get(name="商品删除管理员"))
        delegated_user = User.objects.get(pk=self.owner.pk)
        self.client.force_login(delegated_user)
        response = self.client.get(reverse("ai_knowledge_list_api", args=["product"]))
        delegated_row = next(row for row in response.json()["data"]["rows"] if row["id"] == delegated_product.pk)
        self.assertTrue(delegated_row["can_delete"])
        response = self.client.post(reverse("ai_product_delete", args=[delegated_product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=delegated_product.pk).exists())

    def test_deleting_a_favorite_product_returns_to_the_favorites_list(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="favorite-delete-product",
            payload={"goods_name": "收藏删除商品"},
        )
        admin = User.objects.create_superuser(
            username="favorite-delete-admin",
            password="strong-pass-123",
            responsible_name="知识库管理员",
        )
        ProductFavorite.objects.create(user=admin, product=product)
        self.client.force_login(admin)

        favorites_url = reverse("ai_favorite_product_list")
        response = self.client.get(favorites_url)
        self.assertContains(response, 'data-favorites-only="true"')
        self.assertContains(response, 'name="return_to_favorites" value="1"')

        response = self.client.post(
            reverse("ai_product_delete", args=[product.pk]),
            {"return_to_favorites": "1"},
        )
        self.assertRedirects(response, favorites_url)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_knowledge_forms_save_and_inherited_entries_can_be_blocked_individually(self):
        product = Product.objects.create(
            store=self.store,
            goods_id="goods-ai-blocks",
            payload={"goods_name": "逐条屏蔽商品"},
            material=self.material,
        )
        customer_prompt = AIKnowledgePrompt.objects.create(customer=self.customer, scene="general", content="客户提示词")
        customer_qa = AIKnowledgeQA.objects.create(customer=self.customer, scene="general", question="客户问题", answer="客户回答")
        customer_keyword = AIKnowledgeKeyword.objects.create(customer=self.customer, scene="general", keyword="客户关键词", answer="客户关键词回答", match_type="contains")
        store_qa = AIKnowledgeQA.objects.create(store=self.store, scene="general", question="店铺问题", answer="店铺回答")
        material_keyword = AIKnowledgeKeyword.objects.create(material=self.material, scene="general", keyword="材质关键词", answer="材质关键词回答", match_type="exact")

        self.client.force_login(self.owner)
        customer_url = reverse("ai_knowledge_detail", args=["customer", self.customer.pk])
        for post_data in (
            {"action": "save_prompt", "scene": "presale", "content": "保存提示词"},
            {"action": "add_qa", "scene": "presale", "question": "新增问题", "answer": "新增回答"},
            {"action": "add_keyword", "scene": "presale", "keyword": "新增关键词", "answer": "新增关键词回答", "match_type": "exact"},
        ):
            response = self.client.post(customer_url, post_data)
            self.assertEqual(response.status_code, 302)
        self.assertTrue(AIKnowledgePrompt.objects.filter(customer=self.customer, content="保存提示词").exists())
        self.assertTrue(AIKnowledgeQA.objects.filter(customer=self.customer, question="新增问题").exists())
        self.assertTrue(AIKnowledgeKeyword.objects.filter(customer=self.customer, keyword="新增关键词").exists())

        store_url = reverse("ai_knowledge_detail", args=["store", self.store.pk])
        response = self.client.get(store_url)
        self.assertContains(response, "继承内容与逐条屏蔽")
        self.assertContains(response, "客户提示词")
        response = self.client.post(store_url, {
            "action": "set_inheritance_block",
            "entry_type": "prompt",
            "entry_id": customer_prompt.pk,
            "is_blocked": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AIKnowledgePromptBlock.objects.filter(store=self.store, prompt=customer_prompt).exists())

        product_url = reverse("ai_knowledge_detail", args=["product", product.pk])
        response = self.client.post(product_url, {
            "action": "set_inheritance_block",
            "entry_type": "qa",
            "entry_id": store_qa.pk,
            "is_blocked": "on",
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.post(product_url, {
            "action": "set_inheritance_block",
            "entry_type": "keyword",
            "entry_id": material_keyword.pk,
            "is_blocked": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AIKnowledgeQABlock.objects.filter(product=product, qa=store_qa).exists())
        self.assertTrue(AIKnowledgeKeywordBlock.objects.filter(product=product, keyword=material_keyword).exists())

        response = self.client.get(reverse("api_ai_knowledge_resolve"), {
            "platform": "pdd", "shopid": self.store.external_id, "goods_id": product.goods_id, "scene": "presale",
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]["knowledge"]
        self.assertNotIn(customer_prompt.content, [item["content"] for item in data["special_prompts"]])
        self.assertIn(customer_qa.question, [item["question"] for item in data["qas"]])
        self.assertNotIn(store_qa.question, [item["question"] for item in data["qas"]])
        self.assertIn(customer_keyword.keyword, [item["keyword"] for item in data["keywords"]])
        self.assertNotIn(material_keyword.keyword, [item["keyword"] for item in data["keywords"]])

        response = self.client.post(store_url, {
            "action": "set_inheritance_block",
            "entry_type": "prompt",
            "entry_id": customer_prompt.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AIKnowledgePromptBlock.objects.filter(store=self.store, prompt=customer_prompt).exists())


class AccountPasswordRegistrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="registration-user", password="strong-pass-123", responsible_name="登记负责人"
        )
        Customer.objects.create(name="下拉客户")

    def test_manual_and_api_registration_are_independent_and_filterable(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("account_password_registration"), {
            "shop_name": "独立登记店铺",
            "platform": "自定义平台",
            "account_name": "登记账号名",
            "account_type": "specialist",
            "login_account": "login-name",
            "login_password": "login-password",
            "phone": "13800000000",
            "responsible_1": "登记负责人",
            "responsible_2": "备用负责人",
            "customer": "手工客户",
            "remarks": "仅作记录",
        })
        self.assertEqual(response.status_code, 302)
        registration = AccountPasswordRegistration.objects.get(account_name="登记账号名")
        self.assertEqual(registration.platform, "自定义平台")
        self.assertEqual(registration.account_type, "specialist")
        self.assertEqual(registration.operator_name, "登记负责人")
        self.assertEqual(
            [field.name for field in AccountPasswordRegistration._meta.fields if field.is_relation],
            [],
        )

        response = self.client.get(
            reverse("account_password_registration"),
            {"responsible": "备用", "customer": "手工客", "store": "独立登记"},
        )
        self.assertContains(response, "下拉客户")
        self.assertContains(response, 'list="registration-responsible-options"')
        self.assertContains(response, 'list="registration-store-options"')
        self.assertContains(response, 'list="registration-platform-options"')
        self.assertContains(response, 'data-json-page-type="account-password-registrations"')
        self.assertContains(response, 'data-load-json-on-open="true"')

        response = self.client.get(
            reverse("account_password_registration_api"),
            {"responsible": "备用", "customer": "手工客", "store": "独立登记"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["pagination"]["count"], 1)
        self.assertEqual(payload["data"]["rows"][0]["shop_name"], "独立登记店铺")
        self.assertEqual(payload["data"]["rows"][0]["platform"], "自定义平台")
        self.assertIn("edit_url", payload["data"]["rows"][0])

        AccountPasswordRegistration.objects.create(shop_name="另一间店铺", customer="手工客户", responsible_1="备用负责人")
        response = self.client.get(reverse("account_password_registration_api"), {"store": "另一间"})
        self.assertEqual(response.json()["data"]["pagination"]["count"], 1)
        self.assertEqual(response.json()["data"]["rows"][0]["shop_name"], "另一间店铺")

        response = self.client.post(
            reverse("api_account_password_registration_create"),
            data={
                "store_name": "接口登记店铺", "platform": "抖音", "account_name": "接口机器人",
                "account_type": "robot",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["shop_name"], "接口登记店铺")
        self.assertEqual(payload["data"]["platform"], "抖音")
        self.assertEqual(payload["data"]["account_type"], "robot")
        self.assertEqual(payload["data"]["account_type_name"], "机器人账号")

        response = self.client.post(
            reverse("api_account_password_registration_create"), data={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["shop_name"], "")
        self.assertEqual(response.json()["data"]["platform"], "拼多多")
        self.assertEqual(response.json()["data"]["account_type"], "specialist")

        another_user = User.objects.create_user(
            username="registration-editor", password="strong-pass-123", responsible_name="更新负责人"
        )
        self.client.force_login(another_user)
        response = self.client.get(reverse("account_password_registration_edit", args=[registration.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "修改账号密码登记")
        response = self.client.post(reverse("account_password_registration_edit", args=[registration.pk]), {
            "shop_name": "已修改店铺", "platform": "自定义平台", "account_name": "已修改账号",
            "account_type": "robot", "login_account": "updated-login", "login_password": "updated-password",
            "phone": "", "responsible_1": "登记负责人", "responsible_2": "", "customer": "手工客户",
            "remarks": "已修改",
        })
        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.account_type, "robot")
        self.assertEqual(registration.operator_name, "更新负责人")

        response = self.client.post(reverse("account_password_registration_delete", args=[registration.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccountPasswordRegistration.objects.filter(pk=registration.pk).exists())


class ImageTextRegistrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="image-text-user", password="strong-pass-123", responsible_name="图片文字负责人"
        )
        self.image_url = "https://chat-img.pddugc.com/chat-pic-mall-cs-v1/2026-10-08/73e354709f2f21402170b2b117b90cde.jpeg"

    def test_image_text_registration_can_be_created_by_api_and_managed_in_json_list(self):
        response = self.client.post(
            reverse("api_image_text_registration_create"),
            data={"image_url": self.image_url, "text": "第一段对应文字"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["ok"])
        registration = ImageTextRegistration.objects.get()
        self.assertEqual(registration.content, "第一段对应文字")

        self.client.force_login(self.user)
        response = self.client.get(reverse("image_text_registration"))
        self.assertContains(response, 'id="image-text-registration-panel"')
        self.assertContains(response, 'data-api-url="/api/v1/image-text-registrations/"')
        response = self.client.get(reverse("account_password_registration"))
        self.assertNotContains(response, 'id="image-text-registration-panel"')

        response = self.client.get(reverse("image_text_registration_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["pagination"]["count"], 1)
        row = payload["data"]["rows"][0]
        self.assertEqual(row["image_url"], self.image_url)
        self.assertEqual(row["content"], "第一段对应文字")
        self.assertIn("edit_url", row)
        self.assertIn("delete_url", row)

        response = self.client.post(reverse("image_text_registration_edit", args=[registration.pk]), {"content": "已修改对应文字"})
        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.content, "已修改对应文字")

        response = self.client.post(reverse("image_text_registration_delete", args=[registration.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ImageTextRegistration.objects.filter(pk=registration.pk).exists())

    def test_image_text_registration_api_requires_both_fields_and_valid_url(self):
        response = self.client.post(
            reverse("api_image_text_registration_create"), data={"image_url": self.image_url}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse("api_image_text_registration_create"), data={"image_url": "not-an-image-url", "content": "文字"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class RemoteRegistrationTests(TestCase):
    def setUp(self):
        self.specialist = User.objects.create_user(
            username="remote-specialist", password="strong-pass-123", responsible_name="远程专员"
        )
        self.customer = Customer.objects.create(name="远程登记客户")
        self.client_user = User.objects.create_user(
            username="remote-client", password="strong-pass-123", responsible_name="客户客服",
            customer=self.customer,
        )

    def test_internal_specialist_can_manage_remote_registrations(self):
        self.client.force_login(self.specialist)
        response = self.client.post(reverse("remote_registration"), {
            "machine_no": "10001", "remote_code": "ABC-123", "remote_password": "remote-secret",
        })
        self.assertEqual(response.status_code, 302)
        registration = RemoteRegistration.objects.get(machine_no="10001")
        self.assertEqual(registration.operator_name, "远程专员")

        response = self.client.get(reverse("remote_registration"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "远程登记")
        self.assertContains(response, "remote-secret")

        response = self.client.post(reverse("remote_registration_edit", args=[registration.pk]), {
            "machine_no": "10002", "remote_code": "DEF-456", "remote_password": "changed-secret",
        })
        self.assertEqual(response.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.machine_no, "10002")
        self.assertEqual(registration.operator_name, "远程专员")

        response = self.client.post(reverse("remote_registration_delete", args=[registration.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RemoteRegistration.objects.filter(pk=registration.pk).exists())

    def test_customer_account_cannot_access_remote_registrations(self):
        registration = RemoteRegistration.objects.create(
            machine_no="10003", remote_code="GHI-789", remote_password="customer-secret", operator_name="远程专员"
        )
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse("remote_registration")).status_code, 403)
        self.assertEqual(self.client.post(reverse("remote_registration_delete", args=[registration.pk])).status_code, 403)


class WeChatPendingGroupApiTests(TestCase):
    def test_append_read_and_sent_acknowledgement_clear_the_shared_queue(self):
        self.assertFalse(WeChatPendingGroup.objects.exists())

        response = self.client.post(
            reverse("api_wechat_pending_append"), data={"content": "第一条待发送信息"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["content"], "第一条待发送信息")

        response = self.client.post(
            reverse("api_wechat_pending_append"), data={"message": "第二条待发送信息"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["content"], "第一条待发送信息\n第二条待发送信息")
        self.assertEqual(response.json()["data"]["message_count"], 2)

        response = self.client.get(reverse("api_wechat_pending_read"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["messages"], ["第一条待发送信息", "第二条待发送信息"])
        self.assertEqual(WeChatPendingGroup.objects.count(), 1)

        response = self.client.post(reverse("api_wechat_pending_sent"), data={}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sent")
        self.assertEqual(response.json()["cleared_count"], 2)
        self.assertEqual(response.json()["data"]["content"], "")

        response = self.client.get(reverse("api_wechat_pending_read"))
        self.assertEqual(response.json()["data"]["messages"], [])

    def test_pending_append_requires_content(self):
        response = self.client.post(
            reverse("api_wechat_pending_append"), data={}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


class PasswordVisibilityTests(TestCase):
    def test_all_application_password_inputs_use_plain_text_widgets(self):
        user = User.objects.create_user(username="visible-password-user", password="strong-pass-123")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.context["form"].fields["password"].widget.input_type, "text")

        response = self.client.get(reverse("register"))
        self.assertEqual(response.context["form"].fields["password1"].widget.input_type, "text")
        self.assertEqual(response.context["form"].fields["password2"].widget.input_type, "text")

        self.client.force_login(user)
        response = self.client.get(reverse("password_change"))
        self.assertEqual(response.context["form"].fields["old_password"].widget.input_type, "text")
        self.assertEqual(response.context["form"].fields["new_password1"].widget.input_type, "text")
        self.assertEqual(response.context["form"].fields["new_password2"].widget.input_type, "text")


class AfterSalesStrategyTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="售后策略客户")
        self.owner = User.objects.create_user(
            username="strategy-owner", password="strong-pass-123", responsible_name="策略负责人"
        )
        self.store = Store.objects.create(
            platform="pdd", external_id="strategy-shop-001", name="策略测试店铺",
            customer=self.customer, cookie="registered-cookie",
        )
        StoreShiftClaim.objects.create(
            store=self.store, shift="morning", user=self.owner, customer=self.customer
        )

    def test_cookie_store_strategy_can_be_configured_and_fetched_by_shopid(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("after_sales_strategy_config"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "售后策略配置")
        self.assertContains(response, "退款")
        self.assertContains(response, "补偿比例")
        self.assertContains(response, "补偿金额")

        response = self.client.post(reverse("after_sales_strategy_config"), {
            "customer_id": self.customer.pk,
            "store_id": self.store.pk,
            "compensation_type": "ratio",
            "compensation_count": 2,
            "replacement_count": 1,
            "refund_count": 3,
            "compensation_stage_count": 3,
            "compensation_minimum": "0.30",
            "compensation_maximum": "10.00",
            "warranty_days": 30,
            "first_compensation": "10.00",
            "second_compensation": "30.00",
            "third_compensation": "50.00",
        })
        self.assertEqual(response.status_code, 302)
        strategy = StoreAfterSalesStrategy.objects.get(store=self.store)
        self.assertEqual(strategy.refund_count, 3)
        self.assertEqual(strategy.compensation_type, "ratio")

        response = self.client.get(reverse("api_after_sales_strategy"), {"shopid": self.store.external_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["shopid"], self.store.external_id)
        self.assertEqual(data["negotiation_methods"], {"compensation": 2, "replacement": 1, "refund": 3})
        self.assertEqual(data["compensation_type"], "ratio")
        self.assertEqual(data["compensation_stages"][2]["value"], "50.00")
        self.assertEqual(data["compensation_stages"][2]["unit"], "%")

    def test_store_without_a_registered_cookie_cannot_be_configured(self):
        no_cookie_store = Store.objects.create(
            platform="douyin", external_id="strategy-shop-no-cookie", name="未登记 Cookie 店铺",
            customer=self.customer,
        )
        StoreShiftClaim.objects.create(
            store=no_cookie_store, shift="morning", user=self.owner, customer=self.customer
        )
        self.client.force_login(self.owner)
        response = self.client.post(reverse("after_sales_strategy_config"), {
            "customer_id": self.customer.pk,
            "store_id": no_cookie_store.pk,
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(StoreAfterSalesStrategy.objects.filter(store=no_cookie_store).exists())


class UnownedStoreAdminAssignmentTests(TestCase):
    def test_admin_can_assign_an_empty_responsible_slot(self):
        customer = Customer.objects.create(name="指派客户")
        store = Store.objects.create(platform="douyin", external_id="assign-store", name="待指派店铺")
        admin = User.objects.create_superuser(username="assign-admin", password="strong-pass-123", responsible_name="管理员")
        target = User.objects.create_user(username="assigned-user", password="strong-pass-123", responsible_name="被指派负责人")

        self.client.force_login(admin)
        response = self.client.get(reverse("unowned_store_center"))
        self.assertContains(response, "指定负责人 1")
        response = self.client.post(
            reverse("admin_assign_store_shift", args=[store.pk, "morning"]),
            {"user_id": target.pk, "customer_id": customer.pk},
        )
        self.assertEqual(response.status_code, 302)
        claim = StoreShiftClaim.objects.get(store=store, shift="morning")
        self.assertEqual(claim.user, target)
        self.assertEqual(claim.customer, customer)
        store.refresh_from_db()
        self.assertEqual(store.customer, customer)
        self.assertEqual(store.responsible, target)

        another_customer = Customer.objects.create(name="其他指定客户")
        response = self.client.post(
            reverse("admin_assign_store_shift", args=[store.pk, "evening"]),
            {"user_id": target.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(StoreShiftClaim.objects.filter(store=store, shift="evening").exists())

        response = self.client.post(
            reverse("admin_assign_store_shift", args=[store.pk, "evening"]),
            {"user_id": target.pk, "customer_id": another_customer.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(StoreShiftClaim.objects.filter(store=store, shift="evening").exists())

        response = self.client.post(
            reverse("admin_assign_store_shift", args=[store.pk, "evening"]),
            {"user_id": target.pk, "customer_id": customer.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(StoreShiftClaim.objects.filter(store=store, shift="evening", customer=customer).exists())

        self.client.force_login(target)
        response = self.client.post(
            reverse("admin_assign_store_shift", args=[store.pk, "evening"]),
            {"user_id": target.pk, "customer_id": customer.pk},
        )
        self.assertEqual(response.status_code, 403)


class ClientPortalAndAfterSalesTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="客户甲", allow_store_knowledge_view=True, allow_product_knowledge_view=True,
        )
        self.other_customer = Customer.objects.create(name="客户乙")
        self.store = Store.objects.create(
            platform="pdd", external_id="client-shop-a", name="客户甲店铺", customer=self.customer,
        )
        self.other_store = Store.objects.create(
            platform="pdd", external_id="client-shop-b", name="客户乙店铺", customer=self.other_customer,
        )
        self.client_user = User.objects.create_user(
            username="client-a", password="strong-pass-123", responsible_name="客户甲", customer=self.customer,
        )
        self.specialist = User.objects.create_user(
            username="specialist", password="strong-pass-123", responsible_name="专员",
        )

    def test_client_only_sees_own_invoice_message_and_knowledge(self):
        own_invoice = InvoiceRecord.objects.create(store=self.store, order_no="invoice-own")
        InvoiceRecord.objects.create(store=self.other_store, order_no="invoice-other")
        own_message = MessageTask.objects.create(store=self.store, order_no="message-own", reply_content="请联系售后")
        MessageTask.objects.create(store=self.other_store, order_no="message-other", reply_content="其他客户")
        own_product = Product.objects.create(store=self.store, goods_id="goods-own", payload={"title": "客户甲商品"})
        other_product = Product.objects.create(store=self.other_store, goods_id="goods-other", payload={"title": "客户乙商品"})

        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse("invoice_center")).status_code, 200)
        self.assertEqual(self.client.get(reverse("message_center")).status_code, 200)
        self.assertEqual(self.client.get(reverse("account_center")).status_code, 200)
        invoice_response = self.client.get(reverse("invoice_center_api"), {"store": self.other_store.external_id})
        self.assertEqual(invoice_response.status_code, 200)
        self.assertEqual(invoice_response.json()["data"]["pagination"]["count"], 0)
        invoice_response = self.client.get(reverse("invoice_center_api"))
        self.assertEqual(invoice_response.json()["data"]["rows"][0]["id"], own_invoice.pk)

        message_response = self.client.get(reverse("message_center_api"))
        self.assertEqual(message_response.json()["data"]["rows"][0]["id"], own_message.pk)
        self.assertEqual(self.client.get(reverse("ai_knowledge_detail", args=["product", own_product.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("ai_knowledge_detail", args=["product", other_product.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("ai_knowledge_list", args=["customer"])).status_code, 403)

    def test_client_dashboard_aggregates_only_own_store_data(self):
        StoreMetric.objects.create(
            store=self.store,
            pending_after_sales=7,
            pending_tickets=3,
            today_order_count=21,
            consultation_count=34,
        )
        StoreMetric.objects.create(
            store=self.other_store,
            pending_after_sales=90,
            pending_tickets=80,
            today_order_count=70,
            consultation_count=60,
        )
        StoreAccount.objects.create(
            store=self.store, name="客服 A", login_account="client-a-1",
            login_password="secret", account_type=StoreAccount.AccountType.HUMAN,
        )
        StoreAccount.objects.create(
            store=self.other_store, name="客服 B", login_account="client-b-1",
            login_password="secret", account_type=StoreAccount.AccountType.HUMAN,
        )

        self.client.force_login(self.client_user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/client_dashboard.html")
        self.assertEqual(response.context["store_count"], 1)
        self.assertEqual(response.context["account_count"], 1)
        self.assertEqual(response.context["pending_after_sales"], 7)
        self.assertEqual(response.context["pending_tickets"], 3)
        self.assertEqual(response.context["today_order_count"], 21)
        self.assertEqual(response.context["consultation_count"], 34)

    def test_invoice_external_interfaces_and_retry(self):
        response = self.client.post(reverse("api_invoice_upload"), data={
            "store_id": self.store.external_id,
            "platform": "pdd",
            "order_no": "pdd-order-1",
            "title_type": "企业",
            "company_subject": "客户甲公司",
            "invoice_title": "客户甲公司",
            "taxpayer_id": "tax-001",
            "product_name": "商品 A",
            "quantity": "2",
            "amount": "19.90",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        invoice = InvoiceRecord.objects.get(order_no="pdd-order-1")
        self.assertEqual(invoice.status, InvoiceRecord.Status.PENDING)
        selected_date = invoice.created_at.astimezone().date().isoformat()
        response = self.client.get(reverse("api_invoice_pending"), {"date": selected_date})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["store_id"], self.store.external_id)
        self.assertEqual(response.json()["data"][0]["order_no"], invoice.order_no)

        response = self.client.post(reverse("api_invoice_status_update"), data={"items": [{
            "store_id": self.store.external_id, "platform": "pdd", "order_no": invoice.order_no, "status": "failed",
        }]}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceRecord.Status.FAILED)
        self.client.force_login(self.client_user)
        response = self.client.post(reverse("invoice_retry", args=[invoice.pk]))
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceRecord.Status.PENDING)

    def test_message_create_quick_reply_and_external_interfaces(self):
        self.client.force_login(self.client_user)
        response = self.client.post(reverse("message_center"), {
            "store_id": self.store.pk, "order_no": "message-001", "reply_content": "您好，已登记。", "save_quick_reply": "on",
        })
        self.assertEqual(response.status_code, 302)
        task = MessageTask.objects.get(order_no="message-001")
        self.assertEqual(task.created_by, self.client_user)
        self.assertTrue(QuickReply.objects.filter(customer=self.customer, content=task.reply_content).exists())

        self.client.logout()
        response = self.client.get(reverse("api_message_pending"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["order_no"], task.order_no)
        response = self.client.post(reverse("api_message_status_update"), data={"items": [{
            "store_id": self.store.external_id, "platform": "pdd", "order_no": task.order_no, "status": "success",
        }]}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, MessageTask.Status.SUCCESS)

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def calculate_pdd_timeout_count(consultation_count, three_minute_reply_rate):
    """Return the PDD derived timeout count, or ``None`` when the rate is unavailable."""
    try:
        total = max(Decimal(str(consultation_count or 0)), Decimal("0"))
        reply_rate = Decimal(str(three_minute_reply_rate))
    except (InvalidOperation, TypeError, ValueError):
        return None

    # The stored rate is expressed as a percentage, such as 98.50 for 98.5%.
    reply_rate = min(max(reply_rate, Decimal("0")), Decimal("100"))
    return int(
        (total * (Decimal("100") - reply_rate) / Decimal("100")).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


class PddTimeoutFormulaMixin:
    """Keep PDD timeout metrics derived from consultations and the human reply rate."""

    def apply_pdd_timeout_formula(self):
        if not self.store_id or self.store.platform != Store.Platform.PDD:
            return False
        timeout_count = calculate_pdd_timeout_count(
            self.consultation_count, self.three_minute_reply_rate
        )
        self.timeout_count = timeout_count
        self.robot_timeout_count = timeout_count
        return True

    def save(self, *args, **kwargs):
        formula_applied = self.apply_pdd_timeout_formula()
        update_fields = kwargs.get("update_fields")
        if formula_applied and update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "timeout_count",
                "robot_timeout_count",
            }
        return super().save(*args, **kwargs)


class User(AbstractUser):
    """平台用户；用户名由 AbstractUser 保证唯一。"""

    responsible_name = models.CharField("负责人姓名", max_length=50)
    customer = models.OneToOneField(
        "Customer",
        verbose_name="所属客户",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="portal_user",
        help_text="客户登录账号仅可绑定一个客户；为空表示内部账号。",
    )
    # None 表示尚未设置，数据管理员首次进入时使用默认列；空列表表示主动隐藏全部可选列。
    store_data_visible_fields = models.JSONField("店铺数据中心可见字段", null=True, blank=True, default=None)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"
        permissions = [
            ("can_manage_permissions", "可管理权限中心"),
            ("can_view_customer_performance", "可查看客服绩效和月度回复"),
            ("can_view_own_monthly_replies", "可查看自己的月度回复"),
        ]

    def __str__(self):
        return self.username


class Customer(models.Model):
    name = models.CharField("客户名称", max_length=100, unique=True)
    is_active = models.BooleanField("启用", default=True)
    # None uses the safe default columns.  An empty list is an intentional
    # choice to hide every optional data-center metric from this customer.
    store_data_visible_fields = models.JSONField(
        "客户店铺数据中心可见字段", null=True, blank=True, default=None
    )
    allow_store_knowledge_view = models.BooleanField("允许查看店铺知识库", default=False)
    allow_product_knowledge_view = models.BooleanField("允许查看商品知识库", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "客户"
        verbose_name_plural = "客户"
        ordering = ["name"]
        permissions = [
            ("can_manage_clients", "可新增、修改、禁用和删除客户"),
        ]

    def __str__(self):
        return self.name


class Store(models.Model):
    class Platform(models.TextChoices):
        PDD = "pdd", "拼多多"
        DOUYIN = "douyin", "抖音"
        JINGDONG = "jingdong", "京东"

    class CookieStatus(models.TextChoices):
        VALID = "valid", "有效"
        INVALID = "invalid", "失效"
        DISABLED = "disabled", "禁用"

    platform = models.CharField("平台类型", max_length=20, choices=Platform.choices)
    name = models.CharField("店铺名", max_length=150)
    external_id = models.CharField("店铺编号", max_length=100)
    customer = models.ForeignKey(Customer, verbose_name="所属客户", null=True, blank=True, on_delete=models.CASCADE, related_name="stores")
    main_category = models.CharField("主营类目", max_length=100, default="notfind")
    cookie = models.TextField("Cookie", blank=True)
    cookie_status = models.CharField("Cookie 状态", max_length=12, choices=CookieStatus.choices, default=CookieStatus.VALID)
    cookie_updated_at = models.DateTimeField("Cookie 上次更新时间", auto_now=True)
    robot_cookie = models.TextField("机器人 Cookie", blank=True)
    robot_cookie_updated_at = models.DateTimeField("机器人 Cookie 上次更新时间", auto_now=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="负责人", null=True, blank=True, on_delete=models.SET_NULL, related_name="responsible_stores")
    # 店铺可按内容类型阻断其所属客户的通用知识；材质知识只由商品标注决定，不受这里影响。
    block_customer_prompts = models.BooleanField("屏蔽客户特殊提示词", default=False)
    block_customer_qas = models.BooleanField("屏蔽客户问答对", default=False)
    block_customer_keywords = models.BooleanField("屏蔽客户关键词", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "店铺"
        verbose_name_plural = "店铺"
        ordering = ["-cookie_updated_at"]
        constraints = [models.UniqueConstraint(fields=["platform", "external_id"], name="unique_platform_store_id")]
        permissions = [
            ("can_delete_cookie", "可删除 Cookie"),
            ("can_view_all_store_data", "可查看全部店铺数据"),
        ]

    def __str__(self):
        return f"{self.get_platform_display()} · {self.name} ({self.external_id})"

    @property
    def is_unowned(self):
        return not self.shift_claims.filter(shift=StoreShiftClaim.Shift.MORNING).exists() or not self.shift_claims.filter(shift=StoreShiftClaim.Shift.EVENING).exists()

    @property
    def morning_claim(self):
        return next((claim for claim in self.shift_claims.all() if claim.shift == StoreShiftClaim.Shift.MORNING), None)

    @property
    def evening_claim(self):
        return next((claim for claim in self.shift_claims.all() if claim.shift == StoreShiftClaim.Shift.EVENING), None)


class PendingTask(models.Model):
    """由采集端写入、由店铺负责人处理的待办事项。"""

    class TimeType(models.TextChoices):
        NORMAL = "normal", "普通"
        URGENT = "urgent", "紧急"

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="pending_tasks")
    handling_item = models.CharField("处理事项", max_length=500)
    time_type = models.CharField("时间类型", max_length=10, choices=TimeType.choices, default=TimeType.NORMAL)
    is_processed = models.BooleanField("已处理", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    processed_at = models.DateTimeField("处理时间", null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="处理人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_pending_tasks",
    )

    class Meta:
        verbose_name = "待处理事务"
        verbose_name_plural = "待处理事务"
        ordering = ["-time_type", "created_at"]

    def __str__(self):
        return f"{self.store.name} · {self.handling_item}"


class StoreShiftClaim(models.Model):
    class Shift(models.TextChoices):
        MORNING = "morning", "早班"
        EVENING = "evening", "晚班"

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="shift_claims")
    shift = models.CharField("班次", max_length=10, choices=Shift.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="领取人", on_delete=models.CASCADE, related_name="store_claims")
    # 删除客户时，随其店铺一并清理该客户下的全部认领和账号数据。
    customer = models.ForeignKey(Customer, verbose_name="认领时所属客户", on_delete=models.CASCADE, related_name="shift_claims")
    claimed_at = models.DateTimeField("领取时间", auto_now_add=True)

    class Meta:
        verbose_name = "店铺班次认领"
        verbose_name_plural = "店铺班次认领"
        constraints = [models.UniqueConstraint(fields=["store", "shift"], name="one_claim_per_store_shift")]

    def __str__(self):
        return f"{self.store} - {self.get_shift_display()}"


class StoreMetric(PddTimeoutFormulaMixin, models.Model):
    """一店一份最新指标；采集接口以覆盖方式更新时间。"""

    store = models.OneToOneField(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="metrics")
    consultation_count = models.PositiveIntegerField("咨询数", default=0, null=True, blank=True)
    specialist_reply_count = models.PositiveIntegerField("专员回复数量", default=0, null=True, blank=True)
    three_minute_reply_rate = models.DecimalField("专员3分钟回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True, validators=[MinValueValidator(0)])
    timeout_count = models.PositiveIntegerField("专员超时数量", default=0, null=True, blank=True)
    average_response_seconds = models.DecimalField("专员昨日平均响应（秒）", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    pending_after_sales = models.PositiveIntegerField("待处理售后数量", default=0, null=True, blank=True)
    pending_tickets = models.PositiveIntegerField("待处理工单数量", default=0, null=True, blank=True)
    today_order_count = models.PositiveIntegerField("今日订单数", default=0, null=True, blank=True)
    today_turnover = models.DecimalField("今日营业金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    today_ad_spend = models.DecimalField("今日广告金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    store_experience_score = models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    service_experience_score = models.DecimalField("服务体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_completed_reply_count = models.PositiveIntegerField("机器人完结回复数量", default=0, null=True, blank=True)
    robot_completed_reply_rate = models.DecimalField("机器人完结回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_transferred_count = models.PositiveIntegerField("机器人转出数量", default=0, null=True, blank=True)
    robot_timeout_count = models.PositiveIntegerField("机器人超时数量", default=0, null=True, blank=True)
    robot_three_minute_reply_rate = models.DecimalField("机器人3分钟回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True, validators=[MinValueValidator(0)])
    metric_display_values = models.JSONField("指标文字展示值", default=dict, blank=True)
    data_updated_at = models.DateTimeField("数据更新时间", auto_now=True)

    class Meta:
        verbose_name = "店铺数据"
        verbose_name_plural = "店铺数据"


class StoreMetricSnapshot(PddTimeoutFormulaMixin, models.Model):
    """每个店铺每天每小时一份累计指标，供历史数据和绩效计算使用。"""

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="metric_snapshots")
    report_date = models.DateField("统计日期")
    report_hour = models.PositiveSmallIntegerField("统计小时")
    consultation_count = models.PositiveIntegerField("咨询数", default=0, null=True, blank=True)
    specialist_reply_count = models.PositiveIntegerField("专员回复数量", default=0, null=True, blank=True)
    three_minute_reply_rate = models.DecimalField("专员3分钟回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    timeout_count = models.PositiveIntegerField("专员超时数量", default=0, null=True, blank=True)
    average_response_seconds = models.DecimalField("专员昨日平均响应（秒）", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    pending_after_sales = models.PositiveIntegerField("待处理售后数量", default=0, null=True, blank=True)
    pending_tickets = models.PositiveIntegerField("待处理工单数量", default=0, null=True, blank=True)
    today_order_count = models.PositiveIntegerField("今日订单数", default=0, null=True, blank=True)
    today_turnover = models.DecimalField("今日营业金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    today_ad_spend = models.DecimalField("今日广告金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    store_experience_score = models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    service_experience_score = models.DecimalField("服务体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_completed_reply_count = models.PositiveIntegerField("机器人完结回复数量", default=0, null=True, blank=True)
    robot_completed_reply_rate = models.DecimalField("机器人完结回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_transferred_count = models.PositiveIntegerField("机器人转出数量", default=0, null=True, blank=True)
    robot_timeout_count = models.PositiveIntegerField("机器人超时数量", default=0, null=True, blank=True)
    robot_three_minute_reply_rate = models.DecimalField("机器人3分钟回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    metric_display_values = models.JSONField("指标文字展示值", default=dict, blank=True)
    reported_at = models.DateTimeField("上报时间", auto_now=True)

    class Meta:
        verbose_name = "店铺小时数据快照"
        verbose_name_plural = "店铺小时数据快照"
        ordering = ["-report_date", "-report_hour"]
        constraints = [models.UniqueConstraint(fields=["store", "report_date", "report_hour"], name="one_snapshot_per_store_hour")]

    @property
    def data_updated_at(self):
        return self.reported_at


class ShiftDailySummary(models.Model):
    """通过班次总结接口写入的日汇总，作为月度回复的事实来源。"""

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="daily_summaries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="客服", on_delete=models.SET_NULL, null=True, related_name="daily_shift_summaries")
    shift = models.CharField("班次", max_length=10, choices=StoreShiftClaim.Shift.choices)
    summary_date = models.DateField("总结日期")
    consultation_count = models.PositiveIntegerField("专员回复数量", default=0, null=True, blank=True)
    three_minute_reply_rate = models.DecimalField("专员3分钟回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    timeout_count = models.PositiveIntegerField("专员超时数量", default=0, null=True, blank=True)
    average_response_seconds = models.DecimalField("专员昨日平均响应（秒）", max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    pending_after_sales = models.PositiveIntegerField("待处理售后数量", default=0, null=True, blank=True)
    pending_tickets = models.PositiveIntegerField("待处理工单数量", default=0, null=True, blank=True)
    today_order_count = models.PositiveIntegerField("今日订单数", default=0, null=True, blank=True)
    today_turnover = models.DecimalField("今日营业金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    today_ad_spend = models.DecimalField("今日广告金额", max_digits=14, decimal_places=2, default=0, null=True, blank=True)
    store_experience_score = models.DecimalField("店铺体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    service_experience_score = models.DecimalField("服务体验分", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_completed_reply_count = models.PositiveIntegerField("机器人完结回复数量", default=0, null=True, blank=True)
    robot_completed_reply_rate = models.DecimalField("机器人完结回复率", max_digits=6, decimal_places=2, default=0, null=True, blank=True)
    robot_transferred_count = models.PositiveIntegerField("机器人转出数量", default=0, null=True, blank=True)
    metric_display_values = models.JSONField("指标文字展示值", default=dict, blank=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "客服班次日总结"
        verbose_name_plural = "客服班次日总结"
        ordering = ["-summary_date", "shift"]
        constraints = [models.UniqueConstraint(fields=["store", "summary_date", "shift"], name="one_shift_summary_per_store_day")]


class StoreAccount(models.Model):
    class AccountType(models.TextChoices):
        HUMAN = "human", "专员账号"
        BOT = "bot", "机器人账号"

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField("账号名", max_length=100)
    login_account = models.CharField("登录账号", max_length=100)
    login_password = models.CharField("登录密码", max_length=255)
    corresponding_port = models.CharField("对应端口", max_length=30, blank=True)
    phone = models.CharField("所属手机号", max_length=30, blank=True)
    account_type = models.CharField("账号类型", max_length=10, choices=AccountType.choices)
    external_id = models.CharField("账号 ID", max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="创建人", null=True, blank=True, on_delete=models.SET_NULL, related_name="created_store_accounts")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "店铺账号"
        verbose_name_plural = "店铺账号"
        constraints = [models.UniqueConstraint(fields=["store", "name", "account_type"], name="unique_account_name_type_per_store")]
        permissions = [
            ("can_manage_all_accounts", "可管理所有店铺账号"),
        ]

    def __str__(self):
        return f"{self.store.name} · {self.name}"


class AccountPasswordRegistration(models.Model):
    """独立的账号密码登记表，不与店铺、客户或现有账号建立关联。"""

    class AccountType(models.TextChoices):
        SPECIALIST = "specialist", "专员账号"
        ROBOT = "robot", "机器人账号"

    shop_name = models.CharField("店铺名", max_length=150, blank=True, default="")
    platform = models.CharField("平台", max_length=100, blank=True, default="拼多多")
    account_name = models.CharField("账号名", max_length=100, blank=True, default="")
    account_type = models.CharField(
        "账号类型", max_length=20, choices=AccountType.choices,
        default=AccountType.SPECIALIST,
    )
    login_account = models.CharField("登录账号", max_length=100, blank=True, default="")
    login_password = models.CharField("登录密码", max_length=255, blank=True, default="")
    phone = models.CharField("手机号", max_length=30, blank=True, default="")
    responsible_1 = models.CharField("负责人 1", max_length=100, blank=True, default="")
    responsible_2 = models.CharField("负责人 2", max_length=100, blank=True, default="")
    customer = models.CharField("客户", max_length=100, blank=True, default="")
    specialist_account = models.CharField("专员账号", max_length=100, blank=True, default="")
    robot_account = models.CharField("机器人账号", max_length=100, blank=True, default="")
    remarks = models.TextField("备注", blank=True, default="")
    operator_name = models.CharField("操作人", max_length=100, blank=True, default="")
    created_at = models.DateTimeField("添加时间", auto_now_add=True)

    class Meta:
        verbose_name = "账号密码登记"
        verbose_name_plural = "账号密码登记"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.account_name or self.login_account or self.shop_name or f"登记 #{self.pk}"


class ImageTextRegistration(models.Model):
    """外部接口写入的图片与对应文字，供登记表格统一查看和维护。"""

    image_url = models.URLField("图片链接", max_length=1000)
    content = models.TextField("对应文字")
    created_at = models.DateTimeField("添加时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "图片对应文字"
        verbose_name_plural = "图片对应文字"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.content[:50] or f"图片文字 #{self.pk}"


class StoreAfterSalesStrategy(models.Model):
    """按已登记 Cookie 的店铺保存售后协商和补偿策略。"""

    class CompensationType(models.TextChoices):
        RATIO = "ratio", "补偿比例"
        AMOUNT = "amount", "补偿金额"

    class CompensationStageCount(models.IntegerChoices):
        ONE = 1, "1 阶"
        TWO = 2, "2 阶"
        THREE = 3, "3 阶"

    store = models.OneToOneField(
        Store,
        verbose_name="店铺",
        on_delete=models.CASCADE,
        related_name="after_sales_strategy",
    )
    compensation_type = models.CharField(
        "补偿类型", max_length=10, choices=CompensationType.choices,
        default=CompensationType.RATIO,
    )
    compensation_count = models.PositiveSmallIntegerField("补偿", default=0)
    replacement_count = models.PositiveSmallIntegerField("补发", default=0)
    refund_count = models.PositiveSmallIntegerField("退款", default=0)
    compensation_stage_count = models.PositiveSmallIntegerField(
        "补偿阶数", choices=CompensationStageCount.choices,
        default=CompensationStageCount.ONE,
    )
    compensation_minimum = models.DecimalField(
        "补偿下限", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    compensation_maximum = models.DecimalField(
        "补偿上限", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    warranty_days = models.PositiveSmallIntegerField("质保时间（天）", default=0)
    first_compensation = models.DecimalField(
        "第一次补偿", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    second_compensation = models.DecimalField(
        "第二次补偿", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    third_compensation = models.DecimalField(
        "第三次补偿", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField("设置时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "店铺售后策略"
        verbose_name_plural = "店铺售后策略"
        ordering = ["store__name"]

    def clean(self):
        if self.compensation_minimum > self.compensation_maximum:
            raise ValidationError({"compensation_minimum": "补偿下限不能大于补偿上限。"})
        if self.compensation_type == self.CompensationType.RATIO:
            ratio_fields = ("first_compensation", "second_compensation", "third_compensation")
            for field_name in ratio_fields:
                if getattr(self, field_name) > 100:
                    raise ValidationError({field_name: "补偿比例不能大于 100%。"})

    def __str__(self):
        return f"{self.store.name} 售后策略"


class InvoiceRecord(models.Model):
    """Invoices crawled from a platform and later consumed by an external service."""

    class Status(models.TextChoices):
        PENDING = "pending", "未处理"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="invoices")
    order_no = models.CharField("订单号", max_length=150)
    title_type = models.CharField("抬头类型", max_length=80, blank=True, default="")
    company_subject = models.CharField("公司主体", max_length=200, blank=True, default="")
    platform = models.CharField("平台", max_length=50, blank=True, default="")
    invoice_title = models.CharField("发票抬头", max_length=300, blank=True, default="")
    taxpayer_id = models.CharField("纳税识别号", max_length=100, blank=True, default="")
    product_name = models.CharField("商品名称", max_length=500, blank=True, default="")
    quantity = models.DecimalField("数量", max_digits=12, decimal_places=2, default=Decimal("0"))
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2, default=Decimal("0"))
    status = models.CharField("处理状态", max_length=12, choices=Status.choices, default=Status.PENDING)
    pdf_file = models.FileField("PDF 发票", upload_to="invoices/%Y/%m/", blank=True, null=True)
    created_at = models.DateTimeField("上传时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    processed_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        verbose_name = "发票"
        verbose_name_plural = "发票"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="invoice_status_created_idx"),
            models.Index(fields=["store", "order_no"], name="invoice_store_order_idx"),
        ]

    def __str__(self):
        return f"{self.store.name} · {self.order_no}"


class QuickReply(models.Model):
    """Customer-scoped snippets shared by that customer's client accounts."""

    customer = models.ForeignKey(Customer, verbose_name="客户", on_delete=models.CASCADE, related_name="quick_replies")
    content = models.TextField("快捷回复话术")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建账号",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_quick_replies",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "快捷回复话术"
        verbose_name_plural = "快捷回复话术"
        ordering = ["customer__name", "content"]

    def __str__(self):
        return self.content[:50]


class MessageTask(models.Model):
    """A manually registered post-sales message task."""

    class Status(models.TextChoices):
        PENDING = "pending", "未处理"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="message_tasks")
    order_no = models.CharField("订单号", max_length=150)
    reply_content = models.TextField("回复话术")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="登记账号",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_message_tasks",
    )
    status = models.CharField("处理状态", max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField("录用时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    processed_at = models.DateTimeField("处理时间", null=True, blank=True)

    class Meta:
        verbose_name = "留言任务"
        verbose_name_plural = "留言任务"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="message_status_created_idx"),
            models.Index(fields=["store", "order_no"], name="message_store_order_idx"),
        ]

    def __str__(self):
        return f"{self.store.name} · {self.order_no}"


class WeChatPendingGroup(models.Model):
    """The single shared WeChat queue used by the external sending program."""

    key = models.CharField("队列标识", max_length=50, unique=True, default="pending-wechat-group")
    name = models.CharField("群名称", max_length=100, default="微信群待发送")
    content = models.TextField("待发送信息", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "微信群待发送队列"
        verbose_name_plural = "微信群待发送队列"

    def __str__(self):
        return self.name


class RemoteRegistration(models.Model):
    """Remote-control credentials entered by internal specialists and administrators."""

    machine_no = models.CharField("机器号", max_length=100)
    remote_code = models.CharField("远程码", max_length=100)
    remote_password = models.CharField("远程密码", max_length=255)
    operator_name = models.CharField("登记人", max_length=100)
    created_at = models.DateTimeField("登记时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "远程登记"
        verbose_name_plural = "远程登记"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.machine_no


# ----------------------------- AI 知识库 -----------------------------


class KnowledgeScene(models.TextChoices):
    GENERAL = "general", "通用"
    PRESALE = "presale", "售前"
    AFTERSALE = "aftersale", "售后"


class CustomerMaterial(models.Model):
    """客户可维护的材质标签；一个商品最多关联其中一个标签。"""

    customer = models.ForeignKey(Customer, verbose_name="客户", on_delete=models.CASCADE, related_name="materials")
    name = models.CharField("材质名称", max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_customer_materials",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "客户素材（材质）"
        verbose_name_plural = "客户素材（材质）"
        ordering = ["customer__name", "name"]
        constraints = [models.UniqueConstraint(fields=["customer", "name"], name="unique_material_per_customer")]

    def __str__(self):
        return f"{self.customer.name} · {self.name}"


class Product(models.Model):
    """以哈基米平台商品上传结构原样保存的商品资料。"""

    store = models.ForeignKey(Store, verbose_name="店铺", on_delete=models.CASCADE, related_name="products")
    goods_id = models.CharField("商品号", max_length=100)
    payload = models.JSONField("商品原始数据", default=dict)
    material = models.ForeignKey(
        CustomerMaterial,
        verbose_name="标注材质",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="入库人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_products",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    knowledge_heat = models.PositiveIntegerField("知识库热度", default=0, db_index=True)

    class Meta:
        verbose_name = "商品资料"
        verbose_name_plural = "商品资料"
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["store", "goods_id"], name="unique_goods_per_store")]
        permissions = [
            ("can_delete_product_from_knowledge", "可从商品知识库删除商品"),
        ]

    def clean(self):
        if self.material_id and self.store_id and self.store.customer_id != self.material.customer_id:
            from django.core.exceptions import ValidationError

            raise ValidationError({"material": "商品材质必须属于该店铺的所属客户。"})

    def __str__(self):
        return f"{self.store.name} · {self.goods_id}"


class ProductFavorite(models.Model):
    """用户个人收藏的商品，不影响商品本身或其他账号的收藏状态。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="收藏账号",
        on_delete=models.CASCADE,
        related_name="product_favorites",
    )
    product = models.ForeignKey(
        Product,
        verbose_name="收藏商品",
        on_delete=models.CASCADE,
        related_name="favorite_records",
    )
    created_at = models.DateTimeField("收藏时间", auto_now_add=True)

    class Meta:
        verbose_name = "商品收藏"
        verbose_name_plural = "商品收藏"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_user_product_favorite"),
        ]

    def __str__(self):
        return f"{self.user.username} · {self.product}"


class OrderUrgingScript(models.Model):
    """Customer, store, or product-level order-urging scripts."""

    customer = models.ForeignKey(
        Customer,
        verbose_name="所属客户",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="order_urging_scripts",
    )
    store = models.ForeignKey(
        Store,
        verbose_name="所属店铺",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="order_urging_scripts",
    )
    product = models.ForeignKey(
        Product,
        verbose_name="所属商品",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="order_urging_scripts",
    )
    pending_payment = models.TextField("待支付催单话术", blank=True, default="")
    unplaced_order = models.TextField("未下单催单话术", blank=True, default="")
    block_parent_pending_payment = models.BooleanField("屏蔽上级待支付话术", default=False)
    block_parent_unplaced_order = models.BooleanField("屏蔽上级未下单话术", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "催单话术"
        verbose_name_plural = "催单话术"
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(customer__isnull=False),
                name="unique_customer_order_urging_script",
            ),
            models.UniqueConstraint(
                fields=["store"],
                condition=Q(store__isnull=False),
                name="unique_store_order_urging_script",
            ),
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(product__isnull=False),
                name="unique_product_order_urging_script",
            ),
        ]

    def clean(self):
        if sum(bool(value) for value in (self.customer_id, self.store_id, self.product_id)) != 1:
            raise ValidationError("催单话术必须且只能归属客户、店铺或商品中的一个。")

    @property
    def scope_type(self):
        for name in ("customer", "store", "product"):
            if getattr(self, f"{name}_id"):
                return name
        return ""

    def __str__(self):
        return f"{self.get_scope_display()}催单话术"

    def get_scope_display(self):
        return {"customer": "客户", "store": "店铺", "product": "商品"}.get(self.scope_type, "")


class ProductMaterialInheritanceBlock(models.Model):
    """A product-level switch that prevents every entry from one customer material being inherited."""

    product = models.ForeignKey(
        Product,
        verbose_name="屏蔽目标商品",
        on_delete=models.CASCADE,
        related_name="material_inheritance_blocks",
    )
    material = models.ForeignKey(
        CustomerMaterial,
        verbose_name="被屏蔽客户素材",
        on_delete=models.CASCADE,
        related_name="product_inheritance_blocks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "商品客户素材整项屏蔽"
        verbose_name_plural = "商品客户素材整项屏蔽"
        constraints = [
            models.UniqueConstraint(fields=["product", "material"], name="unique_product_material_inheritance_block"),
        ]

    def clean(self):
        if (
            self.product_id
            and self.material_id
            and self.product.store.customer_id != self.material.customer_id
        ):
            raise ValidationError("只能屏蔽商品所属客户下的客户素材。")

    def __str__(self):
        return f"{self.product} · 屏蔽 {self.material}"


class ScopedKnowledgeBase(models.Model):
    """客户、店铺、商品、材质四层知识内容的公共归属字段。"""

    scene = models.CharField("适用场景", max_length=12, choices=KnowledgeScene.choices, default=KnowledgeScene.GENERAL)
    is_active = models.BooleanField("启用", default=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.CASCADE)
    material = models.ForeignKey(CustomerMaterial, null=True, blank=True, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["scene", "-updated_at"]

    def clean(self):
        if sum(bool(value) for value in (self.customer_id, self.store_id, self.product_id, self.material_id)) != 1:
            from django.core.exceptions import ValidationError

            raise ValidationError("知识内容必须且只能归属客户、店铺、商品或材质中的一个。")

    @property
    def scope_type(self):
        for name in ("customer", "store", "product", "material"):
            if getattr(self, f"{name}_id"):
                return name
        return ""


class AIKnowledgePrompt(ScopedKnowledgeBase):
    content = models.TextField("特殊提示词")

    class Meta(ScopedKnowledgeBase.Meta):
        verbose_name = "AI 特殊提示词"
        verbose_name_plural = "AI 特殊提示词"
        constraints = [
            models.UniqueConstraint(fields=["customer", "scene"], condition=Q(customer__isnull=False), name="unique_customer_prompt_scene"),
            models.UniqueConstraint(fields=["store", "scene"], condition=Q(store__isnull=False), name="unique_store_prompt_scene"),
            models.UniqueConstraint(fields=["product", "scene"], condition=Q(product__isnull=False), name="unique_product_prompt_scene"),
            models.UniqueConstraint(fields=["material", "scene"], condition=Q(material__isnull=False), name="unique_material_prompt_scene"),
        ]


class AIKnowledgeQA(ScopedKnowledgeBase):
    question = models.TextField("问题")
    answer = models.TextField("回答")

    class Meta(ScopedKnowledgeBase.Meta):
        verbose_name = "AI 问答对"
        verbose_name_plural = "AI 问答对"


class AIKnowledgeKeyword(ScopedKnowledgeBase):
    class MatchType(models.TextChoices):
        EXACT = "exact", "完全一样"
        CONTAINS = "contains", "包含"

    keyword = models.CharField("关键词", max_length=255)
    answer = models.TextField("关键词回答", blank=True, default="")
    match_type = models.CharField("匹配方式", max_length=12, choices=MatchType.choices, default=MatchType.CONTAINS)

    class Meta(ScopedKnowledgeBase.Meta):
        verbose_name = "AI 关键词"
        verbose_name_plural = "AI 关键词"


class ScopedKnowledgeInheritanceBlock(models.Model):
    """一条继承知识在店铺或商品层面的屏蔽记录。"""

    store = models.ForeignKey(
        Store,
        verbose_name="屏蔽目标店铺",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="%(class)s_store_blocks",
    )
    product = models.ForeignKey(
        Product,
        verbose_name="屏蔽目标商品",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="%(class)s_product_blocks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作人",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        abstract = True

    def clean(self):
        if bool(self.store_id) == bool(self.product_id):
            from django.core.exceptions import ValidationError

            raise ValidationError("屏蔽规则只能归属一个店铺或一个商品。")

    @property
    def target_scope(self):
        return "store" if self.store_id else "product"


class AIKnowledgePromptBlock(ScopedKnowledgeInheritanceBlock):
    prompt = models.ForeignKey(AIKnowledgePrompt, verbose_name="被屏蔽提示词", on_delete=models.CASCADE, related_name="inheritance_blocks")

    class Meta:
        verbose_name = "AI 提示词继承屏蔽"
        verbose_name_plural = "AI 提示词继承屏蔽"
        constraints = [
            models.UniqueConstraint(fields=["store", "prompt"], condition=Q(store__isnull=False), name="unique_store_prompt_block"),
            models.UniqueConstraint(fields=["product", "prompt"], condition=Q(product__isnull=False), name="unique_product_prompt_block"),
        ]


class AIKnowledgeQABlock(ScopedKnowledgeInheritanceBlock):
    qa = models.ForeignKey(AIKnowledgeQA, verbose_name="被屏蔽问答对", on_delete=models.CASCADE, related_name="inheritance_blocks")

    class Meta:
        verbose_name = "AI 问答对继承屏蔽"
        verbose_name_plural = "AI 问答对继承屏蔽"
        constraints = [
            models.UniqueConstraint(fields=["store", "qa"], condition=Q(store__isnull=False), name="unique_store_qa_block"),
            models.UniqueConstraint(fields=["product", "qa"], condition=Q(product__isnull=False), name="unique_product_qa_block"),
        ]


class AIKnowledgeKeywordBlock(ScopedKnowledgeInheritanceBlock):
    keyword = models.ForeignKey(AIKnowledgeKeyword, verbose_name="被屏蔽关键词", on_delete=models.CASCADE, related_name="inheritance_blocks")

    class Meta:
        verbose_name = "AI 关键词继承屏蔽"
        verbose_name_plural = "AI 关键词继承屏蔽"
        constraints = [
            models.UniqueConstraint(fields=["store", "keyword"], condition=Q(store__isnull=False), name="unique_store_keyword_block"),
            models.UniqueConstraint(fields=["product", "keyword"], condition=Q(product__isnull=False), name="unique_product_keyword_block"),
        ]

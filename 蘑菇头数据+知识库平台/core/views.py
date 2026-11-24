import json
import random
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Subquery, Sum
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import (
    AccountPasswordRegistrationForm,
    CustomerForm,
    ImageTextRegistrationForm,
    RegisterForm,
    RemoteRegistrationForm,
    StoreAccountForm,
    StoreAfterSalesStrategyForm,
    VisiblePasswordChangeForm,
)
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
    KnowledgeScene,
    PendingTask,
    Product,
    ProductFavorite,
    ProductMaterialInheritanceBlock,
    OrderUrgingScript,
    MessageTask,
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


PLATFORM_ALIASES = {
    "pdd": Store.Platform.PDD,
    "拼多多": Store.Platform.PDD,
    "douyin": Store.Platform.DOUYIN,
    "抖音": Store.Platform.DOUYIN,
    "jingdong": Store.Platform.JINGDONG,
    "京东": Store.Platform.JINGDONG,
}
SHIFT_ALIASES = {"morning": StoreShiftClaim.Shift.MORNING, "早班": StoreShiftClaim.Shift.MORNING, "evening": StoreShiftClaim.Shift.EVENING, "晚班": StoreShiftClaim.Shift.EVENING}
PENDING_TASK_TIME_TYPE_ALIASES = {
    "normal": PendingTask.TimeType.NORMAL,
    "普通": PendingTask.TimeType.NORMAL,
    "urgent": PendingTask.TimeType.URGENT,
    "紧急": PendingTask.TimeType.URGENT,
}
KNOWLEDGE_SCENE_ALIASES = {
    "general": KnowledgeScene.GENERAL,
    "通用": KnowledgeScene.GENERAL,
    "presale": KnowledgeScene.PRESALE,
    "pre_sale": KnowledgeScene.PRESALE,
    "售前": KnowledgeScene.PRESALE,
    "aftersale": KnowledgeScene.AFTERSALE,
    "after_sale": KnowledgeScene.AFTERSALE,
    "售后": KnowledgeScene.AFTERSALE,
}
AI_KNOWLEDGE_SCOPES = {
    "customer": "客户知识库",
    "store": "店铺知识库",
    "product": "商品知识库",
    "material": "客户素材知识库",
}
AI_KNOWLEDGE_ENTRY_TYPES = {
    "prompt": {
        "label": "特殊提示词",
        "model": AIKnowledgePrompt,
        "block_model": AIKnowledgePromptBlock,
        "source_field": "prompt",
    },
    "qa": {
        "label": "问答对",
        "model": AIKnowledgeQA,
        "block_model": AIKnowledgeQABlock,
        "source_field": "qa",
    },
    "keyword": {
        "label": "关键词",
        "model": AIKnowledgeKeyword,
        "block_model": AIKnowledgeKeywordBlock,
        "source_field": "keyword",
    },
}

ORDER_URGING_FIELDS = (
    ("pending_payment", "待支付"),
    ("unplaced_order", "未下单"),
)

STORE_DATA_BASE_COLUMNS = (
    "specialist_reply_count",
    "three_minute_reply_rate",
    "timeout_count",
    "average_response_seconds",
    "robot_completed_reply_count",
    "robot_completed_reply_rate",
    "robot_transferred_count",
    "robot_timeout_count",
    "robot_three_minute_reply_rate",
    "consultation_count",
    "pending_after_sales",
    "pending_tickets",
    "customer",
    "data_updated_at",
)
STORE_DATA_ADMIN_COLUMNS = (
    "main_category",
    "today_order_count",
    "responsibles",
    "today_turnover",
    "today_ad_spend",
    "store_experience_score",
    "service_experience_score",
)
STORE_DATA_COLUMN_LABELS = {
    "consultation_count": "咨询数",
    "specialist_reply_count": "专员回复数量",
    "three_minute_reply_rate": "专员3分钟回复率",
    "timeout_count": "专员超时数量",
    "average_response_seconds": "平均响应",
    "pending_after_sales": "今日售后数量",
    "pending_tickets": "今日工单数量",
    "robot_completed_reply_count": "机器人完结回复",
    "robot_completed_reply_rate": "机器人完结率",
    "robot_transferred_count": "机器人转出",
    "robot_timeout_count": "机器人超时数量",
    "robot_three_minute_reply_rate": "机器人3分钟回复率",
    "customer": "所属客户",
    "data_updated_at": "更新时间",
    "main_category": "主营类目",
    "today_order_count": "今日订单",
    "responsibles": "负责人",
    "today_turnover": "营业金额",
    "today_ad_spend": "广告金额",
    "store_experience_score": "店铺体验分",
    "service_experience_score": "服务体验分",
}
STORE_DATA_ALL_COLUMNS = STORE_DATA_BASE_COLUMNS + STORE_DATA_ADMIN_COLUMNS
STORE_DATA_NUMERIC_COLUMNS = (
    "specialist_reply_count",
    "three_minute_reply_rate",
    "timeout_count",
    "average_response_seconds",
    "robot_completed_reply_count",
    "robot_completed_reply_rate",
    "robot_transferred_count",
    "robot_timeout_count",
    "robot_three_minute_reply_rate",
    "consultation_count",
    "pending_after_sales",
    "pending_tickets",
    "today_order_count",
    "today_turnover",
    "today_ad_spend",
    "store_experience_score",
    "service_experience_score",
)
STORE_DATA_TEXT_SORT_FIELDS = {
    "store_name": "name",
    "customer": "customer__name",
    "data_updated_at": "metrics__data_updated_at",
    "main_category": "main_category",
    "responsibles": "responsible__responsible_name",
}
STORE_DATA_SORT_COLUMNS = set(STORE_DATA_NUMERIC_COLUMNS) | set(STORE_DATA_TEXT_SORT_FIELDS)
STORE_DATA_METRIC_SUFFIXES = {
    "three_minute_reply_rate": "%",
    "average_response_seconds": " 秒",
    "robot_completed_reply_rate": "%",
    "robot_three_minute_reply_rate": "%",
    "today_turnover": " 元",
    "today_ad_spend": " 元",
}
CENTER_JSON_PAGE_SIZE = 35
WECHAT_PENDING_GROUP_KEY = "pending-wechat-group"
WECHAT_PENDING_GROUP_NAME = "微信群待发送"


def is_platform_admin(user):
    return user.is_superuser or user.is_staff


def is_customer_account(user):
    """A client portal account is explicitly linked to one Customer."""
    return bool(getattr(user, "customer_id", None))


def customer_stores(user):
    return Store.objects.filter(customer_id=user.customer_id) if is_customer_account(user) else Store.objects.none()


def can_view_all_after_sales(user):
    """Internal accounts are specialists unless they are platform administrators."""
    return not is_customer_account(user)


def can_manage_remote_registrations(user):
    """Remote credentials are available to all internal specialist and admin accounts."""
    return not is_customer_account(user)


def can_access_store(user, store):
    if is_customer_account(user):
        return store.customer_id == user.customer_id
    return can_view_all_after_sales(user) or StoreShiftClaim.objects.filter(store=store, user=user).exists()


def normalize_platform(value):
    return PLATFORM_ALIASES.get(str(value or "").strip().lower())


def normalize_shift(value):
    return SHIFT_ALIASES.get(str(value or "").strip().lower())


def normalize_pending_task_time_type(value):
    return PENDING_TASK_TIME_TYPE_ALIASES.get(str(value or "").strip().lower())


def paginate_center_queryset(queryset, request):
    """Paginate list-style management pages without loading every row into memory."""
    page_obj = Paginator(queryset, CENTER_JSON_PAGE_SIZE).get_page(request.GET.get("page", 1))
    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    return page_obj, list(page_obj.object_list), pagination_query.urlencode()


def pagination_json_data(page_obj):
    return {
        "count": page_obj.paginator.count,
        "number": page_obj.number,
        "num_pages": page_obj.paginator.num_pages,
        "has_previous": page_obj.has_previous(),
        "previous_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
        "has_next": page_obj.has_next(),
        "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
    }


def normalize_knowledge_scene(value):
    return KNOWLEDGE_SCENE_ALIASES.get(str(value or "").strip().lower())


def json_error(message, status=400):
    return JsonResponse({"ok": False, "message": message}, status=status)


def can_view_all_pending_tasks(user):
    return is_platform_admin(user) or user.has_perm("core.can_view_all_store_data")


def can_manage_all_cookies(user):
    """Cookie 超级管理员、数据管理员和平台管理员可以查看全部 Cookie。"""
    return is_platform_admin(user) or user.has_perm("core.can_delete_cookie") or user.has_perm("core.can_view_all_store_data")


def can_delete_ai_knowledge_product(user):
    return user.is_superuser or user.has_perm("core.can_delete_product_from_knowledge")


def pending_tasks_visible_to(user):
    tasks = PendingTask.objects.filter(is_processed=False).select_related("store")
    if not can_view_all_pending_tasks(user):
        tasks = tasks.filter(store__shift_claims__user=user).distinct()
    return tasks.order_by("-time_type", "created_at")


def format_elapsed_time(start_time):
    elapsed_seconds = max(0, int((timezone.now() - start_time).total_seconds()))
    if elapsed_seconds < 60:
        return f"{elapsed_seconds} 秒"
    minutes, _ = divmod(elapsed_seconds, 60)
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} 小时 {minutes} 分钟"
    days, hours = divmod(hours, 24)
    return f"{days} 天 {hours} 小时"


def pending_task_api_data(task):
    elapsed_seconds = max(0, int((timezone.now() - task.created_at).total_seconds()))
    return {
        "id": task.pk,
        "store_id": task.store_id,
        "shop_id": task.store.external_id,
        "shop_name": task.store.name,
        "platform": task.store.platform,
        "handling_item": task.handling_item,
        "time_type": task.time_type,
        "time_type_name": task.get_time_type_display(),
        "is_urgent": task.time_type == PendingTask.TimeType.URGENT,
        "created_at": task.created_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "elapsed_time": format_elapsed_time(task.created_at),
        "is_processed": task.is_processed,
    }


def page_not_found(request, exception):
    faces = ["(｡•́︿•̀｡)", "(；ω；)", "(>_<)", "(´；ω；｀)", "ฅ( ̳• ·̫ • ̳)ฅ"]
    return render(request, "404.html", {"face": random.choice(faces)}, status=404)


def customer_service_landing(request):
    """Public customer-service outsourcing landing page."""
    return render(request, "core/customer_service_landing.html")


def parse_json(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("请求体必须是合法 JSON")
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须为对象")
    return data


def get_customer_from_payload(data, required=False):
    customer_id = data.get("customer_id")
    customer_name = str(data.get("customer") or data.get("customer_name") or "").strip()
    if customer_id:
        try:
            return Customer.objects.get(pk=customer_id)
        except (Customer.DoesNotExist, ValueError, TypeError):
            raise ValueError("customer_id 不存在")
    if customer_name:
        try:
            return Customer.objects.get(name=customer_name)
        except Customer.DoesNotExist:
            raise ValueError("客户不存在，请先在客户统计表创建")
    if required:
        raise ValueError("必须提供 customer 或 customer_id")
    return None


def cookie_value(cookie, name):
    """Return a decoded Cookie value without assuming its attribute order."""
    match = re.search(
        rf"(?:^|;\s*){re.escape(name)}\s*=\s*([^;]*)",
        str(cookie or ""),
        flags=re.IGNORECASE,
    )
    return unquote(match.group(1).strip().strip('"')) if match else ""


def account_id_from_cookie(platform, cookie):
    """Extract the logged-in specialist account ID used by each platform."""
    if platform == Store.Platform.PDD:
        pass_id = cookie_value(cookie, "PASS_ID")
        match = re.search(r"_(\d+)$", pass_id)
        if not match:
            raise ValueError("拼多多 Cookie 中未找到格式正确的 PASS_ID 账号 ID")
        return match.group(1)
    if platform == Store.Platform.DOUYIN:
        pigeon_cid = cookie_value(cookie, "PIGEON_CID")
        if not re.fullmatch(r"\d+", pigeon_cid):
            raise ValueError("抖音 Cookie 中未找到格式正确的 PIGEON_CID 账号 ID")
        return pigeon_cid
    raise ValueError("仅支持从拼多多或抖音 Cookie 抓取账号 ID")


def matching_accounts_for_id_capture(account_name, shop_id="", platform=None, human_only=False):
    """Locate an account by its displayed name or actual login account."""
    accounts = StoreAccount.objects.select_related("store").filter(
        Q(name=account_name) | Q(login_account=account_name)
    )
    if shop_id:
        accounts = accounts.filter(store__external_id=shop_id)
    if platform:
        accounts = accounts.filter(store__platform=platform)
    if human_only:
        accounts = accounts.filter(account_type=StoreAccount.AccountType.HUMAN)
    return accounts


def capture_missing_human_account_id_from_cookie(cookie, account_name="", shop_id="", platform=None):
    """Fill one missing specialist ID from Cookie, without replacing an existing ID."""
    account_name = str(account_name or "").strip()
    if account_name:
        accounts = matching_accounts_for_id_capture(
            account_name, shop_id=shop_id, platform=platform, human_only=True
        )
    else:
        accounts = StoreAccount.objects.select_related("store").filter(
            account_type=StoreAccount.AccountType.HUMAN
        )
        if shop_id:
            accounts = accounts.filter(store__external_id=shop_id)
        if platform:
            accounts = accounts.filter(store__platform=platform)

    matched_accounts = list(accounts)
    if account_name and not matched_accounts:
        raise ValueError("未找到匹配的专员账号")
    missing_id_accounts = [account for account in matched_accounts if not account.external_id]
    if not missing_id_accounts:
        return None, None
    if len(missing_id_accounts) != 1:
        raise ValueError("匹配到多个未填写账号 ID 的专员账号，请传入 account_name 或 login_account")

    account = missing_id_accounts[0]
    account_id = account_id_from_cookie(account.store.platform, cookie)
    account.external_id = account_id
    account.save(update_fields=["external_id"])
    return account, account_id


def backfill_missing_human_account_ids(stores):
    """Fill historical blank specialist IDs from the Cookie already saved for each store."""
    candidate_stores = stores.filter(
        platform__in=(Store.Platform.PDD, Store.Platform.DOUYIN),
        accounts__account_type=StoreAccount.AccountType.HUMAN,
        accounts__external_id="",
    ).exclude(cookie="").distinct()
    captured_count = 0
    for store in candidate_stores:
        try:
            _, account_id = capture_missing_human_account_id_from_cookie(
                store.cookie, shop_id=store.external_id, platform=store.platform
            )
        except ValueError:
            # An invalid Cookie or more than one blank account cannot be matched safely.
            continue
        if account_id:
            captured_count += 1
    return captured_count


def account_api_data(store):
    accounts = store.accounts.all()
    def serialize(account):
        return {
            "account_name": account.name,
            "account_id": account.external_id or "该id没抓",
            "account_type": account.account_type,
            "account_type_name": account.get_account_type_display(),
            "login_account": account.login_account,
            "login_password": account.login_password,
        }

    return {
        "human_accounts": [serialize(account) for account in accounts if account.account_type == StoreAccount.AccountType.HUMAN],
        "bot_accounts": [serialize(account) for account in accounts if account.account_type == StoreAccount.AccountType.BOT],
    }


def cookie_api_data(store, include_cookie=False):
    data = {
        "platform": store.platform,
        "platform_name": store.get_platform_display(),
        "shop_name": store.name,
        "shop_id": store.external_id,
        "customer": store.customer.name if store.customer else None,
        "main_category": store.main_category or "notfind",
        "cookie_status": store.cookie_status,
        "cookie_updated_at": store.cookie_updated_at.isoformat(),
        **account_api_data(store),
    }
    if include_cookie:
        data["cookie"] = store.cookie
    return data


def robot_cookie_api_data(store, include_cookie=False):
    """Return the legacy Cookie API shape, backed by the robot Cookie store."""
    data = cookie_api_data(store)
    data["cookie_updated_at"] = store.robot_cookie_updated_at.isoformat()
    if include_cookie:
        data["cookie"] = store.robot_cookie
    return data


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            monthly_group = Group.objects.filter(name="客服月度回复查看员").first()
            if monthly_group:
                user.groups.add(monthly_group)
            login(request, user)
            messages.success(request, "注册成功，欢迎进入蘑菇头中控平台。")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "core/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    form.fields["password"].widget.input_type = "text"
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.POST.get("next") or "dashboard")
    return render(request, "core/login.html", {"form": form})


@login_required
def dashboard(request):
    if is_customer_account(request.user):
        stores = customer_stores(request.user)
        metric_totals = stores.aggregate(
            pending_after_sales=Sum("metrics__pending_after_sales"),
            pending_tickets=Sum("metrics__pending_tickets"),
            today_order_count=Sum("metrics__today_order_count"),
            consultation_count=Sum("metrics__consultation_count"),
        )
        return render(request, "core/client_dashboard.html", {
            "customer": request.user.customer,
            "store_count": stores.count(),
            "account_count": StoreAccount.objects.filter(store__customer_id=request.user.customer_id).count(),
            "pending_after_sales": metric_totals["pending_after_sales"] or 0,
            "pending_tickets": metric_totals["pending_tickets"] or 0,
            "today_order_count": metric_totals["today_order_count"] or 0,
            "consultation_count": metric_totals["consultation_count"] or 0,
            "recent_stores": stores.select_related("metrics").prefetch_related("accounts").order_by("-metrics__data_updated_at", "name")[:8],
        })
    all_stores = Store.objects.all()
    if not (is_platform_admin(request.user) or request.user.has_perm("core.can_view_all_store_data")):
        all_stores = all_stores.filter(shift_claims__user=request.user).distinct()
    pending_tasks = list(pending_tasks_visible_to(request.user))
    for task in pending_tasks:
        task.elapsed_time = format_elapsed_time(task.created_at)
    context = {
        "store_count": all_stores.count(),
        "customer_count": Customer.objects.filter(is_active=True).count(),
        "unowned_count": Store.objects.annotate(claim_count=Count("shift_claims")).filter(claim_count__lt=2).count(),
        "invalid_cookie_count": Store.objects.filter(cookie_status=Store.CookieStatus.INVALID).count(),
        "recent_stores": all_stores.select_related("customer").order_by("-cookie_updated_at")[:7],
        "pending_tasks": pending_tasks,
        "can_view_all_pending_tasks": can_view_all_pending_tasks(request.user),
        "can_clear_all_pending_tasks": is_platform_admin(request.user),
    }
    return render(request, "core/dashboard.html", context)


@login_required
@require_POST
def pending_task_complete(request, pk):
    task = get_object_or_404(PendingTask.objects.select_related("store"), pk=pk)
    if not can_view_all_pending_tasks(request.user) and not task.store.shift_claims.filter(user=request.user).exists():
        return HttpResponseForbidden("你不是该店铺的负责人，无法处理此事务。")
    if not task.is_processed:
        task.is_processed = True
        task.processed_at = timezone.now()
        task.processed_by = request.user
        task.save(update_fields=["is_processed", "processed_at", "processed_by"])
        messages.success(request, "待处理事务已标记为已处理。")
    return redirect("dashboard")


@login_required
@require_POST
def pending_tasks_clear_all(request):
    """管理员一键清空工作台待办，同时保留处理记录以便追溯。"""
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以清除全部待处理事务。")
    cleared_count = PendingTask.objects.filter(is_processed=False).update(
        is_processed=True,
        processed_at=timezone.now(),
        processed_by=request.user,
    )
    messages.success(request, f"已清除 {cleared_count} 条待处理事务。")
    return redirect("dashboard")


@login_required
def customer_list(request):
    if is_customer_account(request.user):
        return HttpResponseForbidden("客户账号不能查看其他客户信息。")
    customers = Customer.objects.annotate(
        store_total=Count("stores", distinct=True),
        pdd_store_total=Count("stores", filter=Q(stores__platform=Store.Platform.PDD), distinct=True),
        douyin_store_total=Count("stores", filter=Q(stores__platform=Store.Platform.DOUYIN), distinct=True),
        reply_total=Sum("stores__metrics__consultation_count"),
        pdd_reply_total=Sum("stores__metrics__consultation_count", filter=Q(stores__platform=Store.Platform.PDD)),
        douyin_reply_total=Sum("stores__metrics__consultation_count", filter=Q(stores__platform=Store.Platform.DOUYIN)),
    ).select_related("portal_user")
    return render(request, "core/customer_list.html", {"customers": customers, "can_manage": request.user.has_perm("core.can_manage_clients") or is_platform_admin(request.user)})


@login_required
@permission_required("core.can_manage_clients", raise_exception=True)
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.store_data_visible_fields = [
            field for field in request.POST.getlist("visible_fields") if field in STORE_DATA_ALL_COLUMNS
        ]
        customer.allow_store_knowledge_view = request.POST.get("allow_store_knowledge_view") == "on"
        customer.allow_product_knowledge_view = request.POST.get("allow_product_knowledge_view") == "on"
        customer.save()
        messages.success(request, "客户已添加。")
        return redirect("customer_list")
    return render(request, "core/customer_form.html", {
        "form": form,
        "title": "新增客户",
        "column_options": [(key, STORE_DATA_COLUMN_LABELS[key]) for key in STORE_DATA_ALL_COLUMNS],
        "visible_fields": STORE_DATA_BASE_COLUMNS,
    })


@login_required
@permission_required("core.can_manage_clients", raise_exception=True)
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.store_data_visible_fields = [
            field for field in request.POST.getlist("visible_fields") if field in STORE_DATA_ALL_COLUMNS
        ]
        customer.allow_store_knowledge_view = request.POST.get("allow_store_knowledge_view") == "on"
        customer.allow_product_knowledge_view = request.POST.get("allow_product_knowledge_view") == "on"
        customer.save()
        messages.success(request, "客户信息已更新。")
        return redirect("customer_list")
    return render(request, "core/customer_form.html", {
        "form": form,
        "title": f"编辑客户：{customer.name}",
        "customer": customer,
        "column_options": [(key, STORE_DATA_COLUMN_LABELS[key]) for key in STORE_DATA_ALL_COLUMNS],
        "visible_fields": customer.store_data_visible_fields if customer.store_data_visible_fields is not None else STORE_DATA_BASE_COLUMNS,
    })


@login_required
@permission_required("core.can_manage_clients", raise_exception=True)
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    name = customer.name
    customer.delete()
    messages.success(request, f"已删除客户“{name}”及其下属店铺、账号与认领信息。")
    return redirect("customer_list")


@login_required
def client_account_management(request):
    """One portal login may be created for each customer by an administrator."""
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以管理客户登录账号。")

    if request.method == "POST":
        action = request.POST.get("action", "create")
        if action == "create":
            customer = get_object_or_404(Customer, pk=request.POST.get("customer_id"))
            if hasattr(customer, "portal_user"):
                messages.error(request, f"客户“{customer.name}”已创建登录账号。")
            else:
                username = request.POST.get("username", "").strip()
                password = request.POST.get("password", "")
                responsible_name = request.POST.get("responsible_name", "").strip() or customer.name
                if not username:
                    messages.error(request, "登录账号不能为空。")
                elif User.objects.filter(username=username).exists():
                    messages.error(request, "该登录账号已存在。")
                else:
                    try:
                        validate_password(password)
                    except ValidationError as exc:
                        messages.error(request, "；".join(exc.messages))
                    else:
                        User.objects.create_user(
                            username=username,
                            password=password,
                            responsible_name=responsible_name[:50],
                            customer=customer,
                        )
                        messages.success(request, f"已为客户“{customer.name}”创建登录账号。")
        else:
            account = get_object_or_404(User, pk=request.POST.get("user_id"), customer__isnull=False)
            if action == "toggle":
                account.is_active = not account.is_active
                account.save(update_fields=["is_active"])
                messages.success(request, f"客户账号“{account.username}”已{'启用' if account.is_active else '停用'}。")
            elif action == "reset_password":
                password = request.POST.get("password", "")
                try:
                    validate_password(password, account)
                except ValidationError as exc:
                    messages.error(request, "；".join(exc.messages))
                else:
                    account.set_password(password)
                    account.save(update_fields=["password"])
                    messages.success(request, f"客户账号“{account.username}”的密码已重置。")
            else:
                return HttpResponseForbidden("不支持的客户账号操作。")
        return redirect("client_account_management")

    customers = Customer.objects.select_related("portal_user").order_by("name")
    return render(request, "core/client_account_management.html", {"customers": customers})


def get_cookie_center_context(request):
    stores = Store.objects.select_related("customer").prefetch_related("accounts").all()
    if not can_manage_all_cookies(request.user):
        stores = stores.filter(shift_claims__user=request.user).distinct()
    platform = normalize_platform(request.GET.get("platform"))
    if platform:
        stores = stores.filter(platform=platform)
    filter_customers = Customer.objects.filter(stores__in=stores).distinct().order_by("name")
    chosen_customer_id = request.GET.get("customer", "").strip()
    store_query = request.GET.get("store", "").strip()
    try:
        customer_id = int(chosen_customer_id) if chosen_customer_id else None
    except ValueError:
        chosen_customer_id = ""
        customer_id = None
    if customer_id:
        stores = stores.filter(customer_id=customer_id)
    if store_query:
        stores = stores.filter(Q(name__icontains=store_query) | Q(external_id__icontains=store_query))
    can_delete = request.user.has_perm("core.can_delete_cookie") or is_platform_admin(request.user)
    page_obj, stores, pagination_query = paginate_center_queryset(stores, request)
    return {
        "stores": stores,
        "platform": platform,
        "filter_customers": filter_customers,
        "chosen_customer_id": chosen_customer_id,
        "store_query": store_query,
        "can_delete": can_delete,
        "can_manage_status": is_platform_admin(request.user),
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    }


@login_required
def cookie_center(request):
    return render(request, "core/cookie_center.html", get_cookie_center_context(request))


@login_required
@require_GET
def cookie_center_api(request):
    context = get_cookie_center_context(request)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [{
                "id": store.pk,
                "name": store.name,
                "external_id": store.external_id,
                "platform": store.get_platform_display(),
                "customer": store.customer.name if store.customer else "待归属",
                "main_category": store.main_category or "notfind",
                "cookie": store.cookie,
                "cookie_updated_at": store.cookie_updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "status": store.cookie_status,
                "status_label": store.get_cookie_status_display(),
                "delete_url": reverse("cookie_delete", args=[store.pk]),
                "status_url": reverse("cookie_status_update", args=[store.pk]),
            } for store in context["stores"]],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


@login_required
@require_POST
def cookie_delete(request, pk):
    if not (is_platform_admin(request.user) or request.user.has_perm("core.can_delete_cookie")):
        return HttpResponseForbidden("你没有删除 Cookie 的权限。")
    store = get_object_or_404(Store, pk=pk)
    store.delete()
    messages.success(request, "Cookie 与关联店铺数据已删除。")
    return redirect("cookie_center")


@login_required
@require_POST
def cookie_status_update(request, pk):
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以手动设置 Cookie 状态。")
    status = request.POST.get("cookie_status")
    if status not in {Store.CookieStatus.VALID, Store.CookieStatus.INVALID}:
        messages.error(request, "Cookie 状态只能设置为有效或失效。")
        return redirect("cookie_center")
    store = get_object_or_404(Store, pk=pk)
    store.cookie_status = status
    store.save(update_fields=["cookie_status"])
    messages.success(request, f"已将“{store.name}”的 Cookie 设为{store.get_cookie_status_display()}。")
    return redirect("cookie_center")


def get_unowned_store_context(request, *, include_options=True):
    stores = Store.objects.select_related("customer").prefetch_related("shift_claims__user").annotate(claim_count=Count("shift_claims")).filter(claim_count__lt=2)
    search_query = request.GET.get("q", "").strip()
    if search_query:
        stores = stores.filter(Q(name__icontains=search_query) | Q(external_id__icontains=search_query))
    stores = stores.order_by("-cookie_updated_at", "-pk")
    page_obj, stores, pagination_query = paginate_center_queryset(stores, request)
    customers = Customer.objects.filter(is_active=True) if include_options else Customer.objects.none()
    active_users = User.objects.filter(is_active=True).order_by("username") if include_options else User.objects.none()
    return {
        "stores": stores,
        "customers": customers,
        "active_users": active_users,
        "cannot_claim": is_platform_admin(request.user),
        "can_assign_responsible": is_platform_admin(request.user),
        "can_delete_unowned_store": is_platform_admin(request.user),
        "search_query": search_query,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    }


@login_required
def unowned_store_center(request):
    return render(request, "core/unowned_stores.html", get_unowned_store_context(request))


@login_required
@require_GET
def unowned_store_center_api(request):
    context = get_unowned_store_context(request)
    def claim_data(claim):
        if not claim:
            return None
        return {"username": claim.user.username}
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [{
                "id": store.pk,
                "name": store.name,
                "external_id": store.external_id,
                "platform": store.get_platform_display(),
                "cookie_status": store.cookie_status,
                "cookie_status_label": store.get_cookie_status_display(),
                "customer_id": store.customer_id,
                "customer": store.customer.name if store.customer else None,
                "main_category": store.main_category or "notfind",
                "morning_claim": claim_data(store.morning_claim),
                "evening_claim": claim_data(store.evening_claim),
                "delete_url": reverse("unowned_store_delete", args=[store.pk]),
                "morning_claim_url": reverse("claim_store_shift", args=[store.pk, "morning"]),
                "evening_claim_url": reverse("claim_store_shift", args=[store.pk, "evening"]),
                "morning_assign_url": reverse("admin_assign_store_shift", args=[store.pk, "morning"]),
                "evening_assign_url": reverse("admin_assign_store_shift", args=[store.pk, "evening"]),
            } for store in context["stores"]],
            "customers": list(context["customers"].values("pk", "name")),
            "active_users": list(context["active_users"].values("pk", "username", "responsible_name")),
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


@login_required
@require_POST
def unowned_store_delete(request, pk):
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以删除无主店铺。")
    try:
        with transaction.atomic():
            store = Store.objects.select_for_update().get(pk=pk)
            if store.shift_claims.count() >= 2:
                messages.error(request, "该店铺已完成认领，不能从无主店铺中心删除。")
                return redirect("unowned_store_center")
            store_name = store.name
            store.delete()
    except Store.DoesNotExist:
        raise Http404
    messages.success(request, f"已删除无主店铺“{store_name}”及其关联数据。")
    return redirect("unowned_store_center")


@login_required
@require_POST
def claim_store_shift(request, pk, shift):
    if is_platform_admin(request.user):
        return HttpResponseForbidden("管理员账号不允许认领无主店铺。")
    normal_shift = normalize_shift(shift)
    if not normal_shift:
        raise Http404
    customer_id = request.POST.get("customer_id")
    customer_name = request.POST.get("customer_name", "").strip()
    try:
        with transaction.atomic():
            store = Store.objects.select_for_update().get(pk=pk)
            if store.customer:
                customer = store.customer
            elif customer_id:
                customer = Customer.objects.get(pk=customer_id, is_active=True)
            elif customer_name:
                customer = Customer.objects.get(name=customer_name, is_active=True)
            else:
                messages.error(request, "首次认领该店铺时必须填写所属客户。")
                return redirect("unowned_store_center")
            if StoreShiftClaim.objects.filter(store=store, shift=normal_shift).exists():
                messages.error(request, "该班次刚刚已被其他用户领取。")
                return redirect("unowned_store_center")
            if store.customer and store.customer_id != customer.id:
                messages.error(request, "该店铺已归属其他客户，请选择与店铺一致的客户。")
                return redirect("unowned_store_center")
            StoreShiftClaim.objects.create(store=store, shift=normal_shift, user=request.user, customer=customer)
            if not store.customer:
                store.customer = customer
            if not store.responsible:
                store.responsible = request.user
            store.save(update_fields=["customer", "responsible"])
    except Customer.DoesNotExist:
        messages.error(request, "所选客户不存在或已禁用。")
    except Store.DoesNotExist:
        raise Http404
    else:
        slot_name = "负责人 1" if normal_shift == StoreShiftClaim.Shift.MORNING else "负责人 2"
        messages.success(request, f"已领取{slot_name}。")
    return redirect("unowned_store_center")


@login_required
@require_POST
def admin_assign_store_shift(request, pk, shift):
    """管理员为无主店铺的空负责人席位指定任意启用账号。"""
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以为无主店铺指定负责人。")
    normal_shift = normalize_shift(shift)
    if not normal_shift:
        raise Http404
    try:
        target_user = User.objects.get(pk=request.POST.get("user_id"), is_active=True)
        with transaction.atomic():
            store = Store.objects.select_for_update().select_related("customer").get(pk=pk)
            if StoreShiftClaim.objects.filter(store=store, shift=normal_shift).exists():
                messages.error(request, "该负责人席位刚刚已被分配。")
                return redirect("unowned_store_center")
            customer_id = request.POST.get("customer_id")
            if not customer_id:
                messages.error(request, "指定负责人时必须选择所属客户。")
                return redirect("unowned_store_center")
            customer = Customer.objects.get(pk=customer_id, is_active=True)
            if store.customer_id and store.customer_id != customer.id:
                messages.error(request, "该店铺已归属其他客户，请选择与店铺一致的客户。")
                return redirect("unowned_store_center")
            StoreShiftClaim.objects.create(store=store, shift=normal_shift, user=target_user, customer=customer)
            if not store.customer:
                store.customer = customer
            if not store.responsible:
                store.responsible = target_user
            store.save(update_fields=["customer", "responsible"])
    except (User.DoesNotExist, Customer.DoesNotExist):
        messages.error(request, "所选负责人或客户不存在、已被禁用。")
    except Store.DoesNotExist:
        raise Http404
    else:
        slot_name = "负责人 1" if normal_shift == StoreShiftClaim.Shift.MORNING else "负责人 2"
        messages.success(request, f"已将{slot_name}指定为“{target_user.username}”。")
    return redirect("unowned_store_center")


def get_store_data_context(request, *, include_filter_options=True, notify_invalid_filters=True):
    """Build the shared, permission-scoped data set for HTML and JSON responses."""
    is_client = is_customer_account(request.user)
    can_view_all = is_platform_admin(request.user) or request.user.has_perm("core.can_view_all_store_data")
    stores = Store.objects.select_related("customer", "responsible", "metrics").prefetch_related("shift_claims__user")
    saved_columns = request.user.store_data_visible_fields
    if is_client:
        customer_columns = request.user.customer.store_data_visible_fields
        visible_columns = customer_columns if customer_columns is not None else STORE_DATA_BASE_COLUMNS
    else:
        visible_columns = saved_columns if can_view_all and saved_columns is not None else STORE_DATA_ALL_COLUMNS if can_view_all else STORE_DATA_BASE_COLUMNS
    chosen_platform = normalize_platform(request.GET.get("platform"))
    if is_client:
        stores = stores.filter(customer_id=request.user.customer_id)
    elif not can_view_all:
        stores = stores.filter(shift_claims__user=request.user).distinct()

    customers = Customer.objects.none()
    responsibles = User.objects.none()
    if include_filter_options:
        # 筛选候选项基于用户原本可见的店铺生成，避免普通用户通过下拉选项探知其他负责人或客户。
        visible_store_ids = stores.values("pk")
        customers = Customer.objects.filter(stores__in=visible_store_ids).distinct().order_by("name")
        if can_view_all and not is_client:
            responsibles = User.objects.filter(store_claims__store__in=visible_store_ids).distinct().order_by("responsible_name", "username")
        elif not is_client:
            responsibles = User.objects.filter(pk=request.user.pk)

    validation_errors = []

    def add_validation_error(message):
        validation_errors.append(message)
        if notify_invalid_filters:
            messages.error(request, message)

    chosen_customer_id = request.GET.get("customer", "").strip()
    if chosen_customer_id:
        try:
            stores = stores.filter(customer_id=int(chosen_customer_id))
        except ValueError:
            chosen_customer_id = ""
            add_validation_error("客户筛选条件不正确。")

    chosen_responsible_id = request.GET.get("responsible", "").strip()
    if chosen_responsible_id:
        try:
            responsible_id = int(chosen_responsible_id)
            if is_client or (not can_view_all and responsible_id != request.user.pk):
                raise ValueError
            stores = stores.filter(shift_claims__user_id=responsible_id).distinct()
        except ValueError:
            chosen_responsible_id = ""
            add_validation_error("负责人筛选条件不正确。")

    if chosen_platform:
        stores = stores.filter(platform=chosen_platform)
    chosen_date = request.GET.get("date", "").strip()
    chosen_hour_raw = request.GET.get("hour", "").strip()
    chosen_hour = None
    snapshot_date = None
    if chosen_date:
        try:
            snapshot_date = datetime.strptime(chosen_date, "%Y-%m-%d").date()
        except ValueError:
            add_validation_error("日期格式应为 YYYY-MM-DD。")
            chosen_date = ""
    if chosen_hour_raw:
        try:
            chosen_hour = int(chosen_hour_raw)
            if not 0 <= chosen_hour <= 23:
                raise ValueError
        except ValueError:
            add_validation_error("统计小时只能填写 0 到 23 的整数。")
            chosen_hour = None
    sortable_visible_columns = set(visible_columns) | {"store_name"}
    requested_sort = request.GET.get("sort", "").strip()
    current_sort = (
        requested_sort
        if requested_sort in STORE_DATA_SORT_COLUMNS and requested_sort in sortable_visible_columns
        else ""
    )
    requested_direction = request.GET.get("direction", "").strip().lower()
    sort_direction = requested_direction if requested_direction in {"asc", "desc"} else ""
    if current_sort and sort_direction:
        if snapshot_date and chosen_hour is not None and current_sort in STORE_DATA_NUMERIC_COLUMNS:
            sort_value = StoreMetricSnapshot.objects.filter(
                store_id=OuterRef("pk"), report_date=snapshot_date, report_hour=chosen_hour
            ).order_by().values(current_sort)[:1]
            stores = stores.annotate(_sort_value=Subquery(sort_value))
            sort_field = F("_sort_value")
        elif snapshot_date and chosen_hour is not None and current_sort == "data_updated_at":
            sort_value = StoreMetricSnapshot.objects.filter(
                store_id=OuterRef("pk"), report_date=snapshot_date, report_hour=chosen_hour
            ).order_by().values("reported_at")[:1]
            stores = stores.annotate(_sort_value=Subquery(sort_value))
            sort_field = F("_sort_value")
        elif current_sort in STORE_DATA_NUMERIC_COLUMNS:
            sort_field = F(f"metrics__{current_sort}")
        else:
            sort_field = F(STORE_DATA_TEXT_SORT_FIELDS[current_sort])
        stores = stores.order_by(
            sort_field.asc(nulls_last=True) if sort_direction == "asc" else sort_field.desc(nulls_last=True)
        )

    paginator = Paginator(stores, 50)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    stores = list(page_obj.object_list)
    if snapshot_date and chosen_hour is not None:
        snapshots = StoreMetricSnapshot.objects.filter(
            store__in=stores, report_date=snapshot_date, report_hour=chosen_hour
        )
        snapshot_map = {snapshot.store_id: snapshot for snapshot in snapshots}
        for store in stores:
            store.display_metric = snapshot_map.get(store.id)
    else:
        for store in stores:
            store.display_metric = getattr(store, "metrics", None)
    for store in stores:
        claims_by_shift = {claim.shift: claim for claim in store.shift_claims.all()}
        store.responsible_claims = [
            claim for claim in (
                claims_by_shift.get(StoreShiftClaim.Shift.MORNING),
                claims_by_shift.get(StoreShiftClaim.Shift.EVENING),
            ) if claim
        ]

    pagination_query = request.GET.copy()
    pagination_query.pop("page", None)
    sort_query = pagination_query.copy()
    sort_query.pop("sort", None)
    sort_query.pop("direction", None)
    return {
        "stores": stores, "can_view_extra": can_view_all, "is_client_account": is_client,
        "can_manage_responsibility": not is_client,
        "chosen_platform": chosen_platform,
        "chosen_date": chosen_date, "chosen_hour": chosen_hour, "hour_choices": range(24),
        "customers": customers, "responsibles": responsibles,
        "chosen_customer_id": chosen_customer_id, "chosen_responsible_id": chosen_responsible_id,
        "visible_columns": visible_columns, "column_options": [(key, STORE_DATA_COLUMN_LABELS[key]) for key in STORE_DATA_ALL_COLUMNS],
        "page_obj": page_obj, "pagination_query": pagination_query.urlencode(), "current_sort": current_sort,
        "sort_direction": sort_direction, "sort_query": sort_query.urlencode(),
        "validation_errors": validation_errors,
    }


def store_data_metric_value(metric, field):
    """Match the existing template display rule in the JSON response."""
    if metric is None:
        return "NaN"
    display_values = getattr(metric, "metric_display_values", None) or {}
    if field in display_values:
        return str(display_values[field])
    value = getattr(metric, field, None)
    if value is None:
        return "NaN"
    return f"{value}{STORE_DATA_METRIC_SUFFIXES.get(field, '')}"


def store_data_json_row(store, visible_columns, can_view_all):
    values = {}
    for column in visible_columns:
        if column in STORE_DATA_NUMERIC_COLUMNS:
            values[column] = store_data_metric_value(store.display_metric, column)
        elif column == "customer":
            values[column] = store.customer.name if store.customer else "待归属"
        elif column == "data_updated_at":
            updated_at = getattr(store.display_metric, "data_updated_at", None)
            values[column] = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "未上传"
        elif column == "main_category":
            values[column] = store.main_category or "notfind"

    claims = [
        {
            "id": claim.pk,
            "shift": claim.shift,
            "label": "负责人 1" if claim.shift == StoreShiftClaim.Shift.MORNING else "负责人 2",
            "responsible_name": claim.user.responsible_name,
            "username": claim.user.username,
        }
        for claim in store.responsible_claims
    ]
    return {
        "id": store.pk,
        "name": store.name,
        "external_id": store.external_id,
        "platform": store.get_platform_display(),
        "values": values,
        "responsibles": claims,
        "release_url": reverse("release_store_responsibility", args=[store.pk]),
        "can_choose_claim": can_view_all,
    }


@login_required
def store_data_center(request):
    return render(request, "core/store_data_center.html", get_store_data_context(request))


@login_required
@require_GET
def store_data_api(request):
    """Return one data-center page as JSON for in-place filtering and pagination."""
    context = get_store_data_context(
        request, include_filter_options=False, notify_invalid_filters=False
    )
    page_obj = context["page_obj"]
    return JsonResponse({
        "ok": not context["validation_errors"],
        "errors": context["validation_errors"],
        "data": {
            "rows": [
                store_data_json_row(store, context["visible_columns"], context["can_view_extra"])
                for store in context["stores"]
            ],
            "pagination": {
                "count": page_obj.paginator.count,
                "number": page_obj.number,
                "num_pages": page_obj.paginator.num_pages,
                "has_previous": page_obj.has_previous(),
                "previous_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
                "has_next": page_obj.has_next(),
                "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            },
        },
    })


@login_required
@require_POST
def store_data_column_preferences(request):
    if not (is_platform_admin(request.user) or request.user.has_perm("core.can_view_all_store_data")):
        return HttpResponseForbidden("只有数据管理员可以配置店铺数据中心的显示字段。")
    if request.POST.get("reset"):
        request.user.store_data_visible_fields = None
        messages.success(request, "已恢复默认显示字段。")
    else:
        selected_fields = [field for field in request.POST.getlist("visible_fields") if field in STORE_DATA_ALL_COLUMNS]
        request.user.store_data_visible_fields = selected_fields
        messages.success(request, "店铺数据中心显示字段已保存到当前账号。")
    request.user.save(update_fields=["store_data_visible_fields"])
    return redirect("store_data_center")


@login_required
@require_POST
def release_store_responsibility(request, pk):
    """普通用户仅释放自己的席位；管理员可精确释放任一负责人席位。"""
    if is_customer_account(request.user):
        return HttpResponseForbidden("客户账号不能变更店铺负责人。")
    try:
        with transaction.atomic():
            store = Store.objects.select_for_update().get(pk=pk)
            can_manage_all = is_platform_admin(request.user) or request.user.has_perm("core.can_view_all_store_data")
            if can_manage_all:
                claim_id = request.POST.get("claim_id")
                if not claim_id:
                    messages.error(request, "请先选择需要取消的负责人。")
                    return redirect("store_data_center")
                claims = store.shift_claims.filter(pk=claim_id)
            else:
                claims = store.shift_claims.filter(user=request.user)
            if not claims.exists():
                return HttpResponseForbidden("你不是该店铺的负责人，无法取消。")
            claims.delete()
            remaining_claim = store.shift_claims.select_related("user", "customer").first()
            if remaining_claim:
                store.responsible = remaining_claim.user
                store.customer = remaining_claim.customer
            else:
                store.responsible = None
                store.customer = None
            store.save(update_fields=["responsible", "customer"])
    except Store.DoesNotExist:
        raise Http404
    messages.success(request, "已取消负责人。店铺中空出的班次已回到无主店铺中心。")
    return redirect("store_data_center")


def parse_date_or_today(value):
    if not value:
        return timezone.localdate()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("日期格式应为 YYYY-MM-DD")


def parse_hour_or_current(value):
    if value in (None, ""):
        return timezone.localtime().hour
    try:
        hour = int(value)
    except (TypeError, ValueError):
        raise ValueError("小时只能是 0 到 23 的整数")
    if not 0 <= hour <= 23:
        raise ValueError("小时只能是 0 到 23 的整数")
    return hour


def parse_summary_date_payload(data):
    if not all(key in data for key in ("year", "month", "day")):
        raise ValueError("班次日总结必须提供 year、month、day")
    try:
        return datetime(int(data["year"]), int(data["month"]), int(data["day"])).date()
    except (TypeError, ValueError):
        raise ValueError("year、month、day 不是有效日期")


def snapshot_difference(current, baseline, field):
    value = getattr(current, field, 0) if current else 0
    baseline_value = getattr(baseline, field, 0) if baseline else 0
    return max((value or 0) - (baseline_value or 0), 0)


@login_required
@permission_required("core.can_view_customer_performance", raise_exception=True)
def customer_performance(request):
    try:
        report_date = parse_date_or_today(request.GET.get("date"))
    except ValueError as exc:
        messages.error(request, str(exc))
        report_date = timezone.localdate()
    selected_shift = normalize_shift(request.GET.get("shift"))
    platform = normalize_platform(request.GET.get("platform"))
    summaries = ShiftDailySummary.objects.filter(summary_date=report_date)
    if selected_shift:
        summaries = summaries.filter(shift=selected_shift)
    if platform:
        summaries = summaries.filter(store__platform=platform)
    rows = list(summaries.values("user_id", "user__username", "user__responsible_name", "shift").annotate(
        store_count=Count("store_id", distinct=True),
        reply_total=Sum("consultation_count"), timeout_total=Sum("timeout_count"),
    ).order_by("-reply_total", "user__username"))
    for row in rows:
        row["shift_label"] = "早班" if row["shift"] == StoreShiftClaim.Shift.MORNING else "晚班"
    return render(request, "core/customer_performance.html", {"rows": rows, "report_date": report_date.isoformat(), "chosen_platform": platform, "selected_shift": selected_shift})


@login_required
def monthly_replies(request):
    can_view_all = is_platform_admin(request.user) or request.user.has_perm("core.can_view_customer_performance")
    if not can_view_all and not request.user.has_perm("core.can_view_own_monthly_replies"):
        return HttpResponseForbidden("你没有查看月度回复的权限。")
    month = request.GET.get("month", timezone.localdate().strftime("%Y-%m"))
    try:
        month_date = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "月份格式应为 YYYY-MM。")
        month = timezone.localdate().strftime("%Y-%m")
        month_date = timezone.localdate().replace(day=1)
    summaries_query = ShiftDailySummary.objects.filter(summary_date__year=month_date.year, summary_date__month=month_date.month)
    if not can_view_all:
        summaries_query = summaries_query.filter(user=request.user)
    visible_summary_ids = summaries_query.values("pk")
    customers = Customer.objects.filter(stores__daily_summaries__in=visible_summary_ids).distinct().order_by("name")
    if can_view_all:
        responsibles = User.objects.filter(daily_shift_summaries__in=visible_summary_ids).distinct().order_by("responsible_name", "username")
    else:
        responsibles = User.objects.filter(pk=request.user.pk)

    chosen_customer_id = request.GET.get("customer", "").strip()
    if chosen_customer_id:
        try:
            summaries_query = summaries_query.filter(store__customer_id=int(chosen_customer_id))
        except ValueError:
            chosen_customer_id = ""
            messages.error(request, "客户筛选条件不正确。")

    chosen_responsible_id = request.GET.get("responsible", "").strip()
    if chosen_responsible_id:
        try:
            responsible_id = int(chosen_responsible_id)
            if not can_view_all and responsible_id != request.user.pk:
                raise ValueError
            summaries_query = summaries_query.filter(user_id=responsible_id)
        except ValueError:
            chosen_responsible_id = ""
            messages.error(request, "负责人筛选条件不正确。")

    summaries = list(summaries_query.values("summary_date", "user__username", "user__responsible_name", "shift").annotate(reply_total=Sum("consultation_count"), timeout_total=Sum("timeout_count")).order_by("summary_date", "user__username", "shift"))
    for row in summaries:
        row["shift_label"] = "早班" if row["shift"] == StoreShiftClaim.Shift.MORNING else "晚班"
    return render(request, "core/monthly_replies.html", {
        "rows": summaries, "month": month, "own_only": not can_view_all, "customers": customers,
        "responsibles": responsibles, "chosen_customer_id": chosen_customer_id,
        "chosen_responsible_id": chosen_responsible_id,
    })


def get_account_center_context(request, *, run_backfill=True):
    is_client = is_customer_account(request.user)
    manage_all = is_platform_admin(request.user) or request.user.has_perm("core.can_manage_all_accounts")
    own_claimed_stores = Store.objects.filter(shift_claims__user=request.user).distinct()
    if is_client:
        allowed_stores = customer_stores(request.user)
    else:
        allowed_stores = Store.objects.all() if manage_all else own_claimed_stores
    captured_count = backfill_missing_human_account_ids(allowed_stores) if run_backfill and not is_client else 0
    chosen_platform = normalize_platform(request.GET.get("platform"))
    if chosen_platform:
        allowed_stores = allowed_stores.filter(platform=chosen_platform)
    filter_customers = Customer.objects.filter(stores__in=allowed_stores).distinct().order_by("name")
    chosen_customer_id = request.GET.get("customer", "").strip()
    store_query = request.GET.get("store", "").strip()
    has_robot_account = request.GET.get("has_robot_account", "").strip().lower() in {"1", "true", "on", "yes"}
    try:
        customer_id = int(chosen_customer_id) if chosen_customer_id else None
    except ValueError:
        chosen_customer_id = ""
        customer_id = None
    if customer_id:
        allowed_stores = allowed_stores.filter(customer_id=customer_id)
    if store_query:
        allowed_stores = allowed_stores.filter(
            Q(name__icontains=store_query) | Q(external_id__icontains=store_query)
        )
    if has_robot_account:
        allowed_stores = allowed_stores.filter(accounts__account_type=StoreAccount.AccountType.BOT).distinct()
    selectable_stores = allowed_stores
    accounts = StoreAccount.objects.filter(store__in=allowed_stores).select_related(
        "store", "store__customer", "created_by"
    ).prefetch_related("store__accounts").order_by("store__name", "account_type", "name")
    page_obj, accounts, pagination_query = paginate_center_queryset(accounts, request)
    for account in accounts:
        bots = [item.name for item in account.store.accounts.all() if item.account_type == StoreAccount.AccountType.BOT]
        account.has_bot_account = bool(bots)
        account.bot_account_names = "、".join(bots) or "/"
        account.can_edit = not is_client
    return {
        "accounts": accounts,
        "selectable_stores": selectable_stores,
        "has_stores": selectable_stores.exists(),
        "chosen_platform": chosen_platform,
        "filter_customers": filter_customers,
        "chosen_customer_id": chosen_customer_id,
        "store_query": store_query,
        "has_robot_account": has_robot_account,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "captured_count": captured_count,
        "can_manage_store_accounts": not is_client,
    }


@login_required
def account_center(request):
    context = get_account_center_context(request)
    if context["captured_count"]:
        messages.success(request, f"已根据已保存 Cookie 自动补齐 {context['captured_count']} 个专员账号 ID。")
    if request.method == "POST":
        if not context["can_manage_store_accounts"]:
            return HttpResponseForbidden("客户账号仅可查看自己店铺的账号信息。")
        form = StoreAccountForm(request.POST, stores=context["selectable_stores"])
        if form.is_valid():
            account = form.save(commit=False)
            account.created_by = request.user
            account.save()
            messages.success(request, "店铺账号已添加；同店铺早晚班会自动共用该账号。")
            return redirect("account_center")
    else:
        form = StoreAccountForm(stores=context["selectable_stores"])
    context["form"] = form
    return render(request, "core/account_center.html", context)


@login_required
@require_GET
def account_center_api(request):
    context = get_account_center_context(request, run_backfill=False)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [{
                "id": account.pk,
                "store_name": account.store.name,
                "store_external_id": account.store.external_id,
                "name": account.name,
                "account_type": account.account_type,
                "account_type_label": account.get_account_type_display(),
                "login_account": account.login_account,
                "login_password": account.login_password,
                "corresponding_port": account.corresponding_port or "—",
                "phone": account.phone or "—",
                "external_id": account.external_id or "该id没抓",
                "has_bot_account": account.has_bot_account,
                "bot_account_names": account.bot_account_names,
                "can_edit": account.can_edit,
                "edit_url": reverse("account_edit", args=[account.pk]),
                "delete_url": reverse("account_delete", args=[account.pk]),
            } for account in context["accounts"]],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


def get_account_password_center_context(request, *, run_backfill=True):
    store_query = request.GET.get("store", "").strip()
    chosen_customer_id = request.GET.get("customer", "").strip()
    responsible_query = request.GET.get("responsible", "").strip()
    captured_count = backfill_missing_human_account_ids(Store.objects.all()) if run_backfill else 0
    accounts = StoreAccount.objects.select_related("store", "store__customer", "created_by").prefetch_related(
        "store__shift_claims__user"
    ).order_by("store__name", "account_type", "name")
    filter_customers = Customer.objects.filter(stores__accounts__isnull=False).distinct().order_by("name")
    try:
        customer_id = int(chosen_customer_id) if chosen_customer_id else None
    except ValueError:
        chosen_customer_id = ""
        customer_id = None
    if store_query:
        accounts = accounts.filter(
            Q(store__name__icontains=store_query) | Q(store__external_id__icontains=store_query)
        )
    if customer_id:
        accounts = accounts.filter(store__customer_id=customer_id)
    if responsible_query:
        accounts = accounts.filter(
            Q(store__shift_claims__user__responsible_name__icontains=responsible_query)
            | Q(store__shift_claims__user__username__icontains=responsible_query)
        ).distinct()

    page_obj, accounts, pagination_query = paginate_center_queryset(accounts, request)
    for account in accounts:
        account.responsible_claims = sorted(
            account.store.shift_claims.all(), key=lambda claim: claim.shift
        )
    return {
        "accounts": accounts,
        "store_query": store_query,
        "filter_customers": filter_customers,
        "chosen_customer_id": chosen_customer_id,
        "responsible_query": responsible_query,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "captured_count": captured_count,
    }


@login_required
def account_password_center(request):
    """管理员查看全量店铺账号和密码，筛选项均为模糊匹配。"""
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以查看账号密码管理中心。")
    context = get_account_password_center_context(request)
    if context["captured_count"]:
        messages.success(request, f"已根据已保存 Cookie 自动补齐 {context['captured_count']} 个专员账号 ID。")
    return render(request, "core/account_password_center.html", context)


@login_required
@require_GET
def account_password_center_api(request):
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以查看账号密码管理中心。")
    context = get_account_password_center_context(request, run_backfill=False)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [{
                "store_name": account.store.name,
                "store_external_id": account.store.external_id,
                "platform": account.store.get_platform_display(),
                "customer": account.store.customer.name if account.store.customer else "待归属",
                "responsibles": [{
                    "label": "负责人 1" if claim.shift == StoreShiftClaim.Shift.MORNING else "负责人 2",
                    "responsible_name": claim.user.responsible_name,
                    "username": claim.user.username,
                } for claim in account.responsible_claims],
                "name": account.name,
                "account_type": account.account_type,
                "account_type_label": account.get_account_type_display(),
                "login_account": account.login_account,
                "login_password": account.login_password,
                "corresponding_port": account.corresponding_port or "—",
                "phone": account.phone or "—",
                "external_id": account.external_id or "—",
                "created_by": account.created_by.username if account.created_by else "—",
                "created_at": account.created_at.strftime("%Y-%m-%d %H:%M"),
            } for account in context["accounts"]],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


def account_password_registration_options():
    """负责人、客户、店铺、平台只作为共享文本建议，登记记录本身不保存任何外键关系。"""
    registrations = AccountPasswordRegistration.objects
    responsible_options = set(
        User.objects.exclude(responsible_name="").order_by().values_list("responsible_name", flat=True).distinct()
    )
    responsible_options.update(
        registrations.exclude(responsible_1="").order_by().values_list("responsible_1", flat=True).distinct()
    )
    responsible_options.update(
        registrations.exclude(responsible_2="").order_by().values_list("responsible_2", flat=True).distinct()
    )
    customer_options = set(Customer.objects.order_by().values_list("name", flat=True).distinct())
    customer_options.update(
        registrations.exclude(customer="").order_by().values_list("customer", flat=True).distinct()
    )
    store_options = set(Store.objects.exclude(name="").order_by().values_list("name", flat=True).distinct())
    store_options.update(
        registrations.exclude(shop_name="").order_by().values_list("shop_name", flat=True).distinct()
    )
    platform_options = {"拼多多", "京东"}
    platform_options.update(
        registrations.exclude(platform="").order_by().values_list("platform", flat=True).distinct()
    )
    return {
        "responsible_options": sorted(value.strip() for value in responsible_options if value.strip()),
        "customer_options": sorted(value.strip() for value in customer_options if value.strip()),
        "store_options": sorted(value.strip() for value in store_options if value.strip()),
        "platform_options": sorted(value.strip() for value in platform_options if value.strip()),
    }


def get_account_password_registration_context(request):
    responsible_query = request.GET.get("responsible", "").strip()
    customer_query = request.GET.get("customer", "").strip()
    store_query = request.GET.get("store", "").strip()
    registrations = AccountPasswordRegistration.objects.all()
    if responsible_query:
        registrations = registrations.filter(
            Q(responsible_1__icontains=responsible_query)
            | Q(responsible_2__icontains=responsible_query)
        )
    if customer_query:
        registrations = registrations.filter(customer__icontains=customer_query)
    if store_query:
        registrations = registrations.filter(shop_name__icontains=store_query)
    page_obj, registrations, pagination_query = paginate_center_queryset(registrations, request)
    return {
        "registrations": registrations,
        "responsible_query": responsible_query,
        "customer_query": customer_query,
        "store_query": store_query,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        **account_password_registration_options(),
    }


@login_required
@require_http_methods(["GET", "POST"])
def account_password_registration(request):
    if request.method == "POST":
        form = AccountPasswordRegistrationForm(request.POST)
        if form.is_valid():
            registration = form.save(commit=False)
            registration.operator_name = registration_operator_name(request.user)
            registration.save()
            messages.success(request, "账号密码登记已添加。")
            return redirect("account_password_registration")
    else:
        form = AccountPasswordRegistrationForm()
    # 登记记录较多时由列表 JSON 接口分页读取，首次打开页面不再查询整张记录表。
    context = {
        "responsible_query": request.GET.get("responsible", "").strip(),
        "customer_query": request.GET.get("customer", "").strip(),
        "store_query": request.GET.get("store", "").strip(),
        "form": form,
        **account_password_registration_options(),
    }
    return render(request, "core/account_password_registration.html", context)


def account_password_registration_api_data(registration):
    return {
        "id": registration.pk,
        "shop_name": registration.shop_name,
        "platform": registration.platform,
        "account_name": registration.account_name,
        "account_type": registration.account_type,
        "account_type_name": registration.get_account_type_display(),
        "login_account": registration.login_account,
        "login_password": registration.login_password,
        "phone": registration.phone,
        "responsible_1": registration.responsible_1,
        "responsible_2": registration.responsible_2,
        "customer": registration.customer,
        "remarks": registration.remarks,
        "operator_name": registration.operator_name,
        "created_at": registration.created_at.isoformat(),
        "created_at_display": registration.created_at.strftime("%Y-%m-%d %H:%M"),
        "edit_url": reverse("account_password_registration_edit", args=[registration.pk]),
        "delete_url": reverse("account_password_registration_delete", args=[registration.pk]),
    }


@login_required
@require_GET
def account_password_registration_api(request):
    """账号密码登记列表的前端数据源，筛选与分页均在此接口返回。"""
    context = get_account_password_registration_context(request)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [
                account_password_registration_api_data(registration)
                for registration in context["registrations"]
            ],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


def registration_value(data, *keys):
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key]).strip()
    return ""


def registration_operator_name(user):
    return str(user.responsible_name or user.username).strip()


@csrf_exempt
@require_POST
def api_account_password_registration_create(request):
    """供人工以外的系统写入独立账号密码登记记录；全部业务字段均可选。"""
    try:
        data = parse_json(request)
        legacy_specialist = registration_value(data, "specialist_account", "specialist", "专员账号")
        legacy_robot = registration_value(data, "robot_account", "robot", "机器人账号")
        account_type = registration_value(data, "account_type", "type", "账号类型")
        if not account_type:
            account_type = (
                AccountPasswordRegistration.AccountType.ROBOT
                if legacy_robot and not legacy_specialist
                else AccountPasswordRegistration.AccountType.SPECIALIST
            )
        if account_type not in AccountPasswordRegistration.AccountType.values:
            raise ValueError("account_type 只能是 specialist（专员账号）或 robot（机器人账号）")
        registration = AccountPasswordRegistration(
            shop_name=registration_value(data, "shop_name", "store_name", "店铺名"),
            platform=registration_value(data, "platform", "平台") or "拼多多",
            account_name=registration_value(data, "account_name", "账号名") or legacy_specialist or legacy_robot,
            account_type=account_type,
            login_account=registration_value(data, "login_account", "登录账号"),
            login_password=registration_value(data, "login_password", "password", "登录密码"),
            phone=registration_value(data, "phone", "mobile", "手机号"),
            responsible_1=registration_value(data, "responsible_1", "responsible1", "负责人1", "负责人 1"),
            responsible_2=registration_value(data, "responsible_2", "responsible2", "负责人2", "负责人 2"),
            customer=registration_value(data, "customer", "customer_name", "客户"),
            remarks=registration_value(data, "remarks", "remark", "备注"),
            operator_name=registration_value(data, "operator_name", "operator", "操作人"),
        )
        registration.full_clean()
        registration.save()
        return JsonResponse({
            "ok": True,
            "message": "账号密码登记已添加",
            "data": account_password_registration_api_data(registration),
        }, status=201)
    except ValueError as exc:
        return json_error(str(exc))
    except ValidationError as exc:
        return json_error("；".join(exc.messages))


@login_required
@require_http_methods(["GET", "POST"])
def account_password_registration_edit(request, pk):
    """登记表对全部登录账号共享，任意登录账号都可以更正已有记录。"""
    registration = get_object_or_404(AccountPasswordRegistration, pk=pk)
    if request.method == "POST":
        form = AccountPasswordRegistrationForm(request.POST, instance=registration)
        if form.is_valid():
            registration = form.save(commit=False)
            registration.operator_name = registration_operator_name(request.user)
            registration.save()
            messages.success(request, "账号密码登记已更新。")
            return redirect("account_password_registration")
    else:
        form = AccountPasswordRegistrationForm(instance=registration)
    return render(request, "core/account_password_registration_form.html", {
        "form": form,
        "registration": registration,
        **account_password_registration_options(),
    })


@login_required
@require_POST
def account_password_registration_delete(request, pk):
    """登记表对全部登录账号共享，任意登录账号都可以删除失效记录。"""
    registration = get_object_or_404(AccountPasswordRegistration, pk=pk)
    registration.delete()
    messages.success(request, "账号密码登记已删除。")
    return redirect("account_password_registration")


@login_required
@require_http_methods(["GET", "POST"])
def remote_registration(request):
    if not can_manage_remote_registrations(request.user):
        return HttpResponseForbidden("客户账号不能访问远程登记。")
    if request.method == "POST":
        form = RemoteRegistrationForm(request.POST)
        if form.is_valid():
            registration = form.save(commit=False)
            registration.operator_name = registration_operator_name(request.user)
            registration.save()
            messages.success(request, "远程登记已添加。")
            return redirect("remote_registration")
    else:
        form = RemoteRegistrationForm()
    page_obj, registrations, pagination_query = paginate_center_queryset(
        RemoteRegistration.objects.all(), request
    )
    return render(request, "core/remote_registration.html", {
        "form": form,
        "registrations": registrations,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    })


@login_required
@require_http_methods(["GET", "POST"])
def remote_registration_edit(request, pk):
    if not can_manage_remote_registrations(request.user):
        return HttpResponseForbidden("客户账号不能访问远程登记。")
    registration = get_object_or_404(RemoteRegistration, pk=pk)
    form = RemoteRegistrationForm(request.POST or None, instance=registration)
    if request.method == "POST" and form.is_valid():
        registration = form.save(commit=False)
        registration.operator_name = registration_operator_name(request.user)
        registration.save()
        messages.success(request, "远程登记已更新。")
        return redirect("remote_registration")
    return render(request, "core/remote_registration_form.html", {
        "form": form,
        "registration": registration,
    })


@login_required
@require_POST
def remote_registration_delete(request, pk):
    if not can_manage_remote_registrations(request.user):
        return HttpResponseForbidden("客户账号不能访问远程登记。")
    get_object_or_404(RemoteRegistration, pk=pk).delete()
    messages.success(request, "远程登记已删除。")
    return redirect("remote_registration")


def image_text_registration_api_data(registration):
    return {
        "id": registration.pk,
        "image_url": registration.image_url,
        "content": registration.content,
        "created_at": registration.created_at.isoformat(),
        "created_at_display": registration.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": registration.updated_at.isoformat(),
        "updated_at_display": registration.updated_at.strftime("%Y-%m-%d %H:%M"),
        "edit_url": reverse("image_text_registration_edit", args=[registration.pk]),
        "delete_url": reverse("image_text_registration_delete", args=[registration.pk]),
    }


@login_required
def image_text_registration(request):
    """图片对应文字独立页面，记录本身仍通过下方 JSON 接口异步读取。"""
    return render(request, "core/image_text_registration.html")


@login_required
@require_GET
def image_text_registration_api(request):
    """图片对应文字列表独立按 JSON 分页返回，避免登记页初始加载全部记录。"""
    page_obj = Paginator(ImageTextRegistration.objects.all(), CENTER_JSON_PAGE_SIZE).get_page(
        request.GET.get("image_page", 1)
    )
    registrations = list(page_obj.object_list)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [image_text_registration_api_data(registration) for registration in registrations],
            "pagination": pagination_json_data(page_obj),
        },
    })


@csrf_exempt
@require_POST
def api_image_text_registration_create(request):
    """供外部服务写入图片链接和对应文字。"""
    try:
        data = parse_json(request)
        image_url = registration_value(data, "image_url", "imageUrl", "image", "url", "图片链接", "图片")
        content = registration_value(data, "content", "text", "article", "文字", "文章内容")
        if not image_url or not content:
            raise ValueError("image_url（图片链接）和 text 或 content（对应文字）均为必填")
        registration = ImageTextRegistration(image_url=image_url, content=content)
        registration.full_clean()
        registration.save()
        return JsonResponse({
            "ok": True,
            "message": "图片对应文字已添加",
            "data": image_text_registration_api_data(registration),
        }, status=201)
    except ValueError as exc:
        return json_error(str(exc))
    except ValidationError as exc:
        return json_error("；".join(exc.messages))


@login_required
@require_http_methods(["GET", "POST"])
def image_text_registration_edit(request, pk):
    registration = get_object_or_404(ImageTextRegistration, pk=pk)
    form = ImageTextRegistrationForm(request.POST or None, instance=registration)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "图片对应文字已更新。")
        return redirect("image_text_registration")
    return render(request, "core/image_text_registration_form.html", {
        "form": form,
        "registration": registration,
    })


@login_required
@require_POST
def image_text_registration_delete(request, pk):
    get_object_or_404(ImageTextRegistration, pk=pk).delete()
    messages.success(request, "图片对应文字已删除。")
    return redirect("image_text_registration")


def can_edit_account(user, account):
    if is_customer_account(user):
        return False
    return account.created_by_id == user.id or is_platform_admin(user) or user.has_perm("core.can_manage_all_accounts") or StoreShiftClaim.objects.filter(store_id=account.store_id, user=user).exists()


@login_required
@require_http_methods(["GET", "POST"])
def account_edit(request, pk):
    account = get_object_or_404(StoreAccount, pk=pk)
    if not can_edit_account(request.user, account):
        return HttpResponseForbidden("仅账号创建人或该店铺负责人可以修改该账号。")
    stores = Store.objects.all() if (is_platform_admin(request.user) or request.user.has_perm("core.can_manage_all_accounts")) else Store.objects.filter(pk=account.store_id)
    form = StoreAccountForm(request.POST or None, instance=account, stores=stores)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "账号信息已更新。")
        return redirect("account_center")
    return render(request, "core/account_form.html", {"form": form, "title": f"编辑账号：{account.name}"})


@login_required
@require_POST
def account_delete(request, pk):
    account = get_object_or_404(StoreAccount, pk=pk)
    if not can_edit_account(request.user, account):
        return HttpResponseForbidden("仅账号创建人或该店铺负责人可以删除该账号。")
    account.delete()
    messages.success(request, "账号已删除。")
    return redirect("account_center")


@login_required
def permission_center(request):
    if not (is_platform_admin(request.user) or request.user.has_perm("core.can_manage_permissions")):
        return HttpResponseForbidden("你没有访问权限管理中心的权限。")
    groups = Group.objects.filter(name__in=["客户与页面管理员", "Cookie 超级管理员", "数据管理员", "权限管理员", "全局账号管理员", "客服绩效查看员", "客服月度回复查看员", "商品删除管理员"])
    if request.method == "POST":
        user = get_object_or_404(User, pk=request.POST.get("user_id"))
        action = request.POST.get("action", "update_permissions")
        if action == "change_password":
            if not is_platform_admin(request.user):
                return HttpResponseForbidden("仅管理员可以修改用户密码。")
            new_password = request.POST.get("new_password", "")
            try:
                validate_password(new_password, user)
            except ValidationError as exc:
                messages.error(request, "；".join(exc.messages))
                return redirect("permission_center")
            user.set_password(new_password)
            user.save(update_fields=["password"])
            messages.success(request, f"用户“{user.username}”的密码已修改。")
            return redirect("permission_center")

        if user == request.user and not is_platform_admin(request.user):
            return HttpResponseForbidden("不能通过权限中心修改自己的角色或账号状态。")

        update_fields = []
        if is_platform_admin(request.user):
            responsible_name = request.POST.get("responsible_name", "").strip()
            if not responsible_name:
                messages.error(request, "负责人姓名不能为空。")
                return redirect("permission_center")
            if len(responsible_name) > 50:
                messages.error(request, "负责人姓名不能超过 50 个字符。")
                return redirect("permission_center")
            user.responsible_name = responsible_name
            update_fields.append("responsible_name")

        # 管理员编辑自身时只允许更新负责人姓名，避免误改自己的角色或登录状态。
        if user == request.user:
            user.save(update_fields=update_fields)
            messages.success(request, "负责人姓名已更新。")
            return redirect("permission_center")

        group_ids = request.POST.getlist("groups")
        user.groups.set(groups.filter(pk__in=group_ids))
        user.is_active = request.POST.get("is_active") == "on"
        update_fields.append("is_active")
        user.save(update_fields=update_fields)
        messages.success(request, f"已更新用户“{user.username}”的权限。")
        return redirect("permission_center")
    users = User.objects.prefetch_related("groups").order_by("username")
    return render(request, "core/permission_center.html", {
        "users": users,
        "groups": groups,
        "can_delete_users": is_platform_admin(request.user),
        "can_view_account_passwords": is_platform_admin(request.user),
        "can_manage_user_profiles": is_platform_admin(request.user),
    })


@login_required
@require_POST
def permission_user_delete(request, pk):
    if not is_platform_admin(request.user):
        return HttpResponseForbidden("仅管理员可以删除其他账号。")
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        return HttpResponseForbidden("不能通过权限中心删除当前登录账号。")
    username = target_user.username
    target_user.delete()
    messages.success(request, f"账号“{username}”已删除。")
    return redirect("permission_center")


PROCESSING_STATUS_ALIASES = {
    "pending": "pending", "未处理": "pending",
    "success": "success", "成功": "success",
    "failed": "failed", "failure": "failed", "失败": "failed",
}


def normalize_processing_status(value):
    return PROCESSING_STATUS_ALIASES.get(str(value or "").strip().lower())


def resolve_store_from_external_payload(data):
    """Resolve external APIs by shop/store ID, while allowing a clear internal ID escape hatch."""
    internal_id = data.get("store_pk") or data.get("internal_store_id")
    if internal_id not in (None, ""):
        try:
            return Store.objects.get(pk=int(internal_id))
        except (Store.DoesNotExist, TypeError, ValueError):
            raise ValueError("store_pk 不存在")

    shop_id = str(data.get("shop_id") or data.get("shopid") or data.get("store_id") or "").strip()
    if not shop_id:
        raise ValueError("必须提供 store_id（店铺编号）或 store_pk（系统店铺主键）")
    stores = Store.objects.filter(external_id=shop_id)
    platform = normalize_platform(data.get("platform"))
    if data.get("platform") and not platform:
        raise ValueError("platform 不正确")
    if platform:
        stores = stores.filter(platform=platform)
    if stores.count() != 1:
        raise ValueError("店铺不存在或店铺编号跨平台重复，请补充 platform")
    return stores.get()


def external_store_data(store):
    return {
        "store_name": store.name,
        "store_id": store.external_id,
        "store_pk": store.pk,
        "platform": store.platform,
    }


def ensure_external_store_access(request, store):
    """Keep the unauthenticated collector API compatible without widening a logged-in client's scope."""
    if request.user.is_authenticated and is_customer_account(request.user) and store.customer_id != request.user.customer_id:
        raise PermissionError("客户账号不能访问其他客户的店铺数据")


def parse_required_external_date(value):
    value = str(value or "").strip()
    if not value:
        raise ValueError("date 必填，格式为 YYYY-MM-DD")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("date 格式应为 YYYY-MM-DD")


def invoice_queryset_for_user(user):
    invoices = InvoiceRecord.objects.select_related("store", "store__customer", "store__customer__portal_user")
    if is_customer_account(user):
        invoices = invoices.filter(store__customer_id=user.customer_id)
    return invoices


def get_invoice_center_context(request):
    invoices = invoice_queryset_for_user(request.user)
    is_client = is_customer_account(request.user)
    date_value = request.GET.get("date", "").strip()
    status = normalize_processing_status(request.GET.get("status"))
    customer_id = request.GET.get("customer", "").strip() if not is_client else ""
    store_query = request.GET.get("store", "").strip()
    order_no = request.GET.get("order_no", "").strip()

    if date_value:
        try:
            invoices = invoices.filter(created_at__date=datetime.strptime(date_value, "%Y-%m-%d").date())
        except ValueError:
            date_value = ""
            messages.error(request, "日期格式应为 YYYY-MM-DD。")
    if status:
        invoices = invoices.filter(status=status)
    if customer_id:
        try:
            invoices = invoices.filter(store__customer_id=int(customer_id))
        except ValueError:
            customer_id = ""
    if store_query:
        invoices = invoices.filter(Q(store__name__icontains=store_query) | Q(store__external_id__icontains=store_query))
    if order_no:
        invoices = invoices.filter(order_no__icontains=order_no)
    invoices = invoices.order_by("-created_at", "-pk")
    page_obj = Paginator(invoices, 50).get_page(request.GET.get("page", 1))
    rows = list(page_obj.object_list)
    visible_stores = customer_stores(request.user) if is_client else Store.objects.all()
    customers = Customer.objects.filter(stores__in=visible_stores).distinct().order_by("name") if not is_client else Customer.objects.none()
    return {
        "invoices": rows,
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        "date_value": date_value,
        "status": status or "",
        "customer_id": customer_id,
        "store_query": store_query,
        "order_no": order_no,
        "customers": customers,
        "is_client_account": is_client,
        "can_filter_customer": not is_client,
        "status_choices": InvoiceRecord.Status.choices,
    }


def _pagination_query(request):
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


def invoice_json_data(invoice, request):
    return {
        "id": invoice.pk,
        **external_store_data(invoice.store),
        "customer": invoice.store.customer.name if invoice.store.customer else "未归属",
        "order_no": invoice.order_no,
        "title_type": invoice.title_type,
        "company_subject": invoice.company_subject,
        "platform_name": invoice.platform or invoice.store.get_platform_display(),
        "invoice_title": invoice.invoice_title,
        "taxpayer_id": invoice.taxpayer_id,
        "product_name": invoice.product_name,
        "quantity": str(invoice.quantity),
        "amount": str(invoice.amount),
        "status": invoice.status,
        "status_label": invoice.get_status_display(),
        "created_at": timezone.localtime(invoice.created_at).strftime("%Y-%m-%d %H:%M"),
        "pdf_url": request.build_absolute_uri(reverse("invoice_download", args=[invoice.pk])) if invoice.pdf_file else "",
        "upload_url": reverse("invoice_upload_pdf", args=[invoice.pk]),
        "retry_url": reverse("invoice_retry", args=[invoice.pk]),
        "can_retry": invoice.status == InvoiceRecord.Status.FAILED,
    }


@login_required
def invoice_center(request):
    return render(request, "core/invoice_center.html", get_invoice_center_context(request))


@login_required
@require_GET
def invoice_center_api(request):
    context = get_invoice_center_context(request)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [invoice_json_data(invoice, request) for invoice in context["invoices"]],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


@login_required
@require_POST
def invoice_upload_pdf(request, pk):
    invoice = get_object_or_404(invoice_queryset_for_user(request.user), pk=pk)
    uploaded = request.FILES.get("pdf_file")
    if not uploaded:
        messages.error(request, "请选择 PDF 发票文件。")
    elif not uploaded.name.lower().endswith(".pdf"):
        messages.error(request, "仅支持上传 PDF 发票文件。")
    else:
        invoice.pdf_file = uploaded
        invoice.save(update_fields=["pdf_file", "updated_at"])
        messages.success(request, "PDF 发票已上传。")
    return redirect("invoice_center")


@login_required
@require_POST
def invoice_retry(request, pk):
    invoice = get_object_or_404(invoice_queryset_for_user(request.user), pk=pk)
    if invoice.status != InvoiceRecord.Status.FAILED:
        messages.error(request, "仅失败的发票可以重新上传。")
    else:
        invoice.status = InvoiceRecord.Status.PENDING
        invoice.processed_at = None
        invoice.save(update_fields=["status", "processed_at", "updated_at"])
        messages.success(request, "发票已恢复为未处理状态。")
    return redirect("invoice_center")


@require_GET
def invoice_download(request, pk):
    invoice = get_object_or_404(InvoiceRecord, pk=pk)
    try:
        ensure_external_store_access(request, invoice.store)
    except PermissionError as exc:
        return HttpResponseForbidden(str(exc))
    if not invoice.pdf_file:
        raise Http404("该发票尚未上传 PDF")
    return FileResponse(invoice.pdf_file.open("rb"), as_attachment=True, filename=f"{invoice.order_no}.pdf")


def message_queryset_for_user(user):
    tasks = MessageTask.objects.select_related("store", "store__customer", "created_by")
    if is_customer_account(user):
        tasks = tasks.filter(store__customer_id=user.customer_id)
    return tasks


def get_message_center_context(request):
    tasks = message_queryset_for_user(request.user)
    is_client = is_customer_account(request.user)
    date_value = request.GET.get("date", "").strip()
    status = normalize_processing_status(request.GET.get("status"))
    customer_id = request.GET.get("customer", "").strip() if not is_client else ""
    store_query = request.GET.get("store", "").strip()
    order_no = request.GET.get("order_no", "").strip()
    if date_value:
        try:
            tasks = tasks.filter(created_at__date=datetime.strptime(date_value, "%Y-%m-%d").date())
        except ValueError:
            date_value = ""
            messages.error(request, "日期格式应为 YYYY-MM-DD。")
    if status:
        tasks = tasks.filter(status=status)
    if customer_id:
        try:
            tasks = tasks.filter(store__customer_id=int(customer_id))
        except ValueError:
            customer_id = ""
    if store_query:
        tasks = tasks.filter(Q(store__name__icontains=store_query) | Q(store__external_id__icontains=store_query))
    if order_no:
        tasks = tasks.filter(order_no__icontains=order_no)
    tasks = tasks.order_by("-created_at", "-pk")
    page_obj = Paginator(tasks, 50).get_page(request.GET.get("page", 1))
    visible_stores = customer_stores(request.user) if is_client else Store.objects.all()
    customers = Customer.objects.filter(stores__in=visible_stores).distinct().order_by("name") if not is_client else Customer.objects.none()
    quick_replies = QuickReply.objects.select_related("customer")
    if is_client:
        quick_replies = quick_replies.filter(customer_id=request.user.customer_id)
    else:
        quick_replies = quick_replies.filter(customer__in=customers)
    return {
        "tasks": list(page_obj.object_list),
        "page_obj": page_obj,
        "pagination_query": _pagination_query(request),
        "date_value": date_value,
        "status": status or "",
        "customer_id": customer_id,
        "store_query": store_query,
        "order_no": order_no,
        "customers": customers,
        "stores": visible_stores.select_related("customer").order_by("customer__name", "name", "external_id"),
        "quick_replies": quick_replies.order_by("customer__name", "content"),
        "is_client_account": is_client,
        "can_filter_customer": not is_client,
        "can_change_status": not is_client,
        "status_choices": MessageTask.Status.choices,
    }


def message_json_data(task):
    return {
        "id": task.pk,
        **external_store_data(task.store),
        "customer": task.store.customer.name if task.store.customer else "未归属",
        "order_no": task.order_no,
        "reply_content": task.reply_content,
        "status": task.status,
        "status_label": task.get_status_display(),
        "created_at": timezone.localtime(task.created_at).strftime("%Y-%m-%d %H:%M"),
        "created_by": task.created_by.username if task.created_by else "已删除账号",
        "delete_url": reverse("message_task_delete", args=[task.pk]),
        "status_url": reverse("message_task_status", args=[task.pk]),
    }


@login_required
@require_http_methods(["GET", "POST"])
def message_center(request):
    context = get_message_center_context(request)
    if request.method == "POST":
        try:
            store = get_object_or_404(context["stores"], pk=request.POST.get("store_id"))
            order_no = request.POST.get("order_no", "").strip()
            reply_content = request.POST.get("reply_content", "").strip()
            if not order_no or not reply_content:
                raise ValueError("订单号和回复话术均为必填。")
            save_quick_reply = request.POST.get("save_quick_reply") == "on"
            if save_quick_reply and not store.customer_id:
                raise ValueError("未归属客户的店铺不能保存共享快捷回复。")
            task = MessageTask.objects.create(
                store=store, order_no=order_no, reply_content=reply_content, created_by=request.user
            )
            if save_quick_reply and not QuickReply.objects.filter(
                customer=store.customer, content=reply_content
            ).exists():
                QuickReply.objects.create(
                    customer=store.customer, content=reply_content, created_by=request.user
                )
            messages.success(request, f"留言任务“{task.order_no}”已登记。")
            return redirect("message_center")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "core/message_center.html", context)


@login_required
@require_GET
def message_center_api(request):
    context = get_message_center_context(request)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [message_json_data(task) for task in context["tasks"]],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


@login_required
@require_POST
def message_task_delete(request, pk):
    task = get_object_or_404(message_queryset_for_user(request.user), pk=pk)
    task.delete()
    messages.success(request, "留言任务已删除。")
    return redirect("message_center")


@login_required
@require_POST
def message_task_status(request, pk):
    if is_customer_account(request.user):
        return HttpResponseForbidden("客户账号不能修改留言处理状态。")
    task = get_object_or_404(MessageTask, pk=pk)
    status = normalize_processing_status(request.POST.get("status"))
    if not status:
        messages.error(request, "处理状态不正确。")
    else:
        task.status = status
        task.processed_at = timezone.now() if status != MessageTask.Status.PENDING else None
        task.save(update_fields=["status", "processed_at", "updated_at"])
        messages.success(request, "留言处理状态已更新。")
    return redirect("message_center")


def wechat_pending_group_data(group):
    content = group.content or ""
    messages = [line for line in content.splitlines() if line]
    return {
        "id": group.pk,
        "key": group.key,
        "name": group.name,
        "content": content,
        "messages": messages,
        "message_count": len(messages),
        "updated_at": group.updated_at.isoformat(),
        "updated_at_display": timezone.localtime(group.updated_at).strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_wechat_pending_group():
    """Create the shared pending-sending group on first use."""
    return WeChatPendingGroup.objects.get_or_create(
        key=WECHAT_PENDING_GROUP_KEY,
        defaults={"name": WECHAT_PENDING_GROUP_NAME},
    )[0]


def wechat_pending_content(data):
    for key in ("content", "message", "info", "text", "信息"):
        if data.get(key) is not None:
            content = str(data[key]).replace("\r\n", "\n").replace("\r", "\n").strip("\n")
            if content:
                return content
    raise ValueError("content（待发送信息）必填")


@login_required
@require_GET
def wechat_pending_group(request):
    if not can_view_all_after_sales(request.user):
        return HttpResponseForbidden("客户账号不能访问微信群待发送队列。")
    group = get_wechat_pending_group()
    return render(request, "core/wechat_pending_group.html", {
        "group": wechat_pending_group_data(group),
    })


@csrf_exempt
@require_POST
def api_wechat_pending_append(request):
    """Append one or more newline-delimited entries to the shared WeChat queue."""
    try:
        content = wechat_pending_content(parse_json(request))
        with transaction.atomic():
            group = get_wechat_pending_group()
            group = WeChatPendingGroup.objects.select_for_update().get(pk=group.pk)
            group.content = f"{group.content}\n{content}" if group.content else content
            group.save(update_fields=["content", "updated_at"])
        return JsonResponse({
            "ok": True,
            "message": "信息已存入微信群待发送队列",
            "data": wechat_pending_group_data(group),
        })
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_GET
def api_wechat_pending_read(request):
    """Return every queued entry, retaining the original newline-delimited content."""
    group = get_wechat_pending_group()
    return JsonResponse({"ok": True, "data": wechat_pending_group_data(group)})


@csrf_exempt
@require_POST
def api_wechat_pending_sent(request):
    """Acknowledge sending and atomically clear the queue that was acknowledged."""
    with transaction.atomic():
        group = get_wechat_pending_group()
        group = WeChatPendingGroup.objects.select_for_update().get(pk=group.pk)
        cleared_count = len([line for line in (group.content or "").splitlines() if line])
        group.content = ""
        group.save(update_fields=["content", "updated_at"])
    return JsonResponse({
        "ok": True,
        "status": "sent",
        "message": "已发送状态已回传，微信群待发送信息已清空",
        "cleared_count": cleared_count,
        "data": wechat_pending_group_data(group),
    })


# ----------------------------- 外部采集接口 -----------------------------

@csrf_exempt
@require_GET
def api_customers(request):
    customers = Customer.objects.filter(is_active=True).values("id", "name")
    if request.user.is_authenticated and is_customer_account(request.user):
        customers = customers.filter(id=request.user.customer_id)
    return JsonResponse({"ok": True, "data": list(customers)})


def external_value(data, *keys, default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def decimal_payload_value(data, keys, field_label):
    value = external_value(data, *keys, default=0)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_label} 必须是数字")


def invoice_from_payload(data):
    store = resolve_store_from_external_payload(data)
    order_no = str(external_value(data, "order_no", "order_id", "order_sn", "订单号")).strip()
    if not order_no:
        raise ValueError("order_no（订单号）必填")
    invoice = InvoiceRecord(
        store=store,
        order_no=order_no,
        title_type=str(external_value(data, "title_type", "header_type", "抬头类型")).strip(),
        company_subject=str(external_value(data, "company_subject", "company", "公司主体")).strip(),
        platform=str(external_value(data, "invoice_platform", "platform_name", "平台", default=store.get_platform_display())).strip(),
        invoice_title=str(external_value(data, "invoice_title", "title", "发票抬头")).strip(),
        taxpayer_id=str(external_value(data, "taxpayer_id", "tax_id", "纳税识别号")).strip(),
        product_name=str(external_value(data, "product_name", "goods_name", "商品名称")).strip(),
        quantity=decimal_payload_value(data, ("quantity", "count", "数量"), "quantity（数量）"),
        amount=decimal_payload_value(data, ("amount", "money", "金额"), "amount（金 额）"),
    )
    invoice.full_clean()
    return invoice


@csrf_exempt
@require_POST
def api_invoice_upload(request):
    """Write crawled invoice metadata. PDF files are deliberately not accepted here."""
    try:
        data = parse_json(request)
        payloads = data.get("invoices") or data.get("items") or [data]
        if not isinstance(payloads, list) or not payloads:
            raise ValueError("invoices 必须是非空数组，或直接提交一条发票 JSON")
        invoices = []
        with transaction.atomic():
            for payload in payloads:
                if not isinstance(payload, dict):
                    raise ValueError("每条发票数据必须是 JSON 对象")
                invoice = invoice_from_payload(payload)
                ensure_external_store_access(request, invoice.store)
                invoice.save()
                invoices.append(invoice)
        return JsonResponse({
            "ok": True,
            "message": "发票原始信息已写入，状态为未处理",
            "count": len(invoices),
            "data": [{"id": item.pk, **external_store_data(item.store), "order_no": item.order_no, "status": item.status} for item in invoices],
        }, status=201)
    except PermissionError as exc:
        return json_error(str(exc), 403)
    except ValueError as exc:
        return json_error(str(exc))
    except ValidationError as exc:
        return json_error("；".join(exc.messages))


@csrf_exempt
@require_GET
def api_invoice_pending(request):
    """Return at most 100 invoices uploaded on the requested date that remain pending."""
    try:
        selected_date = parse_required_external_date(request.GET.get("date"))
    except ValueError as exc:
        return json_error(str(exc))
    invoices = InvoiceRecord.objects.select_related("store").filter(
        status=InvoiceRecord.Status.PENDING,
        created_at__date=selected_date,
    ).order_by("created_at", "pk")
    if request.user.is_authenticated and is_customer_account(request.user):
        invoices = invoices.filter(store__customer_id=request.user.customer_id)
    invoices = invoices[:100]
    data = []
    for invoice in invoices:
        row = {
            "id": invoice.pk,
            **external_store_data(invoice.store),
            "shop_name": invoice.store.name,
            "shop_id": invoice.store.external_id,
            "order_no": invoice.order_no,
            "pdf_download_url": request.build_absolute_uri(reverse("invoice_download", args=[invoice.pk])) if invoice.pdf_file else "",
        }
        data.append(row)
    return JsonResponse({"ok": True, "date": selected_date.isoformat(), "count": len(data), "data": data})


def apply_external_status_updates(model, data, request, *, status_field="status"):
    items = data.get("items") or data.get("records") or data.get("data")
    if not isinstance(items, list) or not items:
        raise ValueError("items 必须是非空数组")
    updated = 0
    results = []
    with transaction.atomic():
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("items 中每一项必须是 JSON 对象")
            store = resolve_store_from_external_payload(item)
            ensure_external_store_access(request, store)
            order_no = str(external_value(item, "order_no", "order_id", "order_sn", "订单号")).strip()
            status = normalize_processing_status(item.get("status"))
            if not order_no:
                raise ValueError("order_no（订单号）必填")
            if status not in {"success", "failed"}:
                raise ValueError("status 仅支持 success（成功）或 failed（失败）")
            filters = {"store": store, "order_no": order_no}
            matching = model.objects.filter(**filters)
            count = matching.update(
                **{status_field: status, "processed_at": timezone.now(), "updated_at": timezone.now()}
            )
            updated += count
            results.append({**external_store_data(store), "order_no": order_no, "status": status, "updated": count})
    return updated, results


@csrf_exempt
@require_POST
def api_invoice_status_update(request):
    try:
        updated, results = apply_external_status_updates(InvoiceRecord, parse_json(request), request)
        return JsonResponse({"ok": True, "updated": updated, "data": results})
    except PermissionError as exc:
        return json_error(str(exc), 403)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_GET
def api_message_pending(request):
    tasks = MessageTask.objects.select_related("store").filter(status=MessageTask.Status.PENDING).order_by("created_at", "pk")
    if request.user.is_authenticated and is_customer_account(request.user):
        tasks = tasks.filter(store__customer_id=request.user.customer_id)
    tasks = tasks[:100]
    data = [{
        "id": task.pk,
        **external_store_data(task.store),
        "shop_name": task.store.name,
        "shop_id": task.store.external_id,
        "order_no": task.order_no,
        "reply_content": task.reply_content,
        "message_content": task.reply_content,
    } for task in tasks]
    return JsonResponse({"ok": True, "count": len(data), "data": data})


@csrf_exempt
@require_POST
def api_message_status_update(request):
    try:
        if request.user.is_authenticated and is_customer_account(request.user):
            raise PermissionError("客户账号不能批量修改留言处理状态")
        updated, results = apply_external_status_updates(MessageTask, parse_json(request), request)
        return JsonResponse({"ok": True, "updated": updated, "data": results})
    except PermissionError as exc:
        return json_error(str(exc), 403)
    except ValueError as exc:
        return json_error(str(exc))


def resolve_store_from_pending_task_payload(data):
    store_id = data.get("store_id") or data.get("id")
    if store_id not in (None, ""):
        try:
            return Store.objects.get(pk=int(store_id))
        except (Store.DoesNotExist, TypeError, ValueError):
            raise ValueError("store_id 不存在")

    shop_id = str(data.get("shop_id") or "").strip()
    if not shop_id:
        raise ValueError("必须提供 store_id（系统店铺主键）或 shop_id（店铺编号）")
    stores = Store.objects.filter(external_id=shop_id)
    platform = normalize_platform(data.get("platform"))
    if data.get("platform") and not platform:
        raise ValueError("platform 不正确")
    if platform:
        stores = stores.filter(platform=platform)
    if stores.count() != 1:
        raise ValueError("店铺不存在或 shop_id 跨平台重复，请补充正确的 platform")
    return stores.get()


@csrf_exempt
@require_POST
def api_pending_task_create(request):
    """采集端创建待处理事务；负责人由店铺认领关系自动确定。"""
    try:
        data = parse_json(request)
        store = resolve_store_from_pending_task_payload(data)
        time_type = normalize_pending_task_time_type(data.get("time_type") or data.get("type"))
        if not time_type:
            raise ValueError("time_type 为必填，只能是 normal/普通 或 urgent/紧急")
        handling_item = str(data.get("handling_item") or data.get("matter") or data.get("content") or "").strip()
        if not handling_item:
            raise ValueError("handling_item（处理事项）为必填")
        task = PendingTask.objects.create(store=store, time_type=time_type, handling_item=handling_item)
        return JsonResponse({"ok": True, "message": "待处理事务已创建", "data": pending_task_api_data(task)}, status=201)
    except ValueError as exc:
        return json_error(str(exc))


@login_required
@require_GET
def api_pending_tasks(request):
    """返回当前负责人可见的全部未处理事务；管理员可按账号筛选或查看全部。"""
    requested_account_name = str(request.GET.get("account_name") or request.GET.get("username") or "").strip()
    viewer_can_view_all = can_view_all_pending_tasks(request.user)
    target_user = request.user
    if requested_account_name:
        target_user = User.objects.filter(username=requested_account_name).first()
        if not target_user:
            return json_error("未找到该系统账号", 404)
        if not viewer_can_view_all and target_user != request.user:
            return json_error("只能查看自己的待处理事务", 403)

    tasks = pending_tasks_visible_to(request.user)
    if viewer_can_view_all and requested_account_name:
        tasks = tasks.filter(store__shift_claims__user=target_user).distinct()
    return JsonResponse({
        "ok": True,
        "account_name": target_user.username if requested_account_name else None,
        "scope": "all" if viewer_can_view_all and not requested_account_name else "own",
        "count": tasks.count(),
        "data": [pending_task_api_data(task) for task in tasks],
    })


@csrf_exempt
@require_POST
def api_cookie_upsert(request):
    try:
        data = parse_json(request)
        shop_id = str(data.get("shop_id") or "").strip()
        cookie = str(data.get("cookie") or "").strip()
        if not shop_id or not cookie:
            raise ValueError("shop_id 和 cookie 均为必填")
        raw_platform = data.get("platform")
        platform = normalize_platform(raw_platform)
        if raw_platform and not platform:
            raise ValueError("platform 只能是 pdd、douyin、jingdong 或对应中文平台名")
        with transaction.atomic():
            matches = Store.objects.select_for_update().filter(external_id=shop_id)
            if platform:
                matches = matches.filter(platform=platform)
            count = matches.count()
            if count > 1:
                raise ValueError("该 shop_id 在多个平台存在；更新时请补传 platform")
            if count == 1:
                store = matches.get()
                store.cookie = cookie
                store.save(update_fields=["cookie", "cookie_updated_at"])
                created = False
            else:
                shop_name = str(data.get("shop_name") or "").strip()
                if not platform or not shop_name:
                    raise ValueError("新增店铺必须提供 platform、shop_id、shop_name 和 cookie；customer 不需要上传")
                status = data.get("cookie_status", Store.CookieStatus.VALID)
                if status not in Store.CookieStatus.values:
                    raise ValueError("cookie_status 只能是 valid、invalid 或 disabled")
                category = str(data.get("main_category") or "notfind").strip() or "notfind"
                store = Store.objects.create(platform=platform, external_id=shop_id, name=shop_name, cookie=cookie, cookie_status=status, main_category=category)
                created = True
            logged_in_account = str(data.get("account_name") or data.get("login_account") or "").strip()
            captured_account_id = None
            try:
                _, captured_account_id = capture_missing_human_account_id_from_cookie(
                    cookie, account_name=logged_in_account, shop_id=store.external_id,
                    platform=store.platform,
                )
                account_id_capture_error = None
            except ValueError as exc:
                # Cookie 上传不应因同店有多个待匹配账号而失败；将原因返回给采集端。
                account_id_capture_error = str(exc)
        response_data = cookie_api_data(store)
        if captured_account_id:
            response_data["captured_account_id"] = captured_account_id
        if account_id_capture_error:
            response_data["account_id_capture_error"] = account_id_capture_error
        return JsonResponse({"ok": True, "created": created, "message": "Cookie 已新增" if created else "Cookie 已更新", "data": response_data}, status=201 if created else 200)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_GET
def api_cookies(request):
    platform = normalize_platform(request.GET.get("platform"))
    if not platform:
        return json_error("请传入 platform（pdd/拼多多、douyin/抖音 或 jingdong/京东）")
    stores = Store.objects.filter(platform=platform).select_related("customer").prefetch_related("accounts")
    customer_value = request.GET.get("customer") or request.GET.get("customer_id")
    if customer_value:
        if request.GET.get("customer_id"):
            stores = stores.filter(customer_id=customer_value)
        else:
            stores = stores.filter(customer__name=customer_value)
    return JsonResponse({"ok": True, "count": stores.count(), "data": [cookie_api_data(store, include_cookie=True) for store in stores]})


@csrf_exempt
@require_POST
def api_robot_cookie_upsert(request):
    try:
        data = parse_json(request)
        shop_id = str(data.get("shop_id") or "").strip()
        cookie = str(data.get("cookie") or "").strip()
        if not shop_id or not cookie:
            raise ValueError("shop_id 和 cookie 均为必填")
        raw_platform = data.get("platform")
        platform = normalize_platform(raw_platform)
        if raw_platform and not platform:
            raise ValueError("platform 只能是 pdd、douyin、jingdong 或对应中文平台名")
        with transaction.atomic():
            matches = Store.objects.select_for_update().filter(external_id=shop_id)
            if platform:
                matches = matches.filter(platform=platform)
            count = matches.count()
            if count > 1:
                raise ValueError("该 shop_id 在多个平台存在；更新时请补传 platform")
            if count == 1:
                store = matches.get()
                store.robot_cookie = cookie
                store.save(update_fields=["robot_cookie", "robot_cookie_updated_at"])
                created = False
            else:
                shop_name = str(data.get("shop_name") or "").strip()
                if not platform or not shop_name:
                    raise ValueError("新增店铺必须提供 platform、shop_id、shop_name 和 cookie；customer 不需要上传")
                status = data.get("cookie_status", Store.CookieStatus.VALID)
                if status not in Store.CookieStatus.values:
                    raise ValueError("cookie_status 只能是 valid、invalid 或 disabled")
                category = str(data.get("main_category") or "notfind").strip() or "notfind"
                store = Store.objects.create(
                    platform=platform,
                    external_id=shop_id,
                    name=shop_name,
                    robot_cookie=cookie,
                    cookie_status=status,
                    main_category=category,
                )
                created = True
        return JsonResponse({
            "ok": True,
            "created": created,
            "message": "机器人 Cookie 已新增" if created else "机器人 Cookie 已更新",
            "data": robot_cookie_api_data(store),
        }, status=201 if created else 200)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_GET
def api_robot_cookies(request):
    platform = normalize_platform(request.GET.get("platform"))
    if not platform:
        return json_error("请传入 platform（pdd/拼多多、douyin/抖音 或 jingdong/京东）")
    stores = Store.objects.filter(platform=platform).select_related("customer").prefetch_related("accounts")
    customer_value = request.GET.get("customer") or request.GET.get("customer_id")
    if customer_value:
        if request.GET.get("customer_id"):
            stores = stores.filter(customer_id=customer_value)
        else:
            stores = stores.filter(customer__name=customer_value)
    return JsonResponse({
        "ok": True,
        "count": stores.count(),
        "data": [robot_cookie_api_data(store, include_cookie=True) for store in stores],
    })


@csrf_exempt
@require_POST
def api_cookie_invalidate(request):
    try:
        data = parse_json(request)
        shop_id = str(data.get("shop_id") or "").strip()
        if not shop_id:
            raise ValueError("shop_id 为必填")
        stores = Store.objects.filter(external_id=shop_id)
        platform = normalize_platform(data.get("platform"))
        if data.get("platform") and not platform:
            raise ValueError("platform 不正确")
        if platform:
            stores = stores.filter(platform=platform)
        count = stores.count()
        if not count:
            return json_error("未找到店铺", 404)
        if count > 1 and not platform:
            return json_error("该 shop_id 在多个平台存在，请补传 platform", 409)
        stores.update(cookie_status=Store.CookieStatus.INVALID)
        return JsonResponse({"ok": True, "message": "Cookie 已置为失效", "updated": count})
    except ValueError as exc:
        return json_error(str(exc))


STORE_SPECIALIST_METRIC_FIELDS = {
    "specialist_reply_count": ("specialist_reply_count", int),
    "specialist_three_minute_reply_rate": ("three_minute_reply_rate", Decimal),
    "specialist_timeout_count": ("timeout_count", int),
    "specialist_yesterday_average_response_seconds": ("average_response_seconds", Decimal),
    "pending_after_sales": ("pending_after_sales", int),
    "pending_tickets": ("pending_tickets", int),
    "today_order_count": ("today_order_count", int),
    "today_turnover": ("today_turnover", Decimal),
    "today_ad_spend": ("today_ad_spend", Decimal),
    "store_experience_score": ("store_experience_score", Decimal),
    "service_experience_score": ("service_experience_score", Decimal),
}

ROBOT_METRIC_FIELDS = {
    "robot_completed_reply_count": ("robot_completed_reply_count", int),
    "robot_completed_reply_rate": ("robot_completed_reply_rate", Decimal),
    "robot_transferred_count": ("robot_transferred_count", int),
    "robot_timeout_count": ("robot_timeout_count", int),
    "robot_three_minute_reply_rate": ("robot_three_minute_reply_rate", Decimal),
}

STORE_SNAPSHOT_FIELDS = tuple(dict.fromkeys(
    [model_key for model_key, _ in STORE_SPECIALIST_METRIC_FIELDS.values()]
    + [model_key for model_key, _ in ROBOT_METRIC_FIELDS.values()]
    + ["consultation_count"]
))

SHIFT_SUMMARY_METRIC_FIELDS = {
    **STORE_SPECIALIST_METRIC_FIELDS,
    "specialist_reply_count": ("consultation_count", int),
}

def resolve_store_from_metric_payload(data):
    shop_id = str(data.get("shop_id") or "").strip()
    if not shop_id:
        raise ValueError("shop_id 为必填")
    stores = Store.objects.filter(external_id=shop_id)
    platform = normalize_platform(data.get("platform"))
    if data.get("platform") and not platform:
        raise ValueError("platform 不正确")
    if platform:
        stores = stores.filter(platform=platform)
    if stores.count() != 1:
        raise ValueError("店铺不存在或 shop_id 跨平台重复，请补传正确的 platform")
    return stores.get()


def normalize_pdd_realtime_reply_fields(data):
    """兼容拼多多 getCsRealTimeReplyData 的原始 result 数据。"""
    source = data.get("result") if isinstance(data.get("result"), dict) else data
    if "recv_user" in source and "specialist_reply_count" not in data:
        data["specialist_reply_count"] = source["recv_user"]
    if "reply_rate" in source and "specialist_three_minute_reply_rate" not in data:
        raw_rate = source["reply_rate"]
        if raw_rate is None:
            data["specialist_three_minute_reply_rate"] = None
        try:
            # 拼多多以 0~1 小数返回，例如 1.0 表示 100%。
            data["specialist_three_minute_reply_rate"] = Decimal(str(raw_rate)) * 100
        except (ValueError, TypeError, InvalidOperation):
            # 无权限、接口异常等文字继续走通用展示值处理。
            data["specialist_three_minute_reply_rate"] = raw_rate

    # 兼容拼多多旧采集端直接上传 0~1 小数的情况；新版采集端上传百分比时不会重复换算。
    if normalize_platform(data.get("platform")) != Store.Platform.PDD:
        return
    raw_rate = data.get("specialist_three_minute_reply_rate")
    if raw_rate is None:
        return
    try:
        rate = Decimal(str(raw_rate))
    except (ValueError, TypeError, InvalidOperation):
        return
    if Decimal("0") <= rate <= Decimal("1"):
        data["specialist_three_minute_reply_rate"] = rate * 100


def parse_metric_values(data, fields):
    values = {}
    display_values = {}
    for request_key, (model_key, converter) in fields.items():
        if request_key not in data:
            continue
        raw_value = data[request_key]
        if raw_value is None:
            values[model_key] = None
            display_values[model_key] = None
            continue
        try:
            value = converter(str(raw_value)) if converter is Decimal else converter(raw_value)
        except (ValueError, TypeError, InvalidOperation):
            text_value = str(raw_value).strip()
            if not text_value:
                values[model_key] = None
                display_values[model_key] = None
                continue
            # 采集端可用“无权限”等文字替代没有权限读取的数值。
            values[model_key] = None
            display_values[model_key] = text_value
            continue
        if value < 0:
            raise ValueError(f"{request_key} 不能小于 0")
        values[model_key] = value
        display_values[model_key] = None
    return values, display_values


def value_as_nonnegative_int(value):
    """咨询数的计算只使用可确定的数字；空值或文字状态统一按 0。"""
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError, InvalidOperation):
        return 0


def update_consultation_count(metric):
    metric.consultation_count = (
        value_as_nonnegative_int(metric.specialist_reply_count)
        + value_as_nonnegative_int(metric.robot_completed_reply_count)
    )


def metric_snapshot_values(metric):
    values = {field: getattr(metric, field) for field in STORE_SNAPSHOT_FIELDS}
    values["metric_display_values"] = metric.metric_display_values
    return values


def discard_pdd_timeout_inputs(store, values, display_values):
    """PDD timeout fields are derived locally and never use an upstream raw value."""
    if store.platform != Store.Platform.PDD:
        return
    for field in ("timeout_count", "robot_timeout_count"):
        values.pop(field, None)
        # Remove any older text override so the derived value is visible as well.
        display_values[field] = None


def assert_no_robot_fields(data):
    used_fields = sorted(set(data).intersection(ROBOT_METRIC_FIELDS))
    if used_fields:
        raise ValueError("机器人数据请改用 /api/v1/robot-metrics/upsert/ 上传")


def save_store_metric_snapshot(store, metric, data):
    report_date = parse_date_or_today(data.get("report_date"))
    if "time" not in data:
        raise ValueError("店铺数据接口必须提供 time（0 到 23 的整数）")
    report_hour = parse_hour_or_current(data.get("time"))
    snapshot, snapshot_created = StoreMetricSnapshot.objects.update_or_create(
        store=store,
        report_date=report_date,
        report_hour=report_hour,
        defaults=metric_snapshot_values(metric),
    )
    return snapshot, snapshot_created


def merge_metric_display_values(existing_values, changed_values):
    """将本次上报的文字覆盖项合并到既有展示值中。"""
    merged = dict(existing_values or {})
    for field, text_value in changed_values.items():
        if text_value is None:
            merged.pop(field, None)
        else:
            merged[field] = text_value
    return merged


@csrf_exempt
@require_POST
def api_store_metrics_upsert(request):
    try:
        data = parse_json(request)
        normalize_pdd_realtime_reply_fields(data)
        store = resolve_store_from_metric_payload(data)
        assert_no_robot_fields(data)
        parse_date_or_today(data.get("report_date"))
        if "time" not in data:
            raise ValueError("店铺数据接口必须提供 time（0 到 23 的整数）")
        parse_hour_or_current(data.get("time"))
        values, display_values = parse_metric_values(data, STORE_SPECIALIST_METRIC_FIELDS)
        discard_pdd_timeout_inputs(store, values, display_values)
        current_metric = StoreMetric.objects.filter(store=store).only("metric_display_values").first()
        values["metric_display_values"] = merge_metric_display_values(
            current_metric.metric_display_values if current_metric else {},
            {**display_values, "consultation_count": None},
        )
        metric, created = StoreMetric.objects.update_or_create(store=store, defaults=values)
        update_consultation_count(metric)
        metric.save(update_fields=["consultation_count", "metric_display_values", "data_updated_at"])
        snapshot, snapshot_created = save_store_metric_snapshot(store, metric, data)
        return JsonResponse({"ok": True, "created": created, "snapshot_created": snapshot_created, "message": "专员店铺数据及小时快照已更新", "consultation_count": metric.consultation_count, "data_updated_at": metric.data_updated_at.isoformat(), "report_date": snapshot.report_date.isoformat(), "report_hour": snapshot.report_hour})
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_POST
def api_robot_metrics_upsert(request):
    """独立接收机器人数据，并自动重算店铺咨询数。"""
    try:
        data = parse_json(request)
        store = resolve_store_from_metric_payload(data)
        parse_date_or_today(data.get("report_date"))
        if "time" not in data:
            raise ValueError("机器人数据接口必须提供 time（0 到 23 的整数）")
        parse_hour_or_current(data.get("time"))
        values, display_values = parse_metric_values(data, ROBOT_METRIC_FIELDS)
        if not values:
            raise ValueError("至少需要上传一项机器人数据")
        discard_pdd_timeout_inputs(store, values, display_values)
        current_metric = StoreMetric.objects.filter(store=store).only("metric_display_values").first()
        values["metric_display_values"] = merge_metric_display_values(
            current_metric.metric_display_values if current_metric else {},
            {**display_values, "consultation_count": None},
        )
        metric, created = StoreMetric.objects.update_or_create(store=store, defaults=values)
        update_consultation_count(metric)
        metric.save(update_fields=["consultation_count", "metric_display_values", "data_updated_at"])
        snapshot, snapshot_created = save_store_metric_snapshot(store, metric, data)
        return JsonResponse({"ok": True, "created": created, "snapshot_created": snapshot_created, "message": "机器人数据及小时快照已更新", "consultation_count": metric.consultation_count, "data_updated_at": metric.data_updated_at.isoformat(), "report_date": snapshot.report_date.isoformat(), "report_hour": snapshot.report_hour})
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_POST
def api_shift_daily_summary_upsert(request):
    """班次基线接口：独立保存每日班次值，同时冻结当班客服归属。"""
    try:
        data = parse_json(request)
        store = resolve_store_from_metric_payload(data)
        shift = normalize_shift(data.get("shift"))
        if not shift:
            raise ValueError("shift 为必填，只能是 morning/早班 或 evening/晚班")
        claim = StoreShiftClaim.objects.select_related("user").filter(store=store, shift=shift).first()
        if not claim:
            raise ValueError("该店铺当前班次尚未认领，无法保存班次总结")
        assert_no_robot_fields(data)
        values, display_values = parse_metric_values(data, SHIFT_SUMMARY_METRIC_FIELDS)
        if not values:
            raise ValueError("班次总结至少需要上传一项店铺数据")
        summary_date = parse_summary_date_payload(data)
        defaults = {model_key: values.get(model_key, 0) for model_key, _ in SHIFT_SUMMARY_METRIC_FIELDS.values()}
        existing_summary = ShiftDailySummary.objects.filter(
            store=store, summary_date=summary_date, shift=shift
        ).only("metric_display_values").first()
        defaults["metric_display_values"] = merge_metric_display_values(
            existing_summary.metric_display_values if existing_summary else {}, display_values
        )
        defaults["user"] = claim.user
        summary, created = ShiftDailySummary.objects.update_or_create(store=store, summary_date=summary_date, shift=shift, defaults=defaults)
        return JsonResponse({"ok": True, "created": created, "message": "班次基线已保存，可用于客服绩效和月度回复", "summary_date": summary.summary_date.isoformat(), "shift": summary.shift, "customer_service": claim.user.username})
    except ValueError as exc:
        return json_error(str(exc))


def daily_summary_api_data(summary):
    def value_for(field):
        display_values = summary.metric_display_values or {}
        if field in display_values:
            return display_values[field]
        value = getattr(summary, field)
        return str(value) if isinstance(value, Decimal) else value

    return {
        "shop_id": summary.store.external_id,
        "shop_name": summary.store.name,
        "platform": summary.store.platform,
        "shift": summary.shift,
        "shift_name": summary.get_shift_display(),
        "year": summary.summary_date.year,
        "month": summary.summary_date.month,
        "day": summary.summary_date.day,
        "customer_service": summary.user.username if summary.user else None,
        "specialist_reply_count": value_for("consultation_count"),
        "specialist_three_minute_reply_rate": value_for("three_minute_reply_rate"),
        "specialist_timeout_count": value_for("timeout_count"),
        "specialist_yesterday_average_response_seconds": value_for("average_response_seconds"),
        "pending_after_sales": value_for("pending_after_sales"),
        "pending_tickets": value_for("pending_tickets"),
        "today_order_count": value_for("today_order_count"),
        "today_turnover": value_for("today_turnover"),
        "today_ad_spend": value_for("today_ad_spend"),
        "store_experience_score": value_for("store_experience_score"),
        "service_experience_score": value_for("service_experience_score"),
    }


@csrf_exempt
@require_GET
def api_morning_baseline(request):
    """仅传店铺 ID，即可读取该店铺最新上传的早班基线。"""
    shop_id = str(request.GET.get("id") or request.GET.get("shop_id") or "").strip()
    if not shop_id:
        return json_error("请传入 id（店铺 ID）")
    stores = Store.objects.filter(external_id=shop_id)
    if not stores.exists() and shop_id.isdigit():
        stores = Store.objects.filter(pk=int(shop_id))
    count = stores.count()
    if not count:
        return json_error("未找到店铺", 404)
    if count > 1:
        return json_error("该店铺 ID 在多个平台重复，无法仅凭 id 查询", 409)
    summary = ShiftDailySummary.objects.select_related("store", "user").filter(store=stores.get(), shift=StoreShiftClaim.Shift.MORNING).order_by("-summary_date", "-updated_at").first()
    if not summary:
        return json_error("该店铺暂无早班基线", 404)
    return JsonResponse({"ok": True, "data": daily_summary_api_data(summary)})


@csrf_exempt
@require_GET
def api_account_stores(request):
    """按系统账号名查询其认领管理的全部店铺。"""
    account_name = str(request.GET.get("account_name") or request.GET.get("username") or "").strip()
    if not account_name:
        return json_error("请传入 account_name（系统账号名）")
    user = User.objects.filter(username=account_name).first()
    if not user:
        return json_error("未找到该系统账号", 404)
    claims = StoreShiftClaim.objects.filter(user=user).select_related("store", "store__customer").order_by("store__name", "shift")
    stores = {}
    for claim in claims:
        row = stores.setdefault(claim.store_id, {
            "shop_id": claim.store.external_id,
            "shop_name": claim.store.name,
            "platform": claim.store.platform,
            "platform_name": claim.store.get_platform_display(),
            "customer": claim.store.customer.name if claim.store.customer else None,
            "responsible_slots": [],
        })
        row["responsible_slots"].append("负责人 1" if claim.shift == StoreShiftClaim.Shift.MORNING else "负责人 2")
    return JsonResponse({"ok": True, "account_name": user.username, "count": len(stores), "data": list(stores.values())})


@csrf_exempt
@require_POST
def api_account_id_upsert(request):
    try:
        data = parse_json(request)
        account_name = str(data.get("account_name") or data.get("login_account") or "").strip()
        account_id = str(data.get("account_id") or "").strip()
        cookie = str(data.get("cookie") or "").strip()
        shop_id = str(data.get("shop_id") or "").strip()
        if cookie:
            if not (account_name or shop_id):
                raise ValueError("自动抓取账号 ID 时至少需要传入 shop_id、account_name 或 login_account")
        elif not account_name or not account_id:
            raise ValueError("手动回传时 account_name 和 account_id 均为必填")
        raw_platform = data.get("platform")
        platform = normalize_platform(raw_platform)
        if raw_platform and not platform:
            raise ValueError("platform 只能是 pdd、douyin、jingdong 或对应中文平台名")
        if cookie:
            account, captured_account_id = capture_missing_human_account_id_from_cookie(
                cookie, account_name=account_name, shop_id=shop_id, platform=platform
            )
            if not account:
                return JsonResponse({
                    "ok": True,
                    "message": "匹配到的专员账号已有账号 ID，未重复自动抓取",
                    "updated": 0,
                    "skipped": True,
                })
            return JsonResponse({
                "ok": True,
                "message": "已根据 Cookie 自动抓取并更新专员账号 ID",
                "updated": 1,
                "account_id": captured_account_id,
                "account_name": account.name,
                "shop_id": account.store.external_id,
            })

        accounts = matching_accounts_for_id_capture(account_name, shop_id=shop_id, platform=platform)
        count = accounts.update(external_id=account_id)
        if not count:
            return json_error("未找到账号", 404)
        return JsonResponse({"ok": True, "message": "账号 ID 已更新", "updated": count})
    except ValueError as exc:
        return json_error(str(exc))


# ----------------------------- AI 知识库 -----------------------------


def ai_scope_model(scope):
    return {
        "customer": Customer,
        "store": Store,
        "product": Product,
        "material": CustomerMaterial,
    }.get(scope)


def get_ai_scope_object(scope, pk):
    model = ai_scope_model(scope)
    if not model:
        raise Http404("未知的知识库类型")
    select_related = {
        "customer": (),
        "store": ("customer",),
        "product": ("store", "store__customer", "material", "material__customer"),
        "material": ("customer",),
    }[scope]
    return get_object_or_404(model.objects.select_related(*select_related), pk=pk)


def ai_scope_filter(scope, obj):
    return {scope: obj}


def order_urging_script_for_scope(scope, obj):
    if scope not in ("customer", "store", "product"):
        return None
    return OrderUrgingScript.objects.filter(**ai_scope_filter(scope, obj)).first()


def order_urging_parent_scope(scope, obj):
    if scope == "store" and obj.customer_id:
        return "customer", obj.customer
    if scope == "product":
        return "store", obj.store
    return None, None


def resolve_order_urging_value(scope, obj, field_name):
    """Resolve one script field through customer -> store -> product inheritance."""
    script = order_urging_script_for_scope(scope, obj)
    content = str(getattr(script, field_name, "") or "").strip()
    if content:
        return {"content": content, "source_scope": scope, "blocked_by_scope": ""}

    if script and scope in ("store", "product") and getattr(script, f"block_parent_{field_name}"):
        return {"content": "", "source_scope": "", "blocked_by_scope": scope}

    parent_scope, parent_obj = order_urging_parent_scope(scope, obj)
    if parent_obj:
        return resolve_order_urging_value(parent_scope, parent_obj, field_name)
    return {"content": "", "source_scope": "", "blocked_by_scope": ""}


def order_urging_context(scope, obj):
    """Build editable local values and effective inherited values for the knowledge page."""
    if scope not in ("customer", "store", "product"):
        return {"rows": []}

    script = order_urging_script_for_scope(scope, obj)
    parent_scope, parent_obj = order_urging_parent_scope(scope, obj)
    scope_labels = {"customer": "客户", "store": "店铺", "product": "商品"}
    rows = []
    for field_name, label in ORDER_URGING_FIELDS:
        result = resolve_order_urging_value(scope, obj, field_name)
        if result["content"]:
            source_scope = result["source_scope"]
            source_label = "本层配置" if source_scope == scope else f"继承自{scope_labels[source_scope]}"
            effective_content = result["content"]
        elif result["blocked_by_scope"]:
            source_label = f"{scope_labels[result['blocked_by_scope']]}已屏蔽上级"
            effective_content = "无"
        else:
            source_label = "未配置"
            effective_content = "无"
        rows.append({
            "field_name": field_name,
            "label": label,
            "content": getattr(script, field_name, "") if script else "",
            "is_blocked": bool(script and getattr(script, f"block_parent_{field_name}")),
            "can_block_parent": bool(parent_obj),
            "block_label": f"屏蔽{scope_labels[parent_scope]}的{label}话术" if parent_obj else "",
            "effective_content": effective_content,
            "effective_source": source_label,
        })
    return {"rows": rows}


def save_order_urging_script(scope, obj, post_data, user):
    if scope not in ("customer", "store", "product"):
        raise ValueError("只有客户、店铺和商品可以配置催单话术")

    values = {
        field_name: str(post_data.get(field_name, "") or "").strip()
        for field_name, _label in ORDER_URGING_FIELDS
    }
    parent_scope, parent_obj = order_urging_parent_scope(scope, obj)
    blocks = {
        field_name: bool(parent_obj and post_data.get(f"block_parent_{field_name}") == "on")
        for field_name, _label in ORDER_URGING_FIELDS
    }
    filters = ai_scope_filter(scope, obj)
    script = OrderUrgingScript.objects.filter(**filters).first()

    if not any(values.values()) and not any(blocks.values()):
        if script:
            script.delete()
        return

    update_values = {
        **values,
        **{f"block_parent_{field_name}": is_blocked for field_name, is_blocked in blocks.items()},
    }
    if script:
        for field_name, value in update_values.items():
            setattr(script, field_name, value)
        script.save(update_fields=[*update_values, "updated_at"])
    else:
        OrderUrgingScript.objects.create(**filters, **update_values, created_by=user)


def ai_scope_store(scope, obj):
    if scope == "store":
        return obj
    if scope == "product":
        return obj.store
    return None


def ai_scope_customer(scope, obj):
    if scope == "customer":
        return obj
    if scope == "store":
        return obj.customer
    if scope == "product":
        return obj.store.customer
    if scope == "material":
        return obj.customer
    return None


def can_edit_ai_scope(user, scope, obj):
    """知识库全员可见；只有店铺认领负责人及平台管理员可以维护其负责范围。"""
    if is_customer_account(user):
        return False
    if is_platform_admin(user):
        return True
    store = ai_scope_store(scope, obj)
    if store:
        return StoreShiftClaim.objects.filter(store=store, user=user).exists()
    customer = ai_scope_customer(scope, obj)
    if customer:
        return StoreShiftClaim.objects.filter(store__customer=customer, user=user).exists()
    return False


def can_view_ai_scope(user, scope, obj):
    """Client accounts may only read explicitly enabled knowledge for their customer."""
    if not is_customer_account(user):
        return True
    customer = ai_scope_customer(scope, obj)
    if not customer or customer.pk != user.customer_id:
        return False
    if scope == "store":
        return customer.allow_store_knowledge_view
    if scope == "product":
        return customer.allow_product_knowledge_view
    return False


def only_mine_ai_scope(queryset, scope, user):
    if is_customer_account(user):
        filters = {
            "customer": {"pk": user.customer_id},
            "store": {"customer_id": user.customer_id},
            "product": {"store__customer_id": user.customer_id},
            "material": {"customer_id": user.customer_id},
        }
        return queryset.filter(**filters.get(scope, {"pk__in": []}))
    if scope == "customer":
        return queryset.filter(stores__shift_claims__user=user).distinct()
    if scope == "store":
        return queryset.filter(shift_claims__user=user).distinct()
    if scope == "product":
        return queryset.filter(store__shift_claims__user=user).distinct()
    if scope == "material":
        return queryset.filter(customer__stores__shift_claims__user=user).distinct()
    return queryset.none()


def product_title(product):
    payload = product.payload if isinstance(product.payload, dict) else {}
    for field in ("goods_name", "goodsName", "title", "product_name", "name"):
        value = payload.get(field)
        if value not in (None, ""):
            return str(value)
    return "未提供商品标题"


def normalize_image_urls(value):
    """兼容哈基米商品资料的图片数组，也兼容单个外部图片链接。"""
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        return []
    urls = []
    for item in raw_items:
        if isinstance(item, dict):
            item = next((item.get(key) for key in ("url", "src", "image_url", "imageUrl") if item.get(key)), "")
        url = str(item or "").strip()
        if url.startswith(("https://", "http://", "//")) and url not in urls:
            urls.append(url)
    return urls


def product_image_urls(product_or_payload):
    payload = product_or_payload.payload if isinstance(product_or_payload, Product) else product_or_payload
    payload = payload if isinstance(payload, dict) else {}
    main_value = next((payload.get(key) for key in ("mainimgurls", "mainImgUrls", "main_image_urls", "main_images", "images") if payload.get(key)), [])
    detail_value = next((payload.get(key) for key in ("detailimgurls", "detailImgUrls", "detail_image_urls", "detail_images") if payload.get(key)), [])
    return {"main": normalize_image_urls(main_value), "detail": normalize_image_urls(detail_value)}


def product_sku_rows(product_or_payload):
    """将哈基米的 skudetails 等字段整理为 SKU、库存、价格三个稳定字段。"""
    payload = product_or_payload.payload if isinstance(product_or_payload, Product) else product_or_payload
    payload = payload if isinstance(payload, dict) else {}
    raw_rows = next(
        (payload.get(key) for key in ("skudetails", "skuDetails", "sku_details", "skus", "sku_list", "sku", "skuList") if payload.get(key)),
        [],
    )
    if not isinstance(raw_rows, list):
        return []

    def first_value(item, keys):
        return next((item.get(key) for key in keys if item.get(key) not in (None, "")), None)

    def price_in_yuan(value):
        if value in (None, ""):
            return None
        try:
            return format((Decimal(str(value)) / Decimal("100")).quantize(Decimal("0.01")), "f")
        except (InvalidOperation, TypeError, ValueError):
            return None

    rows = []
    for index, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, dict):
            rows.append({"sku_id": "", "sku_name": str(raw), "stock": None, "price": None, "price_yuan": None, "raw": raw})
            continue
        sku_name = first_value(raw, ("sku_name", "skuName", "skuname", "name", "title", "spec", "spec_name", "specName"))
        if not sku_name and isinstance(raw.get("values") or raw.get("specs") or raw.get("attrs"), list):
            values = raw.get("values") or raw.get("specs") or raw.get("attrs")
            sku_name = " / ".join(str(item.get("value") or item.get("name") or item.get("text") or "") if isinstance(item, dict) else str(item) for item in values).strip(" / ")
        price = first_value(raw, ("price", "group_price", "groupPrice", "sale_price", "salePrice", "price_value", "amount", "min_group_price"))
        rows.append({
            "sku_id": str(first_value(raw, ("skuid", "sku_id", "skuID", "skuId", "sku_sn", "skuSN", "id")) or ""),
            "sku_name": str(sku_name or f"SKU {index}"),
            "stock": first_value(raw, ("stock", "stock_num", "stockNum", "quantity", "inventory", "inventory_num", "inventoryNum", "available_stock", "availableStock", "stock_quantity")),
            "price": price,
            "price_yuan": price_in_yuan(price),
            "raw": raw,
        })
    return rows


def product_attribute_rows(product_or_payload):
    """将商品入库 JSON 中格式不一的属性统一成可直接展示的名称和值。"""
    payload = product_or_payload.payload if isinstance(product_or_payload, Product) else product_or_payload
    payload = payload if isinstance(payload, dict) else {}
    raw_attributes = next(
        (
            payload.get(key)
            for key in (
                "values", "attributes", "property", "properties",
                "goods_property", "goods_properties", "props",
            )
            if payload.get(key) not in (None, "")
        ),
        [],
    )

    if isinstance(raw_attributes, dict):
        raw_attributes = [{"name": key, "value": value} for key, value in raw_attributes.items()]
    if not isinstance(raw_attributes, (list, tuple)):
        return []

    name_fields = (
        "name", "Name", "attribute_name", "attributeName", "AttributeName",
        "key", "label", "title", "property_name", "propertyName",
    )
    value_fields = (
        "value", "Value", "attribute_value", "attributeValue", "AttributeValue",
        "text", "content", "property_value", "propertyValue",
    )

    def first_value(item, fields):
        return next((item.get(field) for field in fields if item.get(field) not in (None, "")), None)

    rows = []
    for index, raw in enumerate(raw_attributes, start=1):
        if isinstance(raw, dict):
            name = first_value(raw, name_fields)
            value = first_value(raw, value_fields)
            if value is None:
                nested_values = raw.get("values") or raw.get("items")
                if isinstance(nested_values, (list, tuple)):
                    value = " / ".join(str(item) for item in nested_values if item not in (None, ""))
            if name in (None, "") and len(raw) == 1:
                name, value = next(iter(raw.items()))
        else:
            name, value = f"属性 {index}", raw
        if value in (None, ""):
            continue
        rows.append({"name": str(name or f"属性 {index}"), "value": str(value)})
    return rows


def product_material_match_texts(product):
    """返回可用于客户素材自动匹配的商品标题、SKU 与属性文本。"""
    payload = product.payload if isinstance(product.payload, dict) else {}
    texts = []
    for field in ("goods_name", "goodsName", "title", "product_name", "name"):
        value = payload.get(field)
        if value not in (None, ""):
            texts.append(str(value))

    for sku in product_sku_rows(product):
        for field in ("sku_name", "sku_id"):
            value = sku.get(field)
            if value not in (None, ""):
                texts.append(str(value))

    for attribute in product_attribute_rows(product):
        texts.extend((attribute["name"], attribute["value"]))
    return texts


def ai_automatically_matched_materials(product):
    """按素材名称（区分大小写）匹配当前商品，不在数据库中保存匹配结果。"""
    if not product.store.customer_id:
        return []
    product_text = "\n".join(product_material_match_texts(product))
    if not product_text:
        return []
    return [
        material
        for material in CustomerMaterial.objects.filter(customer_id=product.store.customer_id).order_by("name", "pk")
        if material.name and material.name in product_text
    ]


def ai_product_material_match_modes(product, material):
    """Return the ways a material is a source for a product, ignoring its block state."""
    if product.store.customer_id != material.customer_id:
        return []
    modes = []
    if product.material_id == material.pk:
        modes.append("manual")
    product_text = "\n".join(product_material_match_texts(product))
    if material.name and material.name in product_text:
        modes.append("automatic")
    return modes


def ai_product_material_sources(product):
    """返回商品可继承的素材及其继承类型；手动和自动命中素材均继承全部知识类型。"""
    sources = []
    material_ids = set()
    blocked_material_ids = set(
        ProductMaterialInheritanceBlock.objects.filter(product=product).values_list("material_id", flat=True)
    )
    if product.material_id and product.material_id not in blocked_material_ids:
        sources.append((product.material, None))
        material_ids.add(product.material_id)
    for material in ai_automatically_matched_materials(product):
        if material.pk not in material_ids and material.pk not in blocked_material_ids:
            sources.append((material, {"prompt", "qa", "keyword"}))
            material_ids.add(material.pk)
    return sources


def ai_material_inheriting_product_context(request, material):
    """List products that use this material manually or match it automatically.

    A whole-material block does not remove a row here, so it remains possible to
    restore inheritance from the same material page.
    """
    blocked_product_ids = set(
        ProductMaterialInheritanceBlock.objects.filter(material=material).values_list("product_id", flat=True)
    )
    rows = []
    products = Product.objects.filter(store__customer_id=material.customer_id).select_related(
        "store", "store__customer", "material"
    ).order_by("-updated_at")
    mode_labels = {"manual": "手动标注", "automatic": "自动匹配"}
    for product in products:
        modes = ai_product_material_match_modes(product, material)
        if not modes:
            continue
        rows.append({
            "product": product,
            "product_display": product_title(product),
            "product_subtitle": ai_scope_subtitle("product", product),
            "detail_url": reverse("ai_knowledge_detail", args=["product", product.pk]),
            "mode_display": "、".join(mode_labels[mode] for mode in modes),
            "is_blocked": product.pk in blocked_product_ids,
            "can_change_block": can_edit_ai_scope(request.user, "product", product),
        })
    page_obj, page_rows, pagination_query = paginate_center_queryset(rows, request)
    return page_rows, page_obj, pagination_query


def ai_scope_display(scope, obj):
    if scope == "customer":
        return obj.name
    if scope == "store":
        return obj.name
    if scope == "product":
        return product_title(obj)
    return obj.name


def ai_scope_subtitle(scope, obj):
    if scope == "customer":
        return f"客户 ID：{obj.pk}"
    if scope == "store":
        return f"{obj.get_platform_display()} · 店铺号：{obj.external_id} · {obj.customer.name if obj.customer else '未归属客户'}"
    if scope == "product":
        material = obj.material.name if obj.material else "未标注材质"
        return f"{obj.store.get_platform_display()} · 店铺号：{obj.store.external_id} · 商品号：{obj.goods_id} · {material}"
    return f"客户：{obj.customer.name}"


def get_ai_knowledge_list_context(request, scope, *, favorites_only=False):
    if scope not in AI_KNOWLEDGE_SCOPES:
        raise Http404("未知的知识库类型")

    is_client = is_customer_account(request.user)
    only_mine = request.GET.get("only_mine") == "1" or is_client
    keyword = request.GET.get("keyword", "").strip()
    chosen_platform = normalize_platform(request.GET.get("platform"))
    chosen_customer_id = request.GET.get("customer", "").strip()
    chosen_store_id = request.GET.get("store", "").strip()
    can_filter_by_responsible = is_platform_admin(request.user)
    chosen_responsible_id = request.GET.get("responsible", "").strip() if can_filter_by_responsible else ""
    try:
        customer_id = int(chosen_customer_id) if chosen_customer_id else None
    except ValueError:
        chosen_customer_id = ""
        customer_id = None
    try:
        store_id = int(chosen_store_id) if chosen_store_id else None
    except ValueError:
        chosen_store_id = ""
        store_id = None
    try:
        responsible_id = int(chosen_responsible_id) if chosen_responsible_id else None
    except ValueError:
        chosen_responsible_id = ""
        responsible_id = None

    filter_customers = Customer.objects.none()
    filter_stores = Store.objects.none()
    if scope == "customer":
        items = Customer.objects.all().order_by("name")
        if keyword:
            items = items.filter(name__icontains=keyword)
    elif scope == "store":
        items = Store.objects.select_related("customer").order_by("name")
        if chosen_platform:
            items = items.filter(platform=chosen_platform)
        if customer_id:
            items = items.filter(customer_id=customer_id)
        if keyword:
            items = items.filter(Q(name__icontains=keyword) | Q(external_id__icontains=keyword) | Q(customer__name__icontains=keyword))
        filter_customers = Customer.objects.filter(stores__isnull=False)
        if chosen_platform:
            filter_customers = filter_customers.filter(stores__platform=chosen_platform)
        filter_customers = filter_customers.distinct().order_by("name")
    elif scope == "product":
        favorite_for_current_user = ProductFavorite.objects.filter(
            product_id=OuterRef("pk"), user=request.user
        )
        items = Product.objects.select_related("store", "store__customer", "material").annotate(
            ai_is_favorite=Exists(favorite_for_current_user)
        ).order_by("-knowledge_heat", "-updated_at")
        if chosen_platform:
            items = items.filter(store__platform=chosen_platform)
        if customer_id:
            items = items.filter(store__customer_id=customer_id)
        if store_id:
            items = items.filter(store_id=store_id)
        if keyword:
            items = items.filter(Q(goods_id__icontains=keyword) | Q(store__name__icontains=keyword) | Q(store__external_id__icontains=keyword))
        if favorites_only:
            items = items.filter(ai_is_favorite=True)
        filter_customers = Customer.objects.filter(stores__products__isnull=False)
        if chosen_platform:
            filter_customers = filter_customers.filter(stores__platform=chosen_platform)
        filter_customers = filter_customers.distinct().order_by("name")
        filter_stores = Store.objects.filter(products__isnull=False)
        if chosen_platform:
            filter_stores = filter_stores.filter(platform=chosen_platform)
        if customer_id:
            filter_stores = filter_stores.filter(customer_id=customer_id)
        filter_stores = filter_stores.distinct().order_by("name")
    else:
        items = CustomerMaterial.objects.select_related("customer").order_by("customer__name", "name")
        if customer_id:
            items = items.filter(customer_id=customer_id)
        if keyword:
            items = items.filter(Q(name__icontains=keyword) | Q(customer__name__icontains=keyword))
        filter_customers = Customer.objects.filter(materials__isnull=False).distinct().order_by("name")

    if is_client:
        # The list routes are guarded too; keep the data query scoped here so
        # changing query parameters can never broaden the result set.
        items = only_mine_ai_scope(items, scope, request.user)
        filter_customers = filter_customers.filter(pk=request.user.customer_id)
        filter_stores = filter_stores.filter(customer_id=request.user.customer_id)

    if responsible_id:
        responsible_filters = {
            "customer": "stores__shift_claims__user_id",
            "store": "shift_claims__user_id",
            "product": "store__shift_claims__user_id",
            "material": "customer__stores__shift_claims__user_id",
        }
        items = items.filter(**{responsible_filters[scope]: responsible_id}).distinct()

    if only_mine:
        items = only_mine_ai_scope(items, scope, request.user)
    page_obj, items, pagination_query = paginate_center_queryset(items, request)
    for item in items:
        item.ai_display = ai_scope_display(scope, item)
        item.ai_subtitle = ai_scope_subtitle(scope, item)
        item.ai_can_edit = can_edit_ai_scope(request.user, scope, item)
        item.ai_ownership = (
            "客户知识可由该客户任一已认领店铺负责人维护"
            if scope == "customer"
            else item.customer.name if scope == "material"
            else item.store.name if scope == "product"
            else item.customer.name if item.customer_id else "未归属客户"
        )
        if scope == "product":
            item.ai_main_image_urls = product_image_urls(item)["main"][:1]

    material_customers = Customer.objects.none()
    if scope == "material":
        material_customers = Customer.objects.order_by("name")
        if not is_platform_admin(request.user):
            material_customers = only_mine_ai_scope(material_customers, "customer", request.user)
    responsibles = User.objects.none()
    if can_filter_by_responsible:
        responsibles = User.objects.filter(store_claims__isnull=False).distinct().order_by(
            "responsible_name", "username"
        )
    return {
        "scope": scope,
        "scope_label": "收藏的商品" if favorites_only else AI_KNOWLEDGE_SCOPES[scope],
        "favorites_only": favorites_only,
        "items": items,
        "only_mine": only_mine,
        "keyword": keyword,
        "platform_options": Store.Platform.choices,
        "filter_customers": filter_customers,
        "filter_stores": filter_stores,
        "chosen_platform": chosen_platform,
        "chosen_customer_id": chosen_customer_id,
        "chosen_store_id": chosen_store_id,
        "can_filter_by_responsible": can_filter_by_responsible,
        "responsibles": responsibles,
        "chosen_responsible_id": chosen_responsible_id,
        "material_customers": material_customers,
        "can_delete_products": scope == "product" and can_delete_ai_knowledge_product(request.user),
        "can_delete_materials": scope == "material",
        "page_obj": page_obj,
        "pagination_query": pagination_query,
    }


def ai_knowledge_list_row_data(scope, item, user, can_delete_products=False, can_delete_materials=False):
    data = {
        "id": item.pk,
        "display": ai_scope_display(scope, item),
        "subtitle": ai_scope_subtitle(scope, item),
        "can_edit": can_edit_ai_scope(user, scope, item),
        "ownership": (
            "客户知识可由该客户任一已认领店铺负责人维护"
            if scope == "customer"
            else item.customer.name if scope == "material"
            else item.store.name if scope == "product"
            else item.customer.name if item.customer_id else "未归属客户"
        ),
        "detail_url": reverse("ai_knowledge_detail", args=[scope, item.pk]),
    }
    if scope == "product":
        data.update({
            "main_image_url": next(iter(product_image_urls(item)["main"]), ""),
            "knowledge_heat": item.knowledge_heat,
            "is_favorite": bool(getattr(item, "ai_is_favorite", False)),
            "favorite_url": reverse("ai_product_favorite_toggle", args=[item.pk]),
            "can_delete": can_delete_products,
            "delete_url": reverse("ai_product_delete", args=[item.pk]),
        })
    elif scope == "material":
        data.update({
            "can_delete": can_delete_materials and can_edit_ai_scope(user, "material", item),
            "delete_url": reverse("ai_material_delete", args=[item.pk]),
        })
    return data


@login_required
@require_GET
def ai_knowledge_list(request, scope):
    if scope not in AI_KNOWLEDGE_SCOPES:
        raise Http404("未知的知识库类型")
    if is_customer_account(request.user):
        allowed = (
            scope == "store" and request.user.customer.allow_store_knowledge_view
        ) or (
            scope == "product" and request.user.customer.allow_product_knowledge_view
        )
        if not allowed:
            return HttpResponseForbidden("当前客户账号没有查看此知识库的权限。")
    return render(request, "core/ai_knowledge_list.html", get_ai_knowledge_list_context(request, scope))


@login_required
@require_GET
def ai_knowledge_list_api(request, scope):
    if scope not in AI_KNOWLEDGE_SCOPES:
        raise Http404("未知的知识库类型")
    if is_customer_account(request.user):
        allowed = (
            scope == "store" and request.user.customer.allow_store_knowledge_view
        ) or (
            scope == "product" and request.user.customer.allow_product_knowledge_view
        )
        if not allowed:
            return HttpResponseForbidden("当前客户账号没有查看此知识库的权限。")
    context = get_ai_knowledge_list_context(request, scope)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [
                ai_knowledge_list_row_data(
                    scope,
                    item,
                    request.user,
                    context["can_delete_products"],
                    context["can_delete_materials"],
                )
                for item in context["items"]
            ],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


@login_required
@require_GET
def ai_favorite_product_list(request):
    return render(
        request,
        "core/ai_knowledge_list.html",
        get_ai_knowledge_list_context(request, "product", favorites_only=True),
    )


@login_required
@require_GET
def ai_favorite_product_list_api(request):
    context = get_ai_knowledge_list_context(request, "product", favorites_only=True)
    return JsonResponse({
        "ok": True,
        "data": {
            "rows": [
                ai_knowledge_list_row_data(
                    "product",
                    item,
                    request.user,
                    context["can_delete_products"],
                    context["can_delete_materials"],
                )
                for item in context["items"]
            ],
            "pagination": pagination_json_data(context["page_obj"]),
        },
    })


def after_sales_strategy_editable_stores(user):
    """策略只能配置到已登记 Cookie 的店铺；非管理员仅能维护自己负责的店铺。"""
    if is_customer_account(user):
        return Store.objects.none()
    stores = Store.objects.select_related("customer").exclude(cookie="")
    if not is_platform_admin(user):
        stores = stores.filter(shift_claims__user=user).distinct()
    return stores.order_by("customer__name", "name", "external_id")


def can_edit_after_sales_strategy(user, strategy):
    return can_edit_ai_scope(user, "store", strategy.store)


def after_sales_strategy_stage_data(strategy):
    unit = "%" if strategy.compensation_type == StoreAfterSalesStrategy.CompensationType.RATIO else "元"
    values = (
        strategy.first_compensation,
        strategy.second_compensation,
        strategy.third_compensation,
    )
    return [
        {"sequence": index, "value": value, "unit": unit}
        for index, value in enumerate(values[:strategy.compensation_stage_count], start=1)
    ]


def after_sales_strategy_api_data(strategy):
    store = strategy.store
    return {
        "shopid": store.external_id,
        "shop_name": store.name,
        "platform": store.platform,
        "platform_name": store.get_platform_display(),
        "customer": store.customer.name if store.customer else None,
        "negotiation_methods": {
            "compensation": strategy.compensation_count,
            "replacement": strategy.replacement_count,
            "refund": strategy.refund_count,
        },
        "compensation_type": strategy.compensation_type,
        "compensation_type_name": strategy.get_compensation_type_display(),
        "compensation_stage_count": strategy.compensation_stage_count,
        "compensation_stages": after_sales_strategy_stage_data(strategy),
        "compensation_minimum": strategy.compensation_minimum,
        "compensation_maximum": strategy.compensation_maximum,
        "warranty_days": strategy.warranty_days,
        "created_at": strategy.created_at.isoformat(),
        "updated_at": strategy.updated_at.isoformat(),
    }


def get_after_sales_strategy_context(request):
    is_client = is_customer_account(request.user)
    selected_customer_id = request.GET.get("customer", "").strip()
    store_query = request.GET.get("store", "").strip()
    try:
        customer_id = int(selected_customer_id) if selected_customer_id else None
    except ValueError:
        selected_customer_id = ""
        customer_id = None

    strategies = StoreAfterSalesStrategy.objects.select_related("store", "store__customer")
    if is_client:
        strategies = strategies.filter(store__customer_id=request.user.customer_id)
    if customer_id:
        strategies = strategies.filter(store__customer_id=customer_id)
    if store_query:
        strategies = strategies.filter(
            Q(store__name__icontains=store_query) | Q(store__external_id__icontains=store_query)
        )
    page_obj, strategies, pagination_query = paginate_center_queryset(strategies, request)
    for strategy in strategies:
        strategy.stage_data = after_sales_strategy_stage_data(strategy)
        strategy.can_edit = can_edit_after_sales_strategy(request.user, strategy)

    editable_stores = after_sales_strategy_editable_stores(request.user)
    editable_customers = Customer.objects.filter(
        stores__in=editable_stores
    ).distinct().order_by("name")
    filter_customers = Customer.objects.filter(
        stores__after_sales_strategy__isnull=False
    ).distinct().order_by("name")
    if is_client:
        filter_customers = filter_customers.filter(pk=request.user.customer_id)
    return {
        "strategies": strategies,
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "filter_customers": filter_customers,
        "selected_customer_id": selected_customer_id,
        "store_query": store_query,
        "editable_stores": editable_stores,
        "editable_customers": editable_customers,
        "can_manage_after_sales_strategy": not is_client,
        "is_client_account": is_client,
    }


@login_required
@require_http_methods(["GET", "POST"])
def after_sales_strategy_config(request):
    context = get_after_sales_strategy_context(request)
    if request.method == "POST" and is_customer_account(request.user):
        return HttpResponseForbidden("客户账号仅可查看自己店铺的售后策略。")
    editing_id = request.POST.get("editing_id") or request.GET.get("edit")
    editing_strategy = None
    if editing_id:
        editing_strategy = get_object_or_404(
            StoreAfterSalesStrategy.objects.select_related("store", "store__customer"), pk=editing_id
        )
        if not can_edit_after_sales_strategy(request.user, editing_strategy):
            return HttpResponseForbidden("仅店铺负责人或平台管理员可以维护该店铺的售后策略。")

    if request.method == "POST":
        if editing_strategy:
            store = editing_strategy.store
        else:
            store = get_object_or_404(context["editable_stores"], pk=request.POST.get("store_id"))
        form = StoreAfterSalesStrategyForm(request.POST, instance=editing_strategy)
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.store = store
            strategy.save()
            messages.success(request, f"店铺“{store.name}”的售后策略已保存。")
            return redirect("after_sales_strategy_config")
    else:
        form = StoreAfterSalesStrategyForm(instance=editing_strategy)

    context.update({
        "form": form,
        "editing_strategy": editing_strategy,
        "selected_store_id": editing_strategy.store_id if editing_strategy else request.POST.get("store_id", ""),
        "form_customer_id": editing_strategy.store.customer_id if editing_strategy else request.POST.get("customer_id", ""),
    })
    return render(request, "core/after_sales_strategy_config.html", context)


@login_required
@require_POST
def after_sales_strategy_delete(request, pk):
    strategy = get_object_or_404(StoreAfterSalesStrategy.objects.select_related("store"), pk=pk)
    if not can_edit_after_sales_strategy(request.user, strategy):
        return HttpResponseForbidden("仅店铺负责人或平台管理员可以删除该店铺的售后策略。")
    strategy.delete()
    messages.success(request, "售后策略已删除。")
    return redirect("after_sales_strategy_config")


@csrf_exempt
@require_GET
def api_after_sales_strategy(request):
    """按店铺号读取已配置的售后策略，供外部售后系统直接调用。"""
    shop_id = str(request.GET.get("shopid") or request.GET.get("shop_id") or "").strip()
    if not shop_id:
        return json_error("shopid 必填")
    platform = normalize_platform(request.GET.get("platform"))
    if request.GET.get("platform") and not platform:
        return json_error("platform 只能是 pdd、douyin、jingdong 或对应中文平台名")
    strategies = StoreAfterSalesStrategy.objects.select_related("store", "store__customer").filter(
        store__external_id=shop_id
    )
    if platform:
        strategies = strategies.filter(store__platform=platform)
    strategy_count = strategies.count()
    if strategy_count == 0:
        return json_error("未找到该店铺的售后策略", 404)
    if strategy_count > 1:
        return json_error("该 shopid 在多个平台配置了策略，请补传 platform", 409)
    return JsonResponse({"ok": True, "data": after_sales_strategy_api_data(strategies.get())})


@login_required
@require_POST
def ai_product_favorite_toggle(request, pk):
    """切换当前账号对某一商品的收藏状态，供列表页原位更新使用。"""
    product = get_object_or_404(Product, pk=pk)
    if not can_view_ai_scope(request.user, "product", product):
        return HttpResponseForbidden("无权访问该商品知识库。")
    favorite, created = ProductFavorite.objects.get_or_create(user=request.user, product=product)
    if not created:
        favorite.delete()
    return JsonResponse({"ok": True, "favorite": created})


@login_required
@require_POST
def ai_product_delete(request, pk):
    if not can_delete_ai_knowledge_product(request.user):
        return HttpResponseForbidden("仅管理员可以删除商品。")
    product = get_object_or_404(Product.objects.select_related("store"), pk=pk)
    product_name = product_title(product)
    product.delete()
    messages.success(request, f"已删除商品“{product_name}”及其商品知识内容。")
    if request.POST.get("return_to_favorites") == "1":
        return redirect("ai_favorite_product_list")
    return redirect("ai_knowledge_list", scope="product")


@login_required
@require_POST
def ai_material_delete(request, pk):
    material = get_object_or_404(CustomerMaterial.objects.select_related("customer"), pk=pk)
    if not can_edit_ai_scope(request.user, "material", material):
        return HttpResponseForbidden("仅该客户下已认领店铺的负责人或平台管理员可以删除客户素材。")
    product_count = material.products.count()
    material_name = material.name
    material.delete()
    detail = f"，已取消 {product_count} 个商品的手动素材标注" if product_count else ""
    messages.success(request, f"客户素材“{material_name}”已删除{detail}。")
    return redirect("ai_knowledge_list", scope="material")


@login_required
@require_POST
def ai_material_create(request):
    try:
        customer = get_object_or_404(Customer, pk=request.POST.get("customer_id"))
        if not can_edit_ai_scope(request.user, "customer", customer):
            return HttpResponseForbidden("仅该客户下已认领店铺的负责人可以新增材质。")
        name = request.POST.get("name", "").strip()
        if not name:
            raise ValueError("材质名称不能为空")
        CustomerMaterial.objects.get_or_create(customer=customer, name=name, defaults={"created_by": request.user})
        messages.success(request, "客户材质已保存。")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("ai_knowledge_list", scope="material")


def ai_knowledge_entries(scope, obj):
    filters = ai_scope_filter(scope, obj)
    prompts = {scene: "" for scene, _label in KnowledgeScene.choices}
    for item in AIKnowledgePrompt.objects.filter(**filters):
        prompts[item.scene] = item.content
    return (
        prompts,
        AIKnowledgeQA.objects.filter(**filters).order_by("scene", "-updated_at"),
        AIKnowledgeKeyword.objects.filter(**filters).order_by("scene", "match_type", "keyword"),
    )


def ai_block_target_kwargs(scope, obj):
    if scope not in ("store", "product"):
        raise ValueError("只有店铺和商品知识库可以屏蔽继承内容")
    return {scope: obj}


def ai_inherited_sources(scope, obj):
    """返回当前层级会继承到页面/API 的上游知识来源。"""
    if scope == "store":
        return [("customer", obj.customer, None)] if obj.customer_id else []
    if scope == "product":
        sources = []
        if obj.store.customer_id:
            sources.append(("customer", obj.store.customer, None))
        sources.append(("store", obj.store, None))
        for material, entry_types in ai_product_material_sources(obj):
            sources.append(("material", material, entry_types))
        return sources
    return []


def ai_inherited_entry_is_valid(scope, obj, entry, entry_type):
    """确保屏蔽记录只能指向该对象真正会继承到的内容。"""
    if scope == "store":
        return bool(obj.customer_id and entry.customer_id == obj.customer_id)
    if scope == "product":
        if (obj.store.customer_id and entry.customer_id == obj.store.customer_id) or entry.store_id == obj.store_id:
            return True
        for material, entry_types in ai_product_material_sources(obj):
            if entry.material_id == material.pk and (entry_types is None or entry_type in entry_types):
                return True
        return False
    return False


def ai_blocked_entry_ids(entry_type, scope, obj):
    config = AI_KNOWLEDGE_ENTRY_TYPES[entry_type]
    source_field = config["source_field"]
    return set(config["block_model"].objects.filter(**ai_block_target_kwargs(scope, obj)).values_list(f"{source_field}_id", flat=True))


def ai_entry_type_for_model(model):
    for entry_type, config in AI_KNOWLEDGE_ENTRY_TYPES.items():
        if config["model"] is model:
            return entry_type
    raise ValueError("未知的知识类型")


def ai_visible_entries(model, source_scope, source_obj, scenes, block_targets=()):
    """读取启用的知识条目，并按每个下游店铺/商品的屏蔽记录排除。"""
    entry_type = ai_entry_type_for_model(model)
    blocked_ids = set()
    for target_scope, target_obj in block_targets:
        blocked_ids.update(ai_blocked_entry_ids(entry_type, target_scope, target_obj))
    queryset = model.objects.filter(
        **ai_scope_filter(source_scope, source_obj),
        is_active=True,
        scene__in=scenes,
    ).order_by("scene", "created_at")
    return queryset.exclude(pk__in=blocked_ids) if blocked_ids else queryset


def ai_inherited_rows(scope, obj):
    """给页面提供上游提示词、问答对和关键词及各自的屏蔽状态。"""
    if scope not in ("store", "product"):
        return {entry_type: [] for entry_type in AI_KNOWLEDGE_ENTRY_TYPES}

    blocked_ids = {entry_type: ai_blocked_entry_ids(entry_type, scope, obj) for entry_type in AI_KNOWLEDGE_ENTRY_TYPES}
    rows = {entry_type: [] for entry_type in AI_KNOWLEDGE_ENTRY_TYPES}
    for source_scope, source_obj, allowed_entry_types in ai_inherited_sources(scope, obj):
        for entry_type, config in AI_KNOWLEDGE_ENTRY_TYPES.items():
            if allowed_entry_types is not None and entry_type not in allowed_entry_types:
                continue
            for entry in config["model"].objects.filter(**ai_scope_filter(source_scope, source_obj)).order_by("scene", "created_at"):
                blocked_by_store = False
                # 商品层的客户知识若已在店铺层屏蔽，商品无需再重复设置。
                if scope == "product" and source_scope == "customer":
                    blocked_by_store = entry.pk in ai_blocked_entry_ids(entry_type, "store", obj.store)
                rows[entry_type].append({
                    "entry": entry,
                    "entry_type": entry_type,
                    "entry_type_label": config["label"],
                    "source": source_scope,
                    "source_name": ai_source_name(source_scope, source_obj),
                    "is_blocked": entry.pk in blocked_ids[entry_type],
                    "is_blocked_upstream": blocked_by_store,
                    "can_change_block": not blocked_by_store,
                })
    return rows


def set_ai_inheritance_block(scope, obj, entry_type, entry_id, is_blocked, user):
    if scope not in ("store", "product"):
        raise ValueError("只有店铺和商品知识库可以屏蔽继承内容")
    config = AI_KNOWLEDGE_ENTRY_TYPES.get(entry_type)
    if not config:
        raise ValueError("知识类型无效")
    entry = get_object_or_404(config["model"], pk=entry_id)
    if not ai_inherited_entry_is_valid(scope, obj, entry, entry_type):
        raise ValueError("只能屏蔽当前知识库继承到的内容")
    target_kwargs = ai_block_target_kwargs(scope, obj)
    source_field = config["source_field"]
    relation_kwargs = {**target_kwargs, source_field: entry}
    if is_blocked:
        config["block_model"].objects.get_or_create(**relation_kwargs, defaults={"created_by": user})
    else:
        config["block_model"].objects.filter(**relation_kwargs).delete()
    return entry, config["label"]


def set_ai_product_material_inheritance_block(product, material, is_blocked, user):
    if not ai_product_material_match_modes(product, material):
        raise ValueError("该客户素材当前不会继承到此商品，无法设置整项屏蔽。")
    relation = {"product": product, "material": material}
    if is_blocked:
        ProductMaterialInheritanceBlock.objects.get_or_create(**relation, defaults={"created_by": user})
    else:
        ProductMaterialInheritanceBlock.objects.filter(**relation).delete()


@login_required
@require_http_methods(["GET", "POST"])
def ai_knowledge_detail(request, scope, pk):
    if scope not in AI_KNOWLEDGE_SCOPES:
        raise Http404("未知的知识库类型")
    obj = get_ai_scope_object(scope, pk)
    if not can_view_ai_scope(request.user, scope, obj):
        return HttpResponseForbidden("无权访问该知识库内容。")
    can_edit = can_edit_ai_scope(request.user, scope, obj)
    filters = ai_scope_filter(scope, obj)

    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("你只能维护自己负责范围内的知识库。")
        action = request.POST.get("action", "")
        try:
            if action == "save_order_urging_script":
                save_order_urging_script(scope, obj, request.POST, request.user)
                messages.success(request, "催单话术已保存。")
            elif action == "save_prompt":
                scene = normalize_knowledge_scene(request.POST.get("scene"))
                content = request.POST.get("content", "").strip()
                if not scene:
                    raise ValueError("提示词场景无效")
                existing = AIKnowledgePrompt.objects.filter(**filters, scene=scene).first()
                if not content:
                    if existing:
                        existing.delete()
                    messages.success(request, "已清空该场景的特殊提示词。")
                elif existing:
                    existing.content = content
                    existing.is_active = True
                    existing.save(update_fields=["content", "is_active", "updated_at"])
                    messages.success(request, "特殊提示词已更新。")
                else:
                    AIKnowledgePrompt.objects.create(**filters, scene=scene, content=content, created_by=request.user)
                    messages.success(request, "特殊提示词已保存。")
            elif action == "add_qa":
                scene = normalize_knowledge_scene(request.POST.get("scene"))
                question = request.POST.get("question", "").strip()
                answer = request.POST.get("answer", "").strip()
                if not scene or not question or not answer:
                    raise ValueError("问答对的场景、问题和回答均为必填")
                AIKnowledgeQA.objects.create(**filters, scene=scene, question=question, answer=answer, created_by=request.user)
                messages.success(request, "问答对已添加。")
            elif action == "update_qa":
                entry = get_object_or_404(AIKnowledgeQA, pk=request.POST.get("entry_id"), **filters)
                scene = normalize_knowledge_scene(request.POST.get("scene"))
                question = request.POST.get("question", "").strip()
                answer = request.POST.get("answer", "").strip()
                if not scene or not question or not answer:
                    raise ValueError("问答对的场景、问题和回答均为必填")
                entry.scene, entry.question, entry.answer = scene, question, answer
                entry.is_active = request.POST.get("is_active") == "on"
                entry.save(update_fields=["scene", "question", "answer", "is_active", "updated_at"])
                messages.success(request, "问答对已更新。")
            elif action == "delete_qa":
                get_object_or_404(AIKnowledgeQA, pk=request.POST.get("entry_id"), **filters).delete()
                messages.success(request, "问答对已删除。")
            elif action == "add_keyword":
                scene = normalize_knowledge_scene(request.POST.get("scene"))
                keyword = request.POST.get("keyword", "").strip()
                answer = request.POST.get("answer", "").strip()
                match_type = request.POST.get("match_type", AIKnowledgeKeyword.MatchType.CONTAINS)
                if not scene or not keyword or not answer or match_type not in AIKnowledgeKeyword.MatchType.values:
                    raise ValueError("关键词、回答、场景或匹配方式无效")
                AIKnowledgeKeyword.objects.create(**filters, scene=scene, keyword=keyword, answer=answer, match_type=match_type, created_by=request.user)
                messages.success(request, "关键词已添加。")
            elif action == "update_keyword":
                entry = get_object_or_404(AIKnowledgeKeyword, pk=request.POST.get("entry_id"), **filters)
                scene = normalize_knowledge_scene(request.POST.get("scene"))
                keyword = request.POST.get("keyword", "").strip()
                answer = request.POST.get("answer", "").strip()
                match_type = request.POST.get("match_type")
                if not scene or not keyword or not answer or match_type not in AIKnowledgeKeyword.MatchType.values:
                    raise ValueError("关键词、回答、场景或匹配方式无效")
                entry.scene, entry.keyword, entry.answer, entry.match_type = scene, keyword, answer, match_type
                entry.is_active = request.POST.get("is_active") == "on"
                entry.save(update_fields=["scene", "keyword", "answer", "match_type", "is_active", "updated_at"])
                messages.success(request, "关键词已更新。")
            elif action == "delete_keyword":
                get_object_or_404(AIKnowledgeKeyword, pk=request.POST.get("entry_id"), **filters).delete()
                messages.success(request, "关键词已删除。")
            elif action == "set_inheritance_block":
                _entry, entry_label = set_ai_inheritance_block(
                    scope=scope,
                    obj=obj,
                    entry_type=request.POST.get("entry_type", ""),
                    entry_id=request.POST.get("entry_id", ""),
                    is_blocked=request.POST.get("is_blocked") == "on",
                    user=request.user,
                )
                messages.success(request, f"{entry_label}屏蔽规则已保存。")
            elif action == "set_product_material_inheritance_block" and scope == "material":
                product = get_object_or_404(
                    Product.objects.select_related("store", "store__customer", "material"),
                    pk=request.POST.get("product_id"),
                )
                if not can_edit_ai_scope(request.user, "product", product):
                    return HttpResponseForbidden("你只能设置自己负责店铺下商品的素材继承规则。")
                is_blocked = request.POST.get("is_blocked") == "1"
                set_ai_product_material_inheritance_block(product, obj, is_blocked, request.user)
                messages.success(
                    request,
                    f"商品“{product_title(product)}”的客户素材“{obj.name}”"
                    + ("已整项屏蔽。" if is_blocked else "已恢复继承。"),
                )
            elif action == "save_store_blocks" and scope == "store":
                obj.block_customer_prompts = request.POST.get("block_customer_prompts") == "on"
                obj.block_customer_qas = request.POST.get("block_customer_qas") == "on"
                obj.block_customer_keywords = request.POST.get("block_customer_keywords") == "on"
                obj.save(update_fields=["block_customer_prompts", "block_customer_qas", "block_customer_keywords"])
                messages.success(request, "客户知识库屏蔽规则已保存。")
            elif action == "save_product_material" and scope == "product":
                material_id = request.POST.get("material_id", "").strip()
                material = None
                if material_id:
                    material = get_object_or_404(CustomerMaterial, pk=material_id)
                    if not obj.store.customer_id or material.customer_id != obj.store.customer_id:
                        raise ValueError("材质必须属于商品店铺对应的客户")
                obj.material = material
                obj.save(update_fields=["material", "updated_at"])
                messages.success(request, "商品材质标注已保存。")
            else:
                raise ValueError("不支持的操作")
        except (ValueError, ValidationError, IntegrityError) as exc:
            messages.error(request, str(exc))
        return redirect("ai_knowledge_detail", scope=scope, pk=obj.pk)

    prompts, qas, keywords = ai_knowledge_entries(scope, obj)
    material_options = CustomerMaterial.objects.none()
    images = {"main": [], "detail": []}
    sku_details = []
    product_attributes = []
    material_inheriting_products = []
    material_product_page_obj = None
    material_product_pagination_query = ""
    if scope == "product":
        images = product_image_urls(obj)
        sku_details = product_sku_rows(obj)
        product_attributes = product_attribute_rows(obj)
        if obj.store.customer_id:
            material_options = CustomerMaterial.objects.filter(customer_id=obj.store.customer_id).order_by("name")
    elif scope == "material":
        (
            material_inheriting_products,
            material_product_page_obj,
            material_product_pagination_query,
        ) = ai_material_inheriting_product_context(request, obj)
    prompt_rows = [
        {"value": scene, "label": label, "content": prompts.get(scene, "")}
        for scene, label in KnowledgeScene.choices
    ]
    inherited_rows = ai_inherited_rows(scope, obj)
    order_urging = order_urging_context(scope, obj)
    return render(request, "core/ai_knowledge_detail.html", {
        "scope": scope,
        "scope_label": AI_KNOWLEDGE_SCOPES[scope],
        "scope_object": obj,
        "scope_display": ai_scope_display(scope, obj),
        "scope_subtitle": ai_scope_subtitle(scope, obj),
        "can_edit": can_edit,
        "scene_choices": KnowledgeScene.choices,
        "prompt_rows": prompt_rows,
        "qas": qas,
        "keywords": keywords,
        "inherited_prompts": inherited_rows["prompt"],
        "inherited_qas": inherited_rows["qa"],
        "inherited_keywords": inherited_rows["keyword"],
        "order_urging_rows": order_urging["rows"],
        "match_type_choices": AIKnowledgeKeyword.MatchType.choices,
        "material_options": material_options,
        "main_image_urls": images["main"],
        "detail_image_urls": images["detail"],
        "sku_details": sku_details,
        "product_attributes": product_attributes,
        "material_inheriting_products": material_inheriting_products,
        "material_product_page_obj": material_product_page_obj,
        "material_product_pagination_query": material_product_pagination_query,
    })


def api_ai_store_from_payload(data):
    platform = normalize_platform(data.get("platform") or data.get("platform_type") or data.get("type"))
    shop_id = str(data.get("shopid") or data.get("shop_id") or data.get("shopSN") or "").strip()
    if not platform:
        raise ValueError("platform 必填，仅支持 pdd/拼多多/douyin/抖音/jingdong/京东")
    if not shop_id:
        raise ValueError("shopid（店铺号）不能为空")
    store = Store.objects.select_related("customer").filter(platform=platform, external_id=shop_id).first()
    if not store:
        raise LookupError("未找到该平台下的店铺")
    return store


def api_product_value(payload, fields):
    for field in fields:
        value = payload.get(field)
        if value not in (None, ""):
            return value
    return None


def ai_product_api_data(product):
    payload = product.payload if isinstance(product.payload, dict) else {}
    images = product_image_urls(payload)
    return {
        "platform": product.store.platform,
        "platform_name": product.store.get_platform_display(),
        "shopid": product.store.external_id,
        "shop_name": product.store.name,
        "customer": product.store.customer.name if product.store.customer else None,
        "goods_id": product.goods_id,
        "title": api_product_value(payload, ("goods_name", "goodsName", "title", "product_name", "name")),
        "attributes": api_product_value(payload, ("values", "attributes", "property", "properties", "goods_property", "goods_properties", "props")),
        "sku": api_product_value(payload, ("skudetails", "skuDetails", "sku_details", "skus", "sku_list", "sku", "goods_sku", "skuList")),
        "sku_details": product_sku_rows(payload),
        "mainimgurls": images["main"],
        "detailimgurls": images["detail"],
        "material": {"id": product.material_id, "name": product.material.name} if product.material_id else None,
        "data": payload,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@csrf_exempt
@require_POST
def api_ai_product_upsert(request):
    """兼容哈基米平台：接收 zl JSON，并按店铺号 + 商品号覆盖写入。"""
    try:
        data = parse_json(request)
        payload = data.get("zl") if "zl" in data else data
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                raise ValueError("zl 字段如果是字符串，必须是合法 JSON")
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 zl 对象")
        store_data = {**data, **payload}
        store = api_ai_store_from_payload(store_data)
        goods_id = str(payload.get("goods_id") or data.get("goods_id") or "").strip()
        if not goods_id:
            raise ValueError("goods_id（商品号）不能为空")
        cleaned = dict(payload)
        cleaned.pop("username", None)
        cleaned.pop("operator_username", None)
        if "product_intro" in cleaned and "goods_intro" not in cleaned:
            cleaned["goods_intro"] = cleaned.pop("product_intro")
        existing = Product.objects.filter(store=store, goods_id=goods_id).first()
        if existing and "goods_intro" not in cleaned and isinstance(existing.payload, dict):
            cleaned["goods_intro"] = existing.payload.get("goods_intro", "")
        cleaned["shopid"] = store.external_id
        cleaned["goods_id"] = goods_id
        cleaned["active"] = True
        cleaned["updated_at"] = timezone.now().isoformat()
        if "created_at" not in cleaned:
            cleaned["created_at"] = int(timezone.now().timestamp())
        if existing and isinstance(existing.payload, dict) and existing.payload.get("created_store_at"):
            cleaned["created_store_at"] = existing.payload["created_store_at"]
        else:
            cleaned["created_store_at"] = timezone.now().isoformat()
        product, created = Product.objects.update_or_create(
            store=store,
            goods_id=goods_id,
            defaults={"payload": cleaned},
        )
        return JsonResponse({"ok": True, "message": "商品已写入商品库", "created": created, "data": ai_product_api_data(product)})
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_GET
def api_ai_product_get(request):
    try:
        store = api_ai_store_from_payload(request.GET)
        goods_id = str(request.GET.get("goods_id") or "").strip()
        if not goods_id:
            raise ValueError("goods_id（商品号）不能为空")
        product = Product.objects.select_related("store", "store__customer", "material").filter(store=store, goods_id=goods_id).first()
        if not product:
            return json_error("商品不存在", 404)
        return JsonResponse({"ok": True, "data": ai_product_api_data(product)})
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


def api_order_urging_product_from_payload(data):
    product_id = str(data.get("product_id") or "").strip()
    if not product_id:
        raise ValueError("product_id（商品系统 ID）不能为空")
    try:
        product_pk = int(product_id)
    except (TypeError, ValueError):
        raise ValueError("product_id 必须是商品系统 ID")
    product = Product.objects.select_related("store", "store__customer").filter(pk=product_pk).first()
    if not product:
        raise LookupError("未找到对应的商品")
    return product


def api_order_urging_store_from_payload(data):
    """Resolve a store by its external ID for the store-level script endpoint."""
    internal_id = data.get("store_pk") or data.get("internal_store_id")
    if internal_id not in (None, ""):
        try:
            store_pk = int(internal_id)
        except (TypeError, ValueError):
            raise ValueError("store_pk 必须是系统店铺主键")
        store = Store.objects.select_related("customer").filter(pk=store_pk).first()
        if not store:
            raise LookupError("未找到对应的店铺")
        return store

    store_id = str(data.get("store_id") or data.get("shop_id") or data.get("shopid") or "").strip()
    if not store_id:
        raise ValueError("必须提供 store_id（店铺编号）或 store_pk（系统店铺主键）")
    raw_platform = data.get("platform") or data.get("platform_type") or data.get("type")
    platform = normalize_platform(raw_platform)
    if raw_platform not in (None, "") and not platform:
        raise ValueError("platform 不正确")
    stores = Store.objects.select_related("customer").filter(external_id=store_id)
    if platform:
        stores = stores.filter(platform=platform)
    store_count = stores.count()
    if store_count == 0:
        raise LookupError("未找到对应的店铺")
    if store_count > 1:
        raise ValueError("店铺编号跨平台重复，请补充 platform")
    return stores.get()


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_order_urging_script(request):
    """Return the effective pending-payment and unplaced-order scripts for one product."""
    try:
        data = request.GET if request.method == "GET" else parse_json(request)
        product = api_order_urging_product_from_payload(data)
        pending_payment = resolve_order_urging_value("product", product, "pending_payment")["content"] or "无"
        unplaced_order = resolve_order_urging_value("product", product, "unplaced_order")["content"] or "无"
        return JsonResponse({
            "ok": True,
            "data": {
                "product_id": product.pk,
                "pending_payment": pending_payment,
                "unplaced_order": unplaced_order,
            },
        })
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_order_urging_store_script(request):
    """Return the effective pending-payment and unplaced-order scripts for one store."""
    try:
        data = request.GET if request.method == "GET" else parse_json(request)
        store = api_order_urging_store_from_payload(data)
        pending_payment = resolve_order_urging_value("store", store, "pending_payment")["content"] or "无"
        unplaced_order = resolve_order_urging_value("store", store, "unplaced_order")["content"] or "无"
        return JsonResponse({
            "ok": True,
            "data": {
                "store_id": store.external_id,
                "store_pk": store.pk,
                "platform": store.platform,
                "pending_payment": pending_payment,
                "unplaced_order": unplaced_order,
            },
        })
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


def api_ai_product_from_knowledge_payload(data, *, lock=False):
    """用店铺号和商品号定位商品；店铺号跨平台重复时要求补传 platform。"""
    shop_id = str(data.get("shopid") or data.get("shop_id") or data.get("shopSN") or "").strip()
    goods_id = str(data.get("goods_id") or data.get("goodsid") or "").strip()
    if not shop_id:
        raise ValueError("shopid（店铺号）不能为空")
    if not goods_id:
        raise ValueError("goods_id（商品号）不能为空")

    products = Product.objects.select_related("store", "store__customer").filter(
        store__external_id=shop_id,
        goods_id=goods_id,
    )
    raw_platform = data.get("platform") or data.get("platform_type") or data.get("type")
    if raw_platform:
        platform = normalize_platform(raw_platform)
        if not platform:
            raise ValueError("platform 仅支持 pdd/拼多多/douyin/抖音/jingdong/京东")
        products = products.filter(store__platform=platform)
    if lock:
        products = products.select_for_update()

    product_count = products.count()
    if not product_count:
        raise LookupError("未找到对应的商品")
    if product_count > 1:
        raise ValueError("该店铺号和商品号在多个平台重复，请补传 platform")
    return products.get()


def api_product_qa_items(data):
    qas = data.get("qas")
    if qas is None:
        qas = data.get("qa_pairs")
    if not isinstance(qas, list) or not qas:
        raise ValueError("qas 必填，且必须是至少包含一组问答对的数组")

    items = []
    for index, item in enumerate(qas, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 组问答必须是对象")
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            raise ValueError(f"第 {index} 组问答的问题和回答均不能为空")
        items.append((question, answer))
    return items


@csrf_exempt
@require_POST
def api_ai_product_qa_add(request):
    """按指定场景批量新增商品问答。"""
    try:
        data = parse_json(request)
        qa_items = api_product_qa_items(data)
        scene = normalize_knowledge_scene(data.get("scene"))
        if not scene:
            raise ValueError("scene 必填，仅支持 general/通用、presale/售前 或 aftersale/售后")
        with transaction.atomic():
            product = api_ai_product_from_knowledge_payload(data, lock=True)
            entries = [
                AIKnowledgeQA(
                    product=product,
                    scene=scene,
                    question=question,
                    answer=answer,
                )
                for question, answer in qa_items
            ]
            AIKnowledgeQA.objects.bulk_create(entries)
        return JsonResponse({
            "ok": True,
            "message": f"商品{KnowledgeScene(scene).label}问答对已添加",
            "created_count": len(entries),
            "data": {
                "shopid": product.store.external_id,
                "goods_id": product.goods_id,
                "scene": scene,
                "scene_name": KnowledgeScene(scene).label,
                "qas": [ai_qa_api_data(entry, "product") for entry in entries],
            },
        }, status=201)
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_POST
def api_ai_product_prompt_append(request):
    """将一句提示词追加到商品指定场景提示词末尾。"""
    try:
        data = parse_json(request)
        appended_prompt = str(data.get("prompt") or data.get("content") or "").strip()
        if not appended_prompt:
            raise ValueError("prompt（提示词）不能为空")
        scene = normalize_knowledge_scene(data.get("scene"))
        if not scene:
            raise ValueError("scene 必填，仅支持 general/通用、presale/售前 或 aftersale/售后")
        with transaction.atomic():
            product = api_ai_product_from_knowledge_payload(data, lock=True)
            prompt = AIKnowledgePrompt.objects.select_for_update().filter(
                product=product,
                scene=scene,
            ).first()
            if prompt:
                prompt.content = f"{prompt.content}\n{appended_prompt}" if prompt.content else appended_prompt
                prompt.is_active = True
                prompt.save(update_fields=["content", "is_active", "updated_at"])
                created = False
            else:
                prompt = AIKnowledgePrompt.objects.create(
                    product=product,
                    scene=scene,
                    content=appended_prompt,
                )
                created = True
        return JsonResponse({
            "ok": True,
            "message": f"商品{KnowledgeScene(scene).label}提示词已追加",
            "created": created,
            "data": ai_prompt_api_data(prompt, "product"),
        })
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


def ai_active_entries(model, scope, obj, scenes, block_targets=()):
    """兼容旧调用，并在需要时排除下游逐条屏蔽的继承内容。"""
    return ai_visible_entries(model, scope, obj, scenes, block_targets=block_targets)


def ai_source_name(scope, source_obj=None):
    if scope == "material" and source_obj:
        return f"客户素材：{source_obj.name}"
    return {"customer": "客户", "store": "店铺", "product": "商品", "material": "客户素材"}[scope]


def ai_prompt_api_data(entry, scope):
    return {
        "source": scope,
        "source_name": ai_source_name(scope, entry.material if scope == "material" else None),
        "scene": entry.scene,
        "scene_name": entry.get_scene_display(),
        "content": entry.content,
    }


def ai_qa_api_data(entry, scope):
    return {
        "source": scope,
        "source_name": ai_source_name(scope, entry.material if scope == "material" else None),
        "scene": entry.scene,
        "scene_name": entry.get_scene_display(),
        "question": entry.question,
        "answer": entry.answer,
    }


def ai_keyword_api_data(entry, scope):
    return {
        "source": scope,
        "source_name": ai_source_name(scope, entry.material if scope == "material" else None),
        "scene": entry.scene,
        "scene_name": entry.get_scene_display(),
        "keyword": entry.keyword,
        "answer": entry.answer,
        "match_type": entry.match_type,
        "match_type_name": entry.get_match_type_display(),
    }


def ai_product_keyword_entries(product, scenes):
    """返回商品当前可用的全部关键词及来源，统一执行上游与商品级屏蔽规则。"""
    entries = []
    store = product.store
    customer = store.customer
    if customer and not store.block_customer_keywords:
        entries.extend(
            (entry, "customer")
            for entry in ai_active_entries(
                AIKnowledgeKeyword, "customer", customer, scenes,
                block_targets=(("store", store), ("product", product)),
            )
        )
    entries.extend(
        (entry, "store")
        for entry in ai_active_entries(
            AIKnowledgeKeyword, "store", store, scenes, block_targets=(("product", product),)
        )
    )
    for material, entry_types in ai_product_material_sources(product):
        if entry_types is None or "keyword" in entry_types:
            entries.extend(
                (entry, "material")
                for entry in ai_active_entries(
                    AIKnowledgeKeyword, "material", material, scenes, block_targets=(("product", product),)
                )
            )
    entries.extend(
        (entry, "product")
        for entry in ai_active_entries(AIKnowledgeKeyword, "product", product, scenes)
    )
    return entries


def api_ai_product_for_keyword_match(data):
    """匹配接口优先用商品业务 ID 定位，也兼容系统主键 product_pk。"""
    queryset = Product.objects.select_related("store", "store__customer", "material", "material__customer")
    product_pk = str(data.get("product_pk") or "").strip()
    if product_pk:
        try:
            product = queryset.filter(pk=int(product_pk)).first()
        except (TypeError, ValueError):
            raise ValueError("product_pk 必须是商品系统 ID")
        if not product:
            raise LookupError("未找到对应的商品")
        return product

    goods_id = str(data.get("goods_id") or data.get("goodsid") or data.get("product_id") or "").strip()
    if not goods_id:
        raise ValueError("product_id（商品 ID）或 product_pk（商品系统 ID）不能为空")
    products = queryset.filter(goods_id=goods_id)
    shop_id = str(data.get("shopid") or data.get("shop_id") or data.get("shopSN") or "").strip()
    if shop_id:
        products = products.filter(store__external_id=shop_id)
    raw_platform = data.get("platform") or data.get("platform_type") or data.get("type")
    if raw_platform:
        platform = normalize_platform(raw_platform)
        if not platform:
            raise ValueError("platform 仅支持 pdd/拼多多/douyin/抖音/jingdong/京东")
        products = products.filter(store__platform=platform)
    count = products.count()
    if count == 1:
        return products.get()
    if count > 1:
        raise ValueError("同一商品 ID 存在多条记录，请补传 shopid；店铺号跨平台重复时还需补传 platform")

    # 只有 product_id 且商品业务 ID 未命中时，兼容调用方传入系统主键的情况。
    if str(data.get("product_id") or "").strip().isdigit():
        product = queryset.filter(pk=int(data["product_id"])).first()
        if product:
            return product
    raise LookupError("未找到对应的商品")


def ai_keyword_matches_text(entry, text):
    if not entry.keyword:
        return False
    if entry.match_type == AIKnowledgeKeyword.MatchType.EXACT:
        return text == entry.keyword
    return entry.keyword in text


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_ai_knowledge_keyword_match(request):
    """用一段文本匹配指定商品当前有效的关键词，并返回对应回答。"""
    try:
        data = request.GET if request.method == "GET" else parse_json(request)
        text = str(data.get("text") or data.get("content") or data.get("message") or "")
        if not text.strip():
            raise ValueError("text（待匹配文字）不能为空")
        product = api_ai_product_for_keyword_match(data)
        raw_scene = data.get("scene")
        if raw_scene in (None, ""):
            scenes = list(KnowledgeScene.values)
        else:
            scene = normalize_knowledge_scene(raw_scene)
            if not scene:
                raise ValueError("scene 仅支持 general/通用、presale/售前 或 aftersale/售后")
            scenes = [KnowledgeScene.GENERAL] if scene == KnowledgeScene.GENERAL else [KnowledgeScene.GENERAL, scene]

        matches = [
            ai_keyword_api_data(entry, scope)
            for entry, scope in ai_product_keyword_entries(product, scenes)
            if ai_keyword_matches_text(entry, text)
        ]
        answers = list(dict.fromkeys(item["answer"] for item in matches if item["answer"]))
        Product.objects.filter(pk=product.pk).update(knowledge_heat=F("knowledge_heat") + 1)
        return JsonResponse({
            "ok": True,
            "matched": bool(matches),
            "answer": "\n".join(answers) if answers else "无匹配",
            "message": "匹配成功" if matches else "无匹配",
            "data": {
                "product_id": product.pk,
                "goods_id": product.goods_id,
                "text": text,
                "matches": matches,
                "answers": answers,
            },
        })
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_ai_knowledge_resolve(request):
    """按平台、店铺、商品和售前/售后汇总知识，不执行任何 AI 或文本匹配。"""
    try:
        data = request.GET if request.method == "GET" else parse_json(request)
        store = api_ai_store_from_payload(data)
        goods_id = str(data.get("goods_id") or "").strip()
        scene = normalize_knowledge_scene(data.get("scene"))
        if not goods_id:
            raise ValueError("goods_id（商品号）不能为空")
        if scene not in (KnowledgeScene.PRESALE, KnowledgeScene.AFTERSALE):
            raise ValueError("scene 必填，仅支持 presale/售前 或 aftersale/售后")
        product = Product.objects.select_related("store", "store__customer", "material", "material__customer").filter(store=store, goods_id=goods_id).first()
        if not product:
            return json_error("商品不存在", 404)

        scenes = [KnowledgeScene.GENERAL, scene]
        prompts, qas, keywords = [], [], []

        # 继承的客户知识先经过店铺、再经过商品的逐条屏蔽；手动与自动命中的素材均支持商品逐条屏蔽。
        customer = store.customer
        if customer:
            if not store.block_customer_prompts:
                prompts.extend(ai_prompt_api_data(item, "customer") for item in ai_active_entries(
                    AIKnowledgePrompt, "customer", customer, scenes, block_targets=(("store", store), ("product", product))
                ))
            if not store.block_customer_qas:
                qas.extend(ai_qa_api_data(item, "customer") for item in ai_active_entries(
                    AIKnowledgeQA, "customer", customer, scenes, block_targets=(("store", store), ("product", product))
                ))
            if not store.block_customer_keywords:
                keywords.extend(ai_keyword_api_data(item, "customer") for item in ai_active_entries(
                    AIKnowledgeKeyword, "customer", customer, scenes, block_targets=(("store", store), ("product", product))
                ))

        prompts.extend(ai_prompt_api_data(item, "store") for item in ai_active_entries(
            AIKnowledgePrompt, "store", store, scenes, block_targets=(("product", product),)
        ))
        qas.extend(ai_qa_api_data(item, "store") for item in ai_active_entries(
            AIKnowledgeQA, "store", store, scenes, block_targets=(("product", product),)
        ))
        keywords.extend(ai_keyword_api_data(item, "store") for item in ai_active_entries(
            AIKnowledgeKeyword, "store", store, scenes, block_targets=(("product", product),)
        ))

        # 手动标注和名称自动命中的客户素材，都统一经过整项屏蔽和逐条屏蔽规则。
        for material, entry_types in ai_product_material_sources(product):
            if entry_types is None or "prompt" in entry_types:
                prompts.extend(ai_prompt_api_data(item, "material") for item in ai_active_entries(
                    AIKnowledgePrompt, "material", material, scenes, block_targets=(("product", product),)
                ))
            if entry_types is None or "qa" in entry_types:
                qas.extend(ai_qa_api_data(item, "material") for item in ai_active_entries(
                    AIKnowledgeQA, "material", material, scenes, block_targets=(("product", product),)
                ))
            if entry_types is None or "keyword" in entry_types:
                keywords.extend(ai_keyword_api_data(item, "material") for item in ai_active_entries(
                    AIKnowledgeKeyword, "material", material, scenes, block_targets=(("product", product),)
                ))

        prompts.extend(ai_prompt_api_data(item, "product") for item in ai_active_entries(AIKnowledgePrompt, "product", product, scenes))
        qas.extend(ai_qa_api_data(item, "product") for item in ai_active_entries(AIKnowledgeQA, "product", product, scenes))
        keywords.extend(ai_keyword_api_data(item, "product") for item in ai_active_entries(AIKnowledgeKeyword, "product", product, scenes))

        Product.objects.filter(pk=product.pk).update(knowledge_heat=F("knowledge_heat") + 1)
        return JsonResponse({
            "ok": True,
            "data": {
                "scene": scene,
                "scene_name": KnowledgeScene(scene).label,
                "shop": {
                    "platform": store.platform,
                    "platform_name": store.get_platform_display(),
                    "shopid": store.external_id,
                    "shop_name": store.name,
                    "customer": customer.name if customer else None,
                    "customer_knowledge_blocks": {
                        "prompts": sorted(ai_blocked_entry_ids("prompt", "store", store)),
                        "qas": sorted(ai_blocked_entry_ids("qa", "store", store)),
                        "keywords": sorted(ai_blocked_entry_ids("keyword", "store", store)),
                    },
                },
                "product": ai_product_api_data(product),
                "knowledge": {
                    "special_prompts": prompts,
                    "qas": qas,
                    "keywords": keywords,
                },
            },
        })
    except LookupError as exc:
        return json_error(str(exc), 404)
    except ValueError as exc:
        return json_error(str(exc))

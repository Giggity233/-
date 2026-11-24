from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    if sender.name != "core":
        return
    # 组仅提供预置角色；超级管理员仍拥有完整权限。
    roles = {
        "客户与页面管理员": ["can_manage_clients", "change_customer", "view_customer"],
        "Cookie 超级管理员": ["can_delete_cookie", "view_store"],
        "数据管理员": ["can_view_all_store_data", "view_storemetric"],
        "权限管理员": ["can_manage_permissions", "view_user", "change_user"],
        "全局账号管理员": ["can_manage_all_accounts", "view_storeaccount", "change_storeaccount"],
        "客服绩效查看员": ["can_view_customer_performance"],
        "客服月度回复查看员": ["can_view_own_monthly_replies"],
        "商品删除管理员": ["can_delete_product_from_knowledge"],
    }
    for group_name, codenames in roles.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = Permission.objects.filter(content_type__app_label="core", codename__in=codenames)
        group.permissions.set(permissions)
    # 每个普通账号默认拥有查看自己月度回复的最小权限；绩效权限可额外查看全员数据。
    own_reply_group = Group.objects.get(name="客服月度回复查看员")
    user_model = sender.get_model("User")
    own_reply_group.user_set.add(*user_model.objects.filter(is_superuser=False))

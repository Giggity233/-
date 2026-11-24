from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AccountPasswordRegistration, Customer, ImageTextRegistration, PendingTask, RemoteRegistration, ShiftDailySummary, Store, StoreAccount, StoreAfterSalesStrategy, StoreMetric, StoreMetricSnapshot, StoreShiftClaim, User, WeChatPendingGroup


@admin.register(User)
class LianzunUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("蘑菇头信息", {"fields": ("responsible_name",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("蘑菇头信息", {"fields": ("responsible_name",)}),)
    list_display = ("username", "responsible_name", "is_staff", "is_active")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id", "platform", "customer", "cookie_status", "responsible")
    list_filter = ("platform", "cookie_status")
    search_fields = ("name", "external_id")


admin.site.register(StoreShiftClaim)
admin.site.register(StoreMetric)
admin.site.register(StoreMetricSnapshot)
admin.site.register(ShiftDailySummary)
admin.site.register(StoreAccount)


@admin.register(AccountPasswordRegistration)
class AccountPasswordRegistrationAdmin(admin.ModelAdmin):
    list_display = ("shop_name", "platform", "account_name", "account_type", "login_account", "responsible_1", "responsible_2", "customer", "operator_name", "created_at")
    search_fields = ("shop_name", "platform", "account_name", "login_account", "responsible_1", "responsible_2", "customer", "operator_name")
    list_filter = ("platform", "account_type", "created_at")


@admin.register(ImageTextRegistration)
class ImageTextRegistrationAdmin(admin.ModelAdmin):
    list_display = ("image_url", "content", "created_at", "updated_at")
    search_fields = ("image_url", "content")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RemoteRegistration)
class RemoteRegistrationAdmin(admin.ModelAdmin):
    list_display = ("machine_no", "remote_code", "remote_password", "operator_name", "created_at")
    search_fields = ("machine_no", "remote_code", "operator_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WeChatPendingGroup)
class WeChatPendingGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "updated_at")
    search_fields = ("name", "key", "content")
    readonly_fields = ("created_at", "updated_at")


@admin.register(StoreAfterSalesStrategy)
class StoreAfterSalesStrategyAdmin(admin.ModelAdmin):
    list_display = ("store", "compensation_type", "compensation_count", "replacement_count", "refund_count", "updated_at")
    list_filter = ("compensation_type",)
    search_fields = ("store__name", "store__external_id", "store__customer__name")
    list_select_related = ("store", "store__customer")


@admin.register(PendingTask)
class PendingTaskAdmin(admin.ModelAdmin):
    list_display = ("store", "handling_item", "time_type", "is_processed", "created_at", "processed_at", "processed_by")
    list_filter = ("time_type", "is_processed")
    search_fields = ("store__name", "store__external_id", "handling_item")
    list_select_related = ("store", "processed_by")

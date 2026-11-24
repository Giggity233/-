from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from .models import AccountPasswordRegistration, Customer, ImageTextRegistration, RemoteRegistration, StoreAccount, StoreAfterSalesStrategy, User


class RegisterForm(UserCreationForm):
    responsible_name = forms.CharField(label="负责人姓名", max_length=50)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "responsible_name", "password1", "password2")
        labels = {"username": "账号"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            self.fields[field_name].widget = forms.TextInput(attrs={"autocomplete": "new-password"})


class VisiblePasswordChangeForm(PasswordChangeForm):
    """按业务要求，修改系统密码时也以明文输入框展示。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("old_password", "new_password1", "new_password2"):
            self.fields[field_name].widget = forms.TextInput(attrs={"autocomplete": "new-password"})


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "is_active")
        widgets = {"name": forms.TextInput(attrs={"placeholder": "请输入客户名称"})}


class StoreAccountForm(forms.ModelForm):
    class Meta:
        model = StoreAccount
        fields = (
            "store", "name", "login_account", "login_password", "corresponding_port",
            "phone", "account_type", "external_id",
        )
        widgets = {
            "login_password": forms.TextInput(),
            "corresponding_port": forms.TextInput(attrs={"placeholder": "专员填写，选填"}),
            "phone": forms.TextInput(attrs={"placeholder": "选填"}),
            "external_id": forms.TextInput(attrs={"placeholder": "可自动抓取，也可手动修改"}),
        }

    def __init__(self, *args, stores=None, **kwargs):
        super().__init__(*args, **kwargs)
        if stores is not None:
            self.fields["store"].queryset = stores


class AccountPasswordRegistrationForm(forms.ModelForm):
    class Meta:
        model = AccountPasswordRegistration
        fields = (
            "shop_name", "platform", "account_name", "account_type", "login_account",
            "login_password", "phone", "responsible_1", "responsible_2", "customer", "remarks",
        )
        widgets = {
            "shop_name": forms.TextInput(attrs={"placeholder": "选填"}),
            "platform": forms.TextInput(attrs={"placeholder": "默认：拼多多"}),
            "account_name": forms.TextInput(attrs={"placeholder": "选填"}),
            "login_account": forms.TextInput(attrs={"placeholder": "选填"}),
            "login_password": forms.TextInput(attrs={"placeholder": "选填"}),
            "phone": forms.TextInput(attrs={"placeholder": "选填"}),
            "responsible_1": forms.TextInput(attrs={"placeholder": "输入或点选负责人"}),
            "responsible_2": forms.TextInput(attrs={"placeholder": "输入或点选负责人"}),
            "customer": forms.TextInput(attrs={"placeholder": "输入或点选客户"}),
            "remarks": forms.Textarea(attrs={"placeholder": "选填", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsible_1"].widget.attrs["list"] = "registration-responsible-options"
        self.fields["responsible_2"].widget.attrs["list"] = "registration-responsible-options"
        self.fields["customer"].widget.attrs["list"] = "registration-customer-options"
        self.fields["platform"].widget.attrs["list"] = "registration-platform-options"


class ImageTextRegistrationForm(forms.ModelForm):
    class Meta:
        model = ImageTextRegistration
        fields = ("content",)
        widgets = {
            "content": forms.Textarea(attrs={"rows": 10, "placeholder": "请输入对应文字"}),
        }


class RemoteRegistrationForm(forms.ModelForm):
    class Meta:
        model = RemoteRegistration
        fields = ("machine_no", "remote_code", "remote_password")
        widgets = {
            "machine_no": forms.TextInput(attrs={"placeholder": "请输入机器号"}),
            "remote_code": forms.TextInput(attrs={"placeholder": "请输入远程码"}),
            "remote_password": forms.TextInput(attrs={"placeholder": "请输入远程密码"}),
        }


class StoreAfterSalesStrategyForm(forms.ModelForm):
    class Meta:
        model = StoreAfterSalesStrategy
        fields = (
            "compensation_type", "compensation_count", "replacement_count", "refund_count",
            "compensation_stage_count", "compensation_minimum", "compensation_maximum",
            "warranty_days", "first_compensation", "second_compensation", "third_compensation",
        )
        widgets = {
            "compensation_count": forms.Select(choices=[(value, str(value)) for value in range(0, 6)]),
            "replacement_count": forms.Select(choices=[(value, str(value)) for value in range(0, 6)]),
            "refund_count": forms.Select(choices=[(value, str(value)) for value in range(0, 6)]),
            "compensation_minimum": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "compensation_maximum": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "warranty_days": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "first_compensation": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "second_compensation": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "third_compensation": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
        }

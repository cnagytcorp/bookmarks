from django.contrib import admin
from django.contrib.auth.models import User


# Register your models here.
class UserAdmin(admin.ModelAdmin):
    # get membership status
    def membership_status(self, user):
        groups = []
        for group in user.groups.all():
            groups.append(group.name)
        return "Premium" if "Premium" in groups else "Standard"

    list_display = (
        'username', 'email', 'date_joined', 'membership_status'
    )

    list_filter = ['groups', 'is_staff', 'is_superuser', 'is_active']


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

# Register your models here.

admin.site.register(CustomUser, UserAdmin)



"""
- 'UserAdmin' provides a specific(extra) management UI for managing user models in the admin panel.
- so If you register CustomUser with UserAdmin, you get Django's specific/extra user management features like filtering users, searching users, ...
- and those extra features are not provided for the other models, they only get the basics admin management features like creating, editing, ...
- UserAdmin is a class and it is already built in in django 
"""

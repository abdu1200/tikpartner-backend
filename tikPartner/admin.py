from django.contrib import admin
from .models import  Category, Language, InfluencerProfile, BrandProfile

# Register your models here.

admin.site.register(Category)
admin.site.register(Language)
admin.site.register(BrandProfile)



# class InfluencerProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'tiktok_username', 'category', 'follower_count', 'verified_status')  # Fields to show in list view
#     search_fields = ('tiktok_username', 'user__username')  # Enable searching by username and tiktok username
#     list_filter = ('category', 'verified_status')  # Enable filtering


# admin.site.register(InfluencerProfile, InfluencerProfileAdmin)   # Register the model with InfluencerProfileAdmin















"""
- InfluencerProfileAdmin is used to add extra management UI or features(like searching, filtering, ..) in the admin panel for InfluencerProfile model
- 'admin.ModelAdmin' helps us to create an extra management UI for models in the admin panel
- so now 'InfluencerProfileAdmin' provides extra management UI for managing 'InfluencerProfile' model in the admin panel
"""


#To access different models in the Django admin panel, you need to register them in admin.py of your app.
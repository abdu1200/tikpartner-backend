from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, LanguageViewSet, ConversationViewSet
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'conversations', ConversationViewSet, basename='conversation')


# Schema generation for Swagger Docs
schema_view = get_schema_view(
    openapi.Info(
        title="Your API",
        default_version='v1',
        description="Detailed API documentation",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="youremail@example.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
)


urlpatterns = [
    path('', include(router.urls)),
    path('docs/', schema_view.as_view(), name='api_docs'),
]




























# include(router.urls) is used for including the automatically generated URL patterns for the registered viewsets.
# so router.urls are the automatically generated URL patterns(by drf)


#this would have been the code with out drf default router, we would be manually defining the urlpatterns)


"""
If you're using a viewset from drf to build views, then u need to use drf's routers to define url's or routes
"""



"""
For class-based views (when using drf's APIView for building views)

urlpatterns = [
    path('influencers/', InfluencerList.as_view(), name='influencer-list'),               # For listing influencers
    path('influencers/<int:pk>/', InfluencerDetail.as_view(), name='influencer-detail'),  # For a specific influencer
]

"""


"""
For function-based views (when using drf's api_view decorator for building views)

urlpatterns = [
    path('influencers/', influencer_list, name='influencer-list'),                   # For listing influencers
    path('influencers/<int:pk>/', influencer_detail, name='influencer-detail'),      # For a specific influencer
]

"""
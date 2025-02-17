from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, LanguageViewSet, InfluencerUserViewSet, BrandUserViewSet
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'influencers', InfluencerUserViewSet, basename='influencer')
router.register(r'brands', BrandUserViewSet, basename='brand')


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
# urlpatterns = [
#     path('influencers/', influencer_list, name='influencer-list'),
#     path('influencers/<int:pk>/', influencer_detail, name='influencer-detail'),
#     path('brands/', brand_list, name='brand-list'),
#     path('brands/<int:pk>/', brand_detail, name='brand-detail'),
# ]
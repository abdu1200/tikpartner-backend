from django.urls import path, include
#from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import DefaultRouter, NestedDefaultRouter
from .views import CategoryViewSet, LanguageViewSet, ConversationViewSet, MessageViewSet, ContractViewSet, RequestedOffersViewSet, AcceptedOffersViewSet, ActiveContractsViewSet, ApproveWorksViewSet, DeliverableViewSet, PaymentViewSet, InfluencerStripeOnboardingView, ReviewViewSet, TikTokAuthView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'requested_offers', RequestedOffersViewSet, basename='requested_offer')
router.register(r'accepted_offers', AcceptedOffersViewSet, basename='accepted_offer')
router.register(r'active_contracts', ActiveContractsViewSet, basename='active_contract')
router.register(r'approve_works', ApproveWorksViewSet, basename='approve_work')
router.register(r'deliverables', DeliverableViewSet, basename='deliverable')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'reviews', ReviewViewSet, basename='review')


# GET /conversations/1/messages/   GET /conversations/1/messages/5/    DELETE /conversations/1/messages/5/  
conversation_router = NestedDefaultRouter(router, r'conversations', lookup='conversation')
conversation_router.register(r'messages', MessageViewSet, basename='conversation-messages')



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
    path('', include(conversation_router.urls)),
    path('docs/', schema_view.as_view(), name='api-docs'),
    path('auth/tiktok/', TikTokAuthView.as_view(), name='tiktok-auth'),
    path('influencers/stripe-onboarding/', InfluencerStripeOnboardingView.as_view(), name='stripe-onboarding'),
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
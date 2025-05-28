from django.shortcuts import render
from django.db.models import Count, Case, When, IntegerField
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser, BasePermission
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.views import APIView
from .models import Category, Language, InfluencerProfile, InfluencerPortfolio, BrandProfile, Conversation, Message, MessageNotification, Contract, Deliverable, DeliverableAttachment, Payment, Review, Dispute
from .serializers import CategorySerializer, LanguageSerializer, BrandProfileSerializer, InfluencerProfileSerializer, InfluencerPortfolioSerializer, CreateInfluencerPortfolioSerializer, ConversationSerializer, MessageSerializer, ContractSerializer, ContractDetailSerializer, ContractCreateSerializer, ContractOfferSerializer, DeliverableSerializer, DeliverableDetailSerializer, SubmitDeliverableSerializer, PaymentSerializer, PaymentDetailSerializer, ReviewSerializer, DisputeSerializer
from .services.escrow_service import EscrowService
from .services.stripe_escrow_service import StripeEscrowService
import stripe
import requests
from urllib.parse import urlencode
from django.core.mail import send_mail
from datetime import datetime, timedelta
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY

# Create your views here.


class CategoryViewSet(ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    #permission_classes = [IsAuthenticated]



class LanguageViewSet(ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    #permission_classes = [IsAuthenticated]



class InfluencerUserViewSet(ModelViewSet):
    #queryset = InfluencerProfile.objects.all()
    serializer_class = InfluencerProfileSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete'] 

    def get_queryset(self):
        # Order influencers: Pro first, Basic second, non-subscribers last
        return InfluencerProfile.objects.annotate(
            subscription_priority=Case(
                When(subscription_plan='pro', then=1),
                When(subscription_plan='basic', then=2),
                default=3,
                output_field=IntegerField(),
            )
        ).order_by('subscription_priority', '-follower_count')

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action == 'me':
            return [IsAuthenticated()]
        elif self.action in ['list', 'update', 'partial_update', 'destroy']:
            return [AllowAny()]
        return [AllowAny()]    #this block you to see influencer details(specific resource) like 'api/influencers/1/'

    def destroy(self, request, *args, **kwargs):
        try:  #this is to delete the user when deleting its associated influencer profile right away
            instance = self.get_object()
            user = instance.user  # capture user BEFORE deleting the instance(influencer profile)   
            instance.delete()     # delete the InfluencerProfile
            user.delete()         # delete the associated User
            return Response(status=204)
        except Exception as e:
            return Response({"error": str(e)}, status=400)


    @action(detail=False, methods=['GET', 'PUT'], permission_classes=[IsAuthenticated])
    def me(self, request):
        try:
            profile = InfluencerProfile.objects.get(user=request.user)
            if request.method == 'GET':
                serializer = self.get_serializer(profile) #to serializer model instance to json format
                return Response(serializer.data)   #serializer.data is a dictionary #but Response(serializer.data) returns a json to a client
            elif request.method == 'PUT':
                serializer = self.get_serializer(profile, data=request.data, partial=True) #to deserialize api request data from json to object instance #and making the profile instance ready for update
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)
        except InfluencerProfile.DoesNotExist:
            return Response({"error": "Influencer profile not found"}, status=404)



class InfluencerPortfolioViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Add this for file uploads
    
    def get_queryset(self):
         # Check for query parameters
        influencer_id = self.request.query_params.get('influencer_id')

        if influencer_id:    # api/influencer-portfolio/?influencer=influencer
            return InfluencerPortfolio.objects.filter(influencer_id=influencer_id)

        return InfluencerPortfolio.objects.filter(influencer=self.request.user.influencer_profile)
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateInfluencerPortfolioSerializer
        return InfluencerPortfolioSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={'influencer': request.user.influencer_profile}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Portfolio submitted successfully',
            'portfolio_id': serializer.instance.id if hasattr(serializer, 'instance') and serializer.instance else None
        }, status=status.HTTP_201_CREATED)




class BrandUserViewSet(ModelViewSet):
    queryset = BrandProfile.objects.all()
    serializer_class = BrandProfileSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action == 'me':
            return [IsAuthenticated()]
        elif self.action in ['list', 'update', 'partial_update', 'destroy']:
            return [AllowAny()]
        return [AllowAny()]

    def destroy(self, request, *args, **kwargs):
        try:   #this is to delete the user when deleting its associated brand profile right away
            instance = self.get_object()
            user = instance.user  # capture user BEFORE deleting the instance(brand profile)
            instance.delete()     # delete the InfluencerProfile
            user.delete()         # delete the associated User
            return Response(status=204)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

    @action(detail=False, methods=['GET', 'PUT'], permission_classes=[IsAuthenticated])
    def me(self, request):
        try:
            profile = BrandProfile.objects.get(user=request.user)
            if request.method == 'GET':
                serializer = self.get_serializer(profile)
                return Response(serializer.data)
            elif request.method == 'PUT':
                serializer = self.get_serializer(profile, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data)
        except BrandProfile.DoesNotExist:
            return Response({"error": "Brand profile not found"}, status=404)



# Handle Stripe Connect onboarding for influencers
class InfluencerStripeOnboardingView(APIView):

    # 'onboarding link' is the one that is sent to the client(influencer) to connect their bank accounts to the new created Stripe account(for them) via Stripe Connect Express.
    def post(self, request):     # this is for creating or refreshing an onboarding link(so this returns a new or a refersh onboarding link)
        
        user = request.user
        
        if not hasattr(user, 'influencer_profile'):
            return Response({"error": "Only influencers can access this endpoint"}, 
                           status=status.HTTP_403_FORBIDDEN)
                           
        influencer = user.influencer_profile
        
        
        # the step is first you create a Stripe account for an influencer and for that account, you generate an onboarding link and then send it to the client(influencer). the link is for them to connect their bank accounts to the already created stripe account
        
        if influencer.stripe_account_id:    # If influencer already has a Stripe account ID(w/h means already has a Stripe account ), we can refresh the onboarding(by sending them a new onboarding link)
            
            try:
                account_link = stripe.AccountLink.create(    # here we are generating a new onboarding link(refresh link) for an influencer who already has a Stripe account, incase the previous onboarding(connecting bank accounts with the created Stripe account) was not completed successfully.
                    account=influencer.stripe_account_id,
                    refresh_url=f"{settings.FRONTEND_URL}/onboarding/stripe/refresh",
                    return_url=f"{settings.FRONTEND_URL}/StripeSuccessPage",
                    type="account_onboarding",
                )
                return Response({"url": account_link.url})   # here we are sending the generated onboarding link(refresh link this time) to the client(influencer)
            except stripe.error.StripeError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # the onboarding link takes/redirects the client(influencer) to Stripe's hosted onboarding interface to enter/put their bank accounts or credit card info and then connect with the Stripe account that is created for them.


        # if not, Create a new Stripe Connect account(Stripe account) for the influencer
        try:
            account = stripe.Account.create(
                type="express",  # Use 'express' for a streamlined onboarding, or 'standard' for full features
                email=user.email,
                metadata={
                    "user_id": user.id,
                    "influencer_id": influencer.id
                },
                capabilities={
                    "transfers": {"requested": True},
                },
            )
            
            # Save the stripe account ID to the influencer profile(in the db)
            influencer.stripe_account_id = account.id
            influencer.save()
            
            # Create an account link for the onboarding flow for the newly created Stripe account
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{settings.FRONTEND_URL}/onboarding/stripe/refresh",
                return_url=f"https://tikfrontend-latest.onrender.com/StripeSuccessPage",   # The return_url is where Stripe sends the user after they finish the onboarding process. # It's usually a page on your website that confirms(success or fail) their Stripe account setup is complete.
                type="account_onboarding",
            )
                # The refresh_url is where Stripe sends the user if they click "refresh" or something goes wrong during onboarding (like a session timeout).
            return Response({"url": account_link.url})   #return the onboarding link(account_link.url) back to the client(influencer)
            
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        #This checks onboarding status(of a given influencer)

        user = request.user
        
        if not hasattr(user, 'influencer_profile'):
            return Response({"error": "Only influencers can access this endpoint"}, 
                           status=status.HTTP_403_FORBIDDEN)
                           
        influencer = user.influencer_profile
        
        # this checks if a given influencer has a Stripe account. if not, it means they haven't completed the Stripe onboarding process.
        if not influencer.stripe_account_id:
            return Response({          # Return that the influencer hasn’t onboarded yet(b/c it doesn't even have a Stripe account in the first place )
                "onboarded": False,
                "message": "Stripe account not set up yet"
            })
        
        try:
            # if the influencer has a Stripe account, then Check the account status
            account = stripe.Account.retrieve(influencer.stripe_account_id)  # here retreiving the specific Stripe account info

            # If onboarding is complete, mark the influencer as onboarded in your DB
            if account.details_submitted and not influencer.onboarded:
                influencer.onboarded = True
                influencer.save()
            
            return Response({
                "onboarded": account.details_submitted,     # 'account.details_submitted' checks if the influencer(client) has completed the necessary steps, including entering their bank account details. It returns True if the onboarding is complete(or was succesful), indicating the account(the Stripe account) is ready for use.
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "account_status": "active" if account.details_submitted else "pending"
            })
            
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# POST: Start onboarding process.
# GET: Check onboarding progress(status).




User = get_user_model()

## CONVERSATION VIEW SET
class ConversationViewSet(ModelViewSet):
    #queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only return conversations the current user is part of
        return Conversation.objects.filter(participants=self.request.user)

    def get_permissions(self):
        if self.action in ['update', 'destroy']:
            return [IsAdminUser()]  # Only admins can update/delete a conversation
        return super().get_permissions()
        
    
    def create(self, request):
        # Extracts the list of user IDs from the request data(users who are going to be in the conversation). If no participants are provided, it defaults to an empty list.
        user_ids = request.data.get('participants', [])
        
        # To put the current authenticated user as part of the conversation(yes it is done automatically)
        if request.user.id not in user_ids:
            user_ids.append(request.user.id)
        
        # Check if a conversation with these exact participants/users already exists in the db
        existing_conversation = Conversation.objects.filter(
            participants__id__in=user_ids
        ).annotate(
            participant_count=Count('participants')
        ).filter(participant_count=len(user_ids)).first()
        
        if existing_conversation:   #if yes, then you return the already created conversation data back to the client  
            serializer = self.get_serializer(existing_conversation)
            return Response(serializer.data)
        
        # if not, then create new conversation
        conversation = Conversation.objects.create()
        conversation.participants.set(User.objects.filter(id__in=user_ids))  #This is how many to many r/n ship fields are set
        
        serializer = self.get_serializer(conversation)  #Here The view calls the serializer with the conversation instance so that the serializer converts the instance to a dictionary(to format the data properly in a correct return format)
        return Response(serializer.data)     #here the viewset serializes the dictionary to json and sends it back to the client



"""
- typical json request body data: { "participants": [2, 3] }
- so 'user_ids' including the current user(id 1 added automatically) is like: user_ids = [1, 2, 3] 

- DRF handles the initial parsing of request data to a dictionary before it reaches your view. This parsing happens in DRF's request handling pipeline, not in your view.
- typically a serializer handles input validation, object creation and converting an instance to a dictionary(before it gets serialized  by the viewset)
- But in the case of 'ConversationViewSet', there is no deserialization and input validation at all. the object creation(conversation instance) is done by the viewset itself(in the create method)
so in this case, the ConversationSerializer's job is only to convert an instance(the created conversation instance) to a dictionary and then give it back to the viewset to serialized and returned to the client

- Deserializing is converting JSON data into a dictionary, ensuring the incoming data is in the correct format.
- Converting an instance to a dictionary is done(by a serializer) to format the data properly(in a correct return format) before returning it to the viewset to be converted to JSON for the client.
- Serializing is converting a dictionary to JSON for the response(to the client).

"""

class MessageViewSet(ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_pk')  # note: conversation_pk from nested router
        conversation = Conversation.objects.filter(id=conversation_id, participants=self.request.user).first()
        if not conversation:
            return Message.objects.none()
        return Message.objects.filter(conversation=conversation)


    def perform_create(self, serializer):
        conversation_id = self.kwargs.get('conversation_id')
        conversation = Conversation.objects.get(id=conversation_id)

        if self.request.user not in conversation.participants.all():
            return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

        serializer.save(sender=self.request.user, conversation=conversation)

    # def destroy(self, request, *args, **kwargs):
    #     message = self.get_object()
    #     if message.sender != request.user:
    #         return Response({'error': 'You can only delete your own messages'}, status=status.HTTP_403_FORBIDDEN)
    #     return super().destroy(request, *args, **kwargs)



class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        notifications = MessageNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).select_related('message__sender', 'message__conversation')[:10]
        
        data = [{
            'id': n.id,
            'sender': n.message.sender.username,
            'content': n.message.content[:50] + ('...' if len(n.message.content) > 50 else ''),
            'created_at': n.created_at.isoformat(),
            'conversation_id': n.message.conversation.id
        } for n in notifications]
        
        return Response({'notifications': data, 'count': len(data)})

class MarkNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        notification_ids = request.data.get('ids', [])
        MessageNotification.objects.filter(
            recipient=request.user,
            id__in=notification_ids
        ).update(is_read=True)
        return Response({'status': 'success'})





#### CONTRACT VIEW SET
class ContractViewSet(ModelViewSet):     #a viewset that handles all CRUD operations (Create, Read, Update, Delete)  #a viewset handles the http requests
    queryset = Contract.objects.all()           #The default queryset includes all Contract objects
    serializer_class = ContractSerializer       #The default serializer is the basic ContractSerializer
    
    def get_serializer_class(self):             #This method dynamically selects a serializer based on an action
        if self.action == 'retrieve':           #for viewing/retrieving a single contract
            return ContractDetailSerializer
        elif self.action == 'create':
            return ContractCreateSerializer     #for creating a contract
        return ContractSerializer
    
    def get_queryset(self):                     #This method filters the queryset based on the current user
        user = self.request.user
        
        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(brand=user.brand_profile)    # user.brand_profile is an access through the reverse r/n ship
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(influencer=user.influencer_profile)
        return Contract.objects.none()

    
    def create(self, request, *args, **kwargs):
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save()
        return Response(ContractDetailSerializer(contract).data, status=status.HTTP_201_CREATED)

    
    @action(detail=True, methods=['post'])    #api/contracts/{id}/sign_contract/
    def sign_contract(self, request, pk=None):
        contract = self.get_object()          #get the specific contract instance
        user = request.user
        
        if hasattr(user, 'brand_profile') and user.brand_profile == contract.brand:     #you can only sign a contract you're in(or you own)
            contract.is_signed_by_brand = True
            contract.brand_signed_at = timezone.now()
        elif hasattr(user, 'influencer_profile') and user.influencer_profile == contract.influencer:   #you can only sign a contract you're in(or you own)
            contract.is_signed_by_influencer = True
            contract.influencer_signed_at = timezone.now()
        else:
            return Response({"error": "You are not authorized to sign this contract"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        contract.save()           #save the new contract instance info in the db
        return Response(ContractDetailSerializer(contract).data)        # ContractDetailSerializer(contract) - this converts the contract instance to a dictionary(for the correct return format)



# REQUESTED OFFERS VIEW SET
class RequestedOffersViewSet(ModelViewSet):
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=False
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=False
            )
        return Contract.objects.none()



class AcceptedOffersViewSet(ModelViewSet):
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='pending'
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='pending'
            )
        return Contract.objects.none()


class ActiveContractsViewSet(ModelViewSet):
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow'
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow'
            )
        return Contract.objects.none()


class ActiveContractsBrandViewSet(ModelViewSet):
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status='pending',
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status='pending',
            )
        return Contract.objects.none()


class ApproveWorksViewSet(ModelViewSet):  #contracts waiting for approval or revision request
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status='submitted',
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status='submitted',
            )
        return Contract.objects.none()


class ContractsOnRevisionViewset(ModelViewSet):   #revision contracts
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status__in=['revision', 'updated']
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='in_escrow',
                deliverable__status__in=['revision', 'updated']
            )
        return Contract.objects.none()



class ReleasedContractsViewset(ModelViewSet):   #deliverable approved and fund released contracts
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='released',
                deliverable__status='approved',
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='released',
                deliverable__status='approved',
            )
        return Contract.objects.none()



class ReviewedContractsViewset(ModelViewSet):  
    serializer_class = ContractOfferSerializer
    #permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(
                brand=user.brand_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='released',
                deliverable__status='approved',
                review__rating__isnull=False,    # This ensures only reviewed contracts are included
            )
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(
                influencer=user.influencer_profile,
                is_signed_by_brand=True,
                is_signed_by_influencer=True,
                payment__status='released',
                deliverable__status='approved',
                review__rating__isnull=False,  
            )
        return Contract.objects.none()





#### DELIVERABLE VIEW SET
class DeliverableViewSet(ModelViewSet):
    queryset = Deliverable.objects.all()
    serializer_class = DeliverableSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeliverableDetailSerializer
        return DeliverableSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'brand_profile'):
            return Deliverable.objects.filter(contract__brand=user.brand_profile) #get all deliverables where the contract's brand matches with the current user's brand profile
        elif hasattr(user, 'influencer_profile'):
            return Deliverable.objects.filter(contract__influencer=user.influencer_profile)
        return Deliverable.objects.none()

    def partial_update(self, request, *args, **kwargs):  # this is for when the 'Revision Required' button is clicked by the brand
        instance = self.get_object()
        status_value = request.data.get("status")

        if status_value == "revision":
            instance.status = "revision"
            instance.attachments.all().delete()
            instance.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Otherwise, proceed with default behavior
        return super().partial_update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def submit_attachments(self, request, pk=None):
        deliverable = self.get_object()   #deliverable is the current instance
        user = request.user

        if not hasattr(user, 'influencer_profile') or user.influencer_profile != deliverable.contract.influencer:
            return Response({"error": "Only the assigned influencer can submit this deliverable."},
                            status=status.HTTP_403_FORBIDDEN)

        # user.influencer_profile is the influencer profile of the user making the request
        # deliverable.contract.influencer is the influencer profile associated with the deliverable's contract
        # the right above 'if check' ensures that the user is not just any influencer, but specifically the influencer that owns the contract associated with this deliverable. This prevents one influencer from accessing or modifying another influencer's payments.

        serializer = SubmitDeliverableSerializer(data=request.data)   # when this is called, in the serializr, first it does field level validation(like content_files) then it does custom validation(validate method) 
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Handle URLs
        for url in validated_data.get('content_urls', []):
            DeliverableAttachment.objects.create(
                deliverable=deliverable,
                url=url
            )

        # Handle files
        for file in validated_data.get('content_files', []):
            DeliverableAttachment.objects.create(
                deliverable=deliverable,
                file=file,
                original_filename=file.name  # Store the original filename
            )

        deliverable.status = 'submitted'
        deliverable.submitted_at = timezone.now()
        deliverable.save()

        return Response(DeliverableDetailSerializer(deliverable).data, status=status.HTTP_200_OK)
    

    @action(detail=True, methods=['put'])
    def update_attachments(self, request, pk=None):
        deliverable = self.get_object()

        serializer = SubmitDeliverableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        # Clear old attachments
        deliverable.attachments.all().delete()

        for url in validated_data.get('content_urls', []):
            DeliverableAttachment.objects.create(deliverable=deliverable, url=url)

        for file in validated_data.get('content_files', []):
            DeliverableAttachment.objects.create(deliverable=deliverable, file=file, original_filename=file.name)

        return Response(DeliverableDetailSerializer(deliverable).data, status=status.HTTP_200_OK)



    # @action(detail=True, methods=['post'])
    # def review(self, request, pk=None):
    #     deliverable = self.get_object()
    #     user = request.user
        
    #     if not hasattr(user, 'brand_profile') or user.brand_profile != deliverable.contract.brand:
    #         return Response({"error": "Only the brand can review deliverables"}, 
    #                         status=status.HTTP_403_FORBIDDEN)
        
    #     status_choice = request.data.get('status')
    #     feedback = request.data.get('feedback', '')
        
    #     if status_choice not in ['approved', 'revision']:
    #         return Response({"error": "Status must be either 'approved' or 'revision'"}, 
    #                         status=status.HTTP_400_BAD_REQUEST)
        
    #     deliverable.status = status_choice
    #     deliverable.feedback = feedback
    #     deliverable.save()
        
    #     return Response(DeliverableDetailSerializer(deliverable).data)

"""
- DRF handles the initial parsing of request data to a dictionary before it reaches your view. This parsing happens in DRF's request handling pipeline, not in your view.
- So 'request.data' is a dictionary
- For create/update actions, DRF handles the initial parsing of the incoming raw HTTP request data into Python dictionaries, and then the view calls the serializer to handle validation and conversion to model instances(to work with)
- For custom actions like 'submit', DRF handles the initial parsing of the incoming raw HTTP request data into Python dictionaries, and then the view(inside the custom actions) manually does the validation logic and works with the data.
So inside a custom action, mostly the serializer is only used at the end for formatting a response(instance to dictionary)

POST /deliverables/{id}/submit/
POST /deliverables/{id}/review/
"""


class PaymentViewSet(ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PaymentDetailSerializer
        return PaymentSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'brand_profile'):
            return Payment.objects.filter(contract__brand=user.brand_profile)       #get payment where the contract's brand matches with the current user's brand profile
        elif hasattr(user, 'influencer_profile'):
            return Payment.objects.filter(contract__influencer=user.influencer_profile)
        return Payment.objects.none()

    
    @action(detail=True, methods=['post'])
    def init_payment(self, request, pk=None):
        # this creates/initializes a Stripe PaymentIntent for the brand to deposit money into platform's Stripe account(funds in to escrow).

        payment = self.get_object()
        user = request.user
        
        if not hasattr(user, 'brand_profile') or user.brand_profile != payment.contract.brand:
            return Response({"error": "Only the brand can initialize payments"}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        if payment.status != 'pending':
            return Response({"error": "Payment must be in 'pending' status to initialize"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create a payment intent in Stripe
            payment_intent_data = StripeEscrowService.create_payment_intent(payment.id)
            
            return Response({
                "client_secret": payment_intent_data['client_secret'],
                "payment_intent_id": payment_intent_data['payment_intent_id'],
                "payment": PaymentSerializer(payment).data
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    
    @action(detail=True, methods=['post'])      # deposit_to_escrow is only for confirming a payment thats already made and then update payment status in the db
    def deposit_to_escrow(self, request, pk=None):   #This is to confirm the brand’s payment and mark the payment status as "in escrow" in the db. (note: money is now in the platform’s Stripe account).  # so this is not doing the actual charge(thats already done), its just to confirm and update the payment status in db.
        payment = self.get_object()
        user = request.user
        
        if not hasattr(user, 'brand_profile') or user.brand_profile != payment.contract.brand:
            return Response({"error": "Only the brand can deposit payments to escrow"},  # only brands are able to update the payment status in the db
                           status=status.HTTP_403_FORBIDDEN)

        # user.brand_profile is the brand profile of the user making the request
        # payment.contract.brand is the brand profile associated with the payment's contract
        # the right above 'if' check ensures that the user is not just any brand, but specifically the brand that owns the contract associated with this payment. This prevents one brand from accessing or modifying another brand's payments.
        

        # Get the payment intent ID from the request
        payment_intent_id = request.data.get('payment_intent_id')
        if not payment_intent_id:
            return Response({"error": "payment_intent_id is required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Confirm the payment with Stripe and update to escrow(in db)
            updated_payment = StripeEscrowService.confirm_payment_to_escrow(
                payment.id, 
                payment_intent_id
            )
            
            return Response(PaymentDetailSerializer(updated_payment).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Payment processing error: {str(e)}"}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # the actual money transfer happens client-side when the brand user completes the payment via Stripe Checkout(it happens in the background by Stripe). happens in the pay phase
        # the above 'deposit_to_escrow' just retrieves the intent to verify if Stripe marked it as 'succeeded'(inside the 'confirm_paymen_to_escrow' method) then to update the payment status in the db
        # so actual payment is processed externally by Stripe before you confirm it here on the backend on the deposit_to_escrow.

    
    @action(detail=True, methods=['post'])
    def release_payment(self, request, pk=None):
        payment = self.get_object()
        user = request.user
        
        if not hasattr(user, 'brand_profile') or user.brand_profile != payment.contract.brand:
            return Response({"error": "Only the brand can release payments"}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        try:
            # First check if all deliverables are approved & also if the payment status is 'in escrow'
            EscrowService.can_release_payment(payment.id)
            
            # Then transfer the funds to the influencer using Stripe
            updated_payment = StripeEscrowService.transfer_to_influencer(payment.id)
            
            return Response(PaymentDetailSerializer(updated_payment).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Payment transfer error: {str(e)}"}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def refund_payment(self, request, pk=None):
        payment = self.get_object()
        user = request.user
        
        if not hasattr(user, 'brand_profile') or user.brand_profile != payment.contract.brand:
            return Response({"error": "Only the brand can refund payments"}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        if payment.status != 'in_escrow':
            return Response({"error": "Payment must be in 'in_escrow' status to be refunded"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Handle the refund through Stripe
            updated_payment = StripeEscrowService.refund_payment(payment.id)
            
            return Response(PaymentDetailSerializer(updated_payment).data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Refund error: {str(e)}"}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
    ## we use this custom endpoint on PaymentViewSet for when a contract has multiple payments. # for a single payment like our case, just use the retrieve on PaymentViewSet to get the single payment's status 

    @action(detail=False, methods=['get'])  # its a collection-level route not a detail-level route
    def escrow_summary(self, request):  #unlike the others, this is not about a specific payment, this is to get a summary of all the payments for a given contract
        
        contract_id = request.query_params.get('contract_id')   # b/c the request should be like "api/payments/escrow_summary/?contract_id=123"
        if not contract_id:
            return Response({"error": "contract_id is required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        # Check if the current user has permission to view this contract's payment summary(escrow summary)
        user = request.user
        try:
            contract = Contract.objects.get(id=contract_id)
            # Checks if the user is either the brand or influencer attached to this contract(or that owns this contract)
            if (hasattr(user, 'brand_profile') and user.brand_profile != contract.brand) and \
               (hasattr(user, 'influencer_profile') and user.influencer_profile != contract.influencer):
                return Response({"error": "You don't have permission to view this contract"}, 
                               status=status.HTTP_403_FORBIDDEN)
        except Contract.DoesNotExist:
            return Response({"error": "Contract not found"}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        summary = EscrowService.get_escrow_summary(contract_id)
        return Response(summary)    # summary is a dictionary w/h is then returned as a json to the client
"""

# a dictionary is a native python data structure that stores key-value pairs like 'summary' returned in the above
# JSON is a string format used to represent data that is sent or received over HTTP(over the internet)
# even tho json data and dictionary data look exactly similar, the main difference is, a dictionary is a native Python data structure, while JSON is just a string representation of data.
# An object instance is a specific occurrence of a class. so 'contract' is a specific occurence of a Contract model class



#Review Viewset
class IsContractParticipant(BasePermission):

    def has_permission(self, request, view):      # This permission is for general access(for GET list and POST create)  # but for the Get list, just b/c u are authenticated, u might not get all the list of Review or Dispute instances, b/c queryset narrows it.
        return request.user.is_authenticated      # so only authenticated users can make a Get or Post request 

    def has_object_permission(self, request, view, obj):    # This permission is for object-level actions like retrieving, updating, or deleting specific objects.  

        contract = obj.contract    # so 'obj' here is the review or dispute object that is being accessed(for retrieve, update or delete)

        return (    # so here only users who are part of the contract(in w/h the object/instance is in) can make a retrieve, update and delete request on the object/instance
            (hasattr(request.user, 'brand_profile') and request.user.brand_profile == contract.brand) or
            (hasattr(request.user, 'influencer_profile') and request.user.influencer_profile == contract.influencer)
        )

class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsContractParticipant]
    
    def get_queryset(self):
        user = self.request.user

         # Check for query parameters
        influencer_user_id = self.request.query_params.get('influencer_user_id')

        # If specific influencer's reviews are requested from a brand page(user)
        if influencer_user_id:    # api/reviews/?influencer_user_id=123
            return Review.objects.filter(reviewee_id=influencer_user_id)

        if hasattr(user, 'brand_profile'):
            # Bcoz brand can only be a reviewer
            return Review.objects.filter(reviewer=user)

        elif hasattr(user, 'influencer_profile'):
            # Bcoz influencer can only be a reviewee
            return Review.objects.filter(reviewee=user)

        return Review.objects.none()


    def perform_create(self, serializer):
        contract_id = self.request.data.get('contract')
        reviewee_id = self.request.data.get('reviewee')
        
        #this is checking if there is already a review instance with the current reviewer and reviewee before creating a new one with them
        existing_review = Review.objects.filter(    
            contract_id=contract_id,
            reviewer=self.request.user,
            reviewee_id=reviewee_id
        ).exists()
        
        if existing_review:
            raise ValidationError("You have already reviewed this person for this contract.")
        #if not
        serializer.save()   # this calls the create method in the serializer


# when DRF triggers/calls the create() method/action for handling post http request, it internally calls the performs_create().

# perform_create() is used for handling some kind of checking before saving (like for our eg, an already existing review) and then does saving

# so here in my code, the create() action does its main task w/h is handling the post http request, initializing the serializer, calling the is.valid(). and then, perform_create() handles its checking of review and then saving of an object




# Dispute Viewset
class DisputeViewSet(ModelViewSet):
    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated, IsContractParticipant]   # there is the 'IsContractParticipant' class definiton right above ReviewViewSet
   
    
    def get_queryset(self):
        user = self.request.user
        
        # Get contracts where the user is involved
        if hasattr(user, 'brand_profile'):
            contracts = Contract.objects.filter(brand=user.brand_profile)
        elif hasattr(user, 'influencer_profile'):
            contracts = Contract.objects.filter(influencer=user.influencer_profile)
        else:
            return Dispute.objects.none()
            
        queryset = Dispute.objects.filter(contract__in=contracts)   # so even if you don't initiate any of the disputes, just b/c you're in the contract, if there is any dispute in that contract, you get those dispute instances(in the queryset).
                                                                    # so You don't have to be the one who initiated the dispute to see it in your queryset.
        # further Filter the queryset for a specific contract
        contract_id = self.request.query_params.get('contract_id', None)
        if contract_id is not None:
            queryset = queryset.filter(contract_id=contract_id)
            
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(initiated_by=self.request.user)             # the perform_create is used to set extra data in the validated_data before saving the object(before calling the serializer's create method)   # you know in the calling of serializer.save(), the validated_data is being passed to the create method of the serializer
    
    def perform_update(self, serializer):                           # like perform_create(), perform_update() is used for handling some kind of checking before saving
        instance = self.get_object()
        user = self.request.user
        
        new_status = self.request.data.get('status')
        
        # Only admins can set dispute's status to 'resolved'
        if new_status == 'resolved' and not user.is_staff:
            raise PermissionDenied("Only staff members can resolve disputes")
            
        serializer.save()









class TikTokAuthView(APIView):
    permission_classes = [AllowAny]  # Allow unauthenticated access for OAuth flow

    def post(self, request):
        # Get the authorization code(access code) from the request
        code = request.data.get('code')
        #print(code)

        if code and ('&' in code or '%26' in code):
            code = code.split('&')[0].split('%26')[0]

        if not code:
            return Response({"error": "Authorization code is required"}, status=status.HTTP_400_BAD_REQUEST)

        # TikTok OAuth endpoints
        token_url = "https://open.tiktokapis.com/v2/oauth/token/"  # this is the url to request tiktok for access token passing auth/access code
        user_info_url = "https://open.tiktokapis.com/v2/user/info/"  # this is the url to request/fetch user tiktok data passing access token from tiktok's api
        
        # Your TikTok app credentials - store these in Django settings.py
        client_key = settings.TIKTOK_CLIENT_KEY
        client_secret = settings.TIKTOK_CLIENT_SECRET
        redirect_uri = settings.TIKTOK_REDIRECT_URI
        

        # Exchange the code for an access token
        token_payload = {
            'client_key': client_key,
            'client_secret': client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }  
        
        #In the backend, you pass redirect_uri to the access token URL mainly for security reasons, nothing else.
        
        try:
            # 1111111111111 to Make request to TikTok for access token(passing auth/access code)
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cache-Control': 'no-cache',
            }

            token_response = requests.post(token_url, headers=headers, data=token_payload)

            print("Status code:", token_response.status_code)
            print("token Response text:", token_response.text)

            # print("Request URL:", token_response.request.url)
            # print("Request Headers:", token_response.request.headers)
            # print("Request Body:", token_response.request.body)
            # print("Response Status:", token_response.status_code)
            # print("Response Content:", token_response.text)



            if token_response.status_code != 200:
                return Response({"error": "Failed to obtain access tokens", "details": token_response.text}, 
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                token_data = token_response.json()
            except ValueError:
                return Response({"error": "Invalid JSON in token response", "details": token_response.text},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Extract tokens and user info from response
            access_token = token_data['access_token']
            open_id = token_data['open_id']
            





            
            # 222222222 Request/Fetch user info using the access token from tiktok
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            params = {
                "fields": "open_id,union_id,avatar_url,display_name,username,follower_count,video_count,likes_count"
            }
            
            user_response = requests.get(user_info_url, headers=headers, params=params)

            print("Status code:", user_response.status_code)
            print("user Response text:", user_response.text)


            if user_response.status_code != 200:
                return Response(
                    {"error": "Failed to fetch user info", "details": user_response.text},
                    status=status.HTTP_400_BAD_REQUEST
                )


            try:
                user_data = user_response.json()
            except ValueError:
                return Response(
                    {"error": "Invalid JSON in user info response", "details": user_response.text},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            print("user data in the backend", user_data)

            # Extract TikTok username and other user info
            tiktok_info = {
                'tiktok_username': user_data['data']['user'].get('username', ''),
                'tiktok_display_name': user_data['data']['user'].get('display_name', ''),
                'tiktok_avatar_url': user_data['data']['user'].get('avatar_url', ''),
                'tiktok_follower_count': user_data['data']['user'].get('follower_count', ''),
                'tiktok_video_count': user_data['data']['user'].get('video_count', ''),
                'tiktok_likes_count': user_data['data']['user'].get('likes_count', ''),                    
                'tiktok_open_id': open_id,
                'tiktok_access_token': access_token,
            }
            
            # Return the TikTok user info to the frontend
            return Response({
                "success": True,
                "tiktok_info": tiktok_info
            }, status=status.HTTP_200_OK)
            
        except requests.exceptions.RequestException as e:
            return Response({"error": "Network error when connecting to TikTok", "details": str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ValueError as e:
            return Response({"error": "Invalid response from TikTok", "details": str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)



## for subscription
class CreateCheckoutSessionView(APIView):  # this is for creating a checkout session when the user clicks 'subscribe' on the frontend
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            price_id = request.data.get('price_id')
            
            if not price_id:
                return Response(
                    {'error': 'Price ID is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # success_url=f"{settings.FRONTEND_URL}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}",  # if the subscription is complete(if the checkout session is completed or if the money is paid)
            
            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{settings.FRONTEND_URL}/MySubscriptionPage",
                cancel_url=f"{settings.FRONTEND_URL}/subscriptions",
                customer_email=request.user.email,
                metadata={
                    'user_id': request.user.id,
                }
            )
            
            return Response({
                'url': checkout_session.url,  # for the frontend to use to shoot the stripe checkout form
                'session_id': checkout_session.id
            })
            
        except stripe.error.StripeError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=500)



logger = logging.getLogger(__name__)

class StripeWebhookView(APIView):  # this is a stripe webhook, it listens to subscription events, like its used for when the checkout session is completed(or subscription is completed/paid)
    permission_classes = []
    
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            return Response(status=400)
        except stripe.error.SignatureVerificationError:
            return Response(status=400)
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            # Handle successful subscription
            self.handle_subscription_success(session)   # this calls the webhook handler that updates the database of influencer user and sends email
        
        return Response(status=200)
    

    def handle_subscription_success(self, session):
        try:
            logger.info(f"Starting webhook for session: {session.get('id')}")
            
            # Get the price ID from the session to determine plan
            line_items = stripe.checkout.Session.list_line_items(session['id'])
            price_id = line_items.data[0].price.id
            logger.info(f"Price ID: {price_id}")
            
            # Map price IDs to plan names
            plan_mapping = {
                'price_1RTgh8Rt8NVEmh7TSprcxTFh': 'basic',
                'price_1RThTKRt8NVEmh7TwDnzxEmL': 'pro', 
            }
            
            user_id = session['metadata']['user_id']
            logger.info(f"User ID: {user_id}")
            
            influencer = InfluencerProfile.objects.get(user_id=user_id)
            influencer.is_subscribed = True
            influencer.subscription_plan = plan_mapping.get(price_id)
            influencer.subscription_start_date = timezone.now()
            influencer.save()
            
            logger.info(f"Database updated for user {user_id}")
            

            # Calculate the end date (30 days from now)
            end_date = datetime.now() + timedelta(days=30)
            formatted_end_date = end_date.strftime("%B %d, %Y")  # e.g., "June 27, 2025"

            # Separate email handling
            try:
                send_mail(
                    subject="Subscription Activated",
                    message=f"hello {influencer.user.first_name}, you have successfully subscribed to the {influencer.subscription_plan} Plan.\n\n"
                            f"Your subscription will end on {formatted_end_date}.\n\n"
                            f"Thank you for subscribing, Enjoy!",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[influencer.user.email],
                    fail_silently=False,
                )
                logger.info(f"Email sent to {influencer.user.email}")
            except Exception as e:
                logger.error(f"Email failed: {e}")
                
        except (KeyError, InfluencerProfile.DoesNotExist) as e:
            logger.error(f"Webhook error: {e}")
            return Response(status=400)
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return Response(status=500)

# when the checkout session is completed, stripe webhook listens to that and stripe makes the request to the 'api/webhooks/stripe/' endpoint in django and django(the StripeWebhookView) receives it and uses the stripe webhook secrect to verify its from stripe. and if so, it calls its webhook handler to update the database...
from django.shortcuts import render
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser, BasePermission
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.views import APIView
from .models import Category, Language, InfluencerProfile, BrandProfile, Conversation, Contract, Deliverable, Payment, Review, Dispute
from .serializers import CategorySerializer, LanguageSerializer, BrandProfileSerializer, InfluencerProfileSerializer, ConversationSerializer, ContractSerializer, ContractDetailSerializer, DeliverableSerializer, DeliverableDetailSerializer, PaymentSerializer, PaymentDetailSerializer, ReviewSerializer, DisputeSerializer
from .services.escrow_service import EscrowService
from .services.stripe_escrow_service import StripeEscrowService
import stripe

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
    queryset = InfluencerProfile.objects.all()
    serializer_class = InfluencerProfileSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete'] 


    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action == 'me':
            return [IsAuthenticated()]
        elif self.action in ['list', 'update', 'partial_update', 'destroy']:
            return [AllowAny()]
        return [AllowAny()]    #this block you to see influencer details(specific resource) like 'api/influencers/1/'


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



class BrandUserViewSet(ModelViewSet):
    queryset = BrandProfile.objects.all()
    serializer_class = BrandProfileSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action == 'me':
            return [IsAuthenticated()]
        elif self.action in ['list', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

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
                    return_url=f"{settings.FRONTEND_URL}/onboarding/stripe/complete",
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
                return_url=f"{settings.FRONTEND_URL}/onboarding/stripe/complete",
                type="account_onboarding",
            )
            
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
            
            return Response({
                "onboarded": account.details_submitted,     # 'account.details_submitted' checks if the influencer(client) has completed the necessary steps, including entering their bank account details. It returns True if the onboarding is complete(or was succesful), indicating the account(the Stripe account) is ready for use.
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "account_status": "active" if account.details_submitted else "pending"
            })
            
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# POST: Start onboarding process.
# GET: Check onboarding progress.


User = get_user_model()

class ConversationViewSet(ModelViewSet):
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

- typically a serializer handles deserialization(from json to dic), input validation, object creation and converting an instance to a dictionary(before it gets serialized  by the viewset)
- But in the case of 'ConversationViewSet', there is no deserialization and input validation at all. the object creation(conversation instance) is done by the viewset itself(in the create method)
so in this case, the ConversationSerializer's job is only to convert an instance(the created conversation instance) to a dictionary and then give it back to the viewset to serialized and returned to the client

- Deserializing is converting JSON data into a dictionary, ensuring the incoming data is in the correct format.
- Converting an instance to a dictionary is done(by a serializer) to format the data properly(in a correct return format) before returning it to the viewset to be converted to JSON for the client.
- Serializing is converting a dictionary to JSON for the response(to the client).

"""




class ContractViewSet(ModelViewSet):     #a viewset that handles all CRUD operations (Create, Read, Update, Delete)  #a viewset handles the http requests
    queryset = Contract.objects.all()           #The default queryset includes all Contract objects
    serializer_class = ContractSerializer       #The default serializer is the basic ContractSerializer
    
    def get_serializer_class(self):             #This method dynamically selects a serializer based on an action
        if self.action == 'retrieve':           #for viewing/retrieving a single contract
            return ContractDetailSerializer
        return ContractSerializer
    
    def get_queryset(self):                     #This method filters the queryset based on the current user
        user = self.request.user
        
        if hasattr(user, 'brand_profile'):
            return Contract.objects.filter(brand=user.brand_profile)    # user.brand_profile is an access through the reverse r/n ship
        elif hasattr(user, 'influencer_profile'):
            return Contract.objects.filter(influencer=user.influencer_profile)
        return Contract.objects.none()
    
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
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        deliverable = self.get_object()   #deliverable is the current instance
        user = request.user
        
        if not hasattr(user, 'influencer_profile') or user.influencer_profile != deliverable.contract.influencer:  #the latter one is comparing two objects
            return Response({"error": "Only the influencer can submit deliverables"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        # user.influencer_profile is the influencer profile of the user making the request
        # deliverable.contract.influencer is the influencer profile associated with the deliverable's contract
        # the right above 'if check' ensures that the user is not just any influencer, but specifically the influencer that owns the contract associated with this deliverable. This prevents one influencer from accessing or modifying another influencer's payments.
        

        
        # Update content_url if provided
        content_url = request.data.get('content_url')
        if content_url:
            deliverable.content_url = content_url
        
        # Handle file upload if provided
        content_file = request.FILES.get('content_file')
        if content_file:
            deliverable.content_file = content_file
        
        deliverable.status = 'submitted'
        deliverable.submitted_at = timezone.now()
        deliverable.save()
        
        return Response(DeliverableDetailSerializer(deliverable).data)
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        deliverable = self.get_object()
        user = request.user
        
        if not hasattr(user, 'brand_profile') or user.brand_profile != deliverable.contract.brand:
            return Response({"error": "Only the brand can review deliverables"}, 
                            status=status.HTTP_403_FORBIDDEN)
        
        status_choice = request.data.get('status')
        feedback = request.data.get('feedback', '')
        
        if status_choice not in ['approved', 'revision']:
            return Response({"error": "Status must be either 'approved' or 'revision'"}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        deliverable.status = status_choice
        deliverable.feedback = feedback
        deliverable.save()
        
        return Response(DeliverableDetailSerializer(deliverable).data)

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
        user = self.request.user    # the current user making the request
        queryset = Review.objects.filter(  # you only get a review instances where you are either the reviewer or the reviewee
            reviewer=user
        ) | Review.objects.filter(
            reviewee=user
        )
        contract_id = self.request.query_params.get('contract_id')  # api/reviews/?contract_id=""
        if contract_id:
            queryset = queryset.filter(contract_id=contract_id)  # you can also over filter(narrow) the review instances you get like for a specific contract
        return queryset

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
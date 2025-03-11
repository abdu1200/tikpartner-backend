from django.shortcuts import render
from django.db.models import Count
from django.contrib.auth import get_user_model
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from .models import Category, Language, InfluencerProfile, BrandProfile, Conversation
from .serializers import CategorySerializer, LanguageSerializer, BrandProfileSerializer, InfluencerProfileSerializer, ConversationSerializer


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
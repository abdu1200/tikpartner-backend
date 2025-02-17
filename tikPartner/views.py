from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from .models import Category, Language, InfluencerProfile, BrandProfile
from .serializers import CategorySerializer, LanguageSerializer, BrandProfileSerializer, InfluencerProfileSerializer


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
                return Response(serializer.data)
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











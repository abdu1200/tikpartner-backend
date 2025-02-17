from rest_framework import serializers
from .models import Category, Language, InfluencerProfile, BrandProfile
from custom.serializers import CustomUserSerializer 
from custom.models import CustomUser


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']



class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'name']



"""
- after deserialization, when a serializer validates the data, it checks required fields, formats, unique constraints
- If validation passes, the validated_data is returned to the viewset and then used in create() or update()
- so the common error is occurring because the unique field validation(by checking the db) is happening at the serializer level before reaching your update method
"""   

"""
- after deserialization, first DRF executes Field Level Validations based on the model definitions
- field level validations are like 'validate_username()', 'validate_email()', etc in the CustomUserSerializer. And also like 'validate_category()', 'validate_languages()', etc in the InfluencerProfileSerializer
- and then after that, it exhibits Full Object validation like 'validate()' in the InfluencerProfileSerializer, and this helps us to handle additional validations like our specific update case
- and then at last, the InfluencerProfileSerializer returns the whole validated data to the viewset
"""

class InfluencerProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # a nested serializer field

    class Meta:
        model = InfluencerProfile
        fields = ['user', 'category', 'languages', 'budget_min', 'budget_max', 
                  'tiktok_username', 'follower_count', 'average_views', 
                  'engagement_rate', 'verified_status'] 

    
    def validate(self, data):
        user_data = data.get('user', {})     #deserialized but not yet validated user data
        user_instance = self.instance.user if self.instance else None    # the current user being updated

        # Only validate uniqueness if the the new value the user put is different from the current user in the db
        if user_instance:    #if so, then it is a user update case
            if 'username' in user_data:
                if (user_data['username'] != user_instance.username and 
                    CustomUser.objects.filter(username=user_data['username']).exists()):
                    raise serializers.ValidationError({
                        'user': {'username': ['A user with that username already exists.']}
                    })
                    
            if 'email' in user_data:
                if (user_data['email'] != user_instance.email and 
                    CustomUser.objects.filter(email=user_data['email']).exists()):
                    raise serializers.ValidationError({
                        'user': {'email': ['A user with this email already exists.']}
                    })

        return data


    def create(self, validated_data):
        user_data = validated_data.pop('user')      # validated_data is a deserialized validated dictionary(key-value pairs)  # user_data is also a dictionary by it self
        languages_data = validated_data.pop('languages', [])  #in the validated_data dictionary, languages is a key and its value is an array(of languages)    #so languages_data is an array

        user = CustomUser.objects.create_user(**user_data)  # Create user   #here we use 'create_user' method of the custom user manager instead of just 'create'    # **user_data is unpacking a dictionary    #user is a python object
        influencer_profile = InfluencerProfile.objects.create(user=user, **validated_data) #create InfluencerProfile
        influencer_profile.languages.set(languages_data)   # assigning the lanuages_data(an array of languages) to the languages field of the InfluencerProfile(w/h is a many to many field)

        return influencer_profile


    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})     #validated_data is a dictionary containing the deserialized validated input data     #user is a key in the dictionary  
        languages_data = validated_data.pop('languages', None)  #languages_data is an array and languages is a key in the dictionary

        if user_data:
            user_instance = instance.user
            for attr, value in user_data.items():    # 'attr' and 'value' represents key and value in the 'user_data' dictionary 
                setattr(user_instance, attr, value)  # 'setattr' sets the the values in the user_data dictionary to the corresponding fields of the instance.user
            user_instance.save()  

        if languages_data is not None:
            instance.languages.set(languages_data)  

        for attr, value in validated_data.items():  
            setattr(instance, attr, value)         #instance represents the InfluencerProfile instance

        instance.save()  
        return instance                            #return the updated instance to the viewset to be then serialized and returned back to the client as json


"""
- The .create() method in the InfluencerProfileSerializer(or in any serializer) does not support writable nested fields(like user) by default.
and for it to work, 1, you need to Write an explicit .create() method in/for the serializer that handles both the creation of Influencer Profile and a User at the same time
                    2, or set read_only=True on nested serializer fields 
  
- there are two types of nested serializer fields: 1,both writable and readable nested field (works only if you create a custom create() method in the serializer)  
                                                  2,only readable nested field

- " user = CustomUserSerializer() " - is a writable nested field
- " user = CustomUserSerializer(read_only=True) " - is a read only(only readable) nested field

- in the serializer, for eg, when we are creating an Influener Profile, for a category, django presents all the different instances of a category from the database for us to choose one(cuz its a many to one r/n ship)  
and the same for languages, but it lets us select more than one language(cuz its a many to many r/n ship).

- when you create an InfluencerProfile(in the db using the create method), even though the languages field is a many to many field, you can not assign the validated multiple language instances(like eng, amh) directly to the languages field(many to many field)
what you do is, first you create your main instance(w/h is the InfluencerProfile) with out setting its many to many field(w/h is languages in this case) and then you use the '.set()' to assign the multiple instances(language instances) to the many to many field(w/h is languages)


'validated_data' is structured like: 

{
    "user": { ... },            # Nested dictionary for user data
    "languages": [ ... ],       # List of language instances
    "follower_count": 0,        # normal data
    ...
}

"""        

class BrandProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer() # Nest the full user details (nest CustomUserSerializer)

    class Meta:
        model = BrandProfile
        fields = ['user', 'category', 'company_name', 'website', 
                  'company_size', 'verification_documents']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.create(**user_data)  
        brand_profile = BrandProfile.objects.create(user=user, **validated_data)
        return brand_profile


    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)  

        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)  
            instance.user.save()  

        for attr, value in validated_data.items():
            setattr(instance, attr, value)  

        instance.save()  
        return instance

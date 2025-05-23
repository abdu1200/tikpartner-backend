from rest_framework import serializers
from .models import Category, Language, InfluencerProfile, BrandProfile, Conversation, Message, Contract, Deliverable, DeliverableAttachment, Payment, Review, Dispute
from custom.user_serializers import CustomUserSerializer 
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
- so the COMMON ERROR is occurring because the unique field validation(by checking the db) is happening at the serializer level before reaching your update method
"""   

"""
- after deserialization, first DRF executes Field Level Validations based on the model definitions(like validating required fields, uniqueness(w/h is different in our case, but yeah), formats, etc)
- field level validations are like 'validate_username()', 'validate_email()', etc in the CustomUserSerializer. And also like 'validate_category()', 'validate_languages()', etc in the InfluencerProfileSerializer
- and then after that, it executes Full Object validation like 'validate()' in the InfluencerProfileSerializer, and this helps us to handle additional validations. like for eg our case, w/h is a custom unique field validation(for user's username and email input) for updating and creating users.
- and then at last, the InfluencerProfileSerializer returns the whole validated data to the viewset

- when django intializes a nested serializer(CustomUserSerializer) inside InfluencerProfileSerializer, it doesn't pass it the current user instance. so you can't do custom update validation logics inside 'validate_username()' and the likes        
"""

class InfluencerProfileSerializer(serializers.ModelSerializer):
    user = CustomUserSerializer()  # a nested serializer field

    class Meta:
        model = InfluencerProfile
        fields = [
            'id', 'user', 'category', 'gender', 'languages', 'budget',
            'tiktok_username', 'avatar_url', 'display_name',
            'follower_count', 'video_count', 'likes_count',
            'stripe_account_id'
        ]


    def validate(self, data):
        user_data = data.get('user', {})     #deserialized but not yet validated user data

        username = user_data.get("username")
        email = user_data.get("email")

        # Debugging: Check if instance is being passed from the viewset to the InfluencerProfileSerializer
        print("Instance in validate():", self.instance)

        # updating an existing user
        if self.instance:
            if username and username != self.instance.user.username and CustomUser.objects.filter(username=username).exists():
                raise serializers.ValidationError({"username": "A user with that username already exists."})
            if email and email != self.instance.user.email and CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "A user with this email already exists."})
        
        # creating a new user
        else:
            if username and CustomUser.objects.filter(username=username).exists():
                raise serializers.ValidationError({"username": "A user with that username already exists."})
            if email and CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "A user with this email already exists."})

        return data  # Return the validated data



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
                if attr == "password":  
                    user_instance.set_password(value)  # Hash the password before saving
                else:
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
        fields = ['id', 'user', 'category', 'company_name', 'website', 
                  'company_size', 'verification_documents']

    

    def validate(self, data):
        user_data = data.get('user', {})     #deserialized but not yet validated user data

        username = user_data.get("username")
        email = user_data.get("email")

        # Debugging: Check if instance is being passed from the viewset to the BrandProfileSerializer
        print("Instance in validate():", self.instance)

        # updating an existing user
        if self.instance:
            if username and username != self.instance.user.username and CustomUser.objects.filter(username=username).exists():
                raise serializers.ValidationError({"username": "A user with that username already exists."})
            if email and email != self.instance.user.email and CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "A user with this email already exists."})
        
        # creating a new user
        else:
            if username and CustomUser.objects.filter(username=username).exists():
                raise serializers.ValidationError({"username": "A user with that username already exists."})
            if email and CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "A user with this email already exists."})

        return data  # Return the validated data



    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.create_user(**user_data)  
        brand_profile = BrandProfile.objects.create(user=user, **validated_data)
        return brand_profile


    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)        

        if user_data:
            user_instance = instance.user
            for attr, value in user_data.items():
                if attr == "password": 
                    user_instance.set_password(value)
                else:
                    setattr(user_instance, attr, value)  
            user_instance.save()  

        for attr, value in validated_data.items():
            setattr(instance, attr, value)  

        instance.save()  
        return instance





# CONVERSATION AND MESSAGE
class UserBasicSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'avatar_url']

    def get_avatar_url(self, obj):
        if hasattr(obj, 'influencer_profile') and obj.influencer_profile.avatar_url:
            return obj.influencer_profile.avatar_url

        if hasattr(obj, 'brand_profile') and obj.profile_picture:  
            try:
                return obj.profile_picture.url  #obj.profile_picture returns a Django ImageFieldFile object, but .url returns the actual URL string(MEDIA_URL)
            except ValueError:
                return None

        return None

class ConversationSerializer(serializers.ModelSerializer):
    participants = UserBasicSerializer(many=True, read_only=True)
    latest_message = serializers.SerializerMethodField() # SerializerMethodField in Django REST Framework is inherently read-only
    
    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'created_at', 'latest_message']

    def get_latest_message(self, obj):    #to get the latest message in a given conversation
        latest = obj.messages.order_by('-created_at').first()
        if latest:
            return {
                'id': latest.id,
                'content': latest.content,
                'sender': latest.sender.id,
                'sender_username': latest.sender.username,
                'is_read': latest.is_read, 
                'created_at': latest.created_at
            }   
        return None




class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.StringRelatedField(read_only=True)  # returns sender.username

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'content', 'attachments', 'is_read', 'created_at']
        read_only_fields = ['sender', 'created_at', 'is_read']





## CONTRACT
class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'       #includes all Contact model fields
        read_only_fields = ('created_at', 'updated_at')


class ContractDetailSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='brand.company_name')   #a custom field #it is the 'company_name' property of the related 'brand' object/field
    influencer_name = serializers.ReadOnlyField(source='influencer.display_name')  #a custom field #it is the 'tiktok_username' property of the related 'influencer' object/field
    
    class Meta:
        model = Contract
        fields = '__all__'       #includes all Contract model fields plus the two new custom fields
        read_only_fields = ('created_at', 'updated_at')


class ContractCreateSerializer(serializers.ModelSerializer):
    payment_amount = serializers.DecimalField(max_digits=10, decimal_places=2, write_only=True)
    deliverable_title = serializers.CharField(write_only=True)
    deliverable_description = serializers.CharField(write_only=True, allow_blank=True, required=False)
    deliverable_deadline = serializers.DateTimeField(write_only=True)


    class Meta:
        model = Contract
        fields = [
            'brand',
            'influencer',
            'title',
            'is_signed_by_influencer',
            'influencer_signed_at',
            'is_signed_by_brand',
            'brand_signed_at',
            'payment_amount',
            'deliverable_title',
            'deliverable_description',
            'deliverable_deadline',
        ]

    def create(self, validated_data):
        payment_amount = validated_data.pop('payment_amount')
        deliverable_title = validated_data.pop('deliverable_title')
        deliverable_description = validated_data.pop('deliverable_description')
        deliverable_deadline = validated_data.pop('deliverable_deadline')

        contract = Contract.objects.create(**validated_data)

        Payment.objects.create(contract=contract, amount=payment_amount)
        Deliverable.objects.create(contract=contract, title=deliverable_title, description=deliverable_description, deadline=deliverable_deadline)

        return contract



class ContractOfferSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='brand.company_name')
    influencer_name = serializers.ReadOnlyField(source='influencer.display_name')
    payment_amount = serializers.SerializerMethodField()
    payment_id = serializers.SerializerMethodField()
    deliverable_id = serializers.SerializerMethodField()
    deliverable_title = serializers.SerializerMethodField()
    deliverable_description = serializers.SerializerMethodField()
    deliverable_deadline = serializers.SerializerMethodField()
    deliverable_submitted_at = serializers.SerializerMethodField()
    deliverable_status = serializers.SerializerMethodField()


    class Meta:
        model = Contract
        fields = [
            'id',
            'brand',
            'brand_name',
            'influencer',
            'influencer_name',
            'title',
            'is_signed_by_influencer',
            'influencer_signed_at',
            'is_signed_by_brand',
            'brand_signed_at',
            'payment_amount',
            'payment_id',
            'deliverable_id',
            'deliverable_title',
            'deliverable_description',
            'deliverable_deadline',
            'deliverable_status',
            'deliverable_submitted_at',
        ]

    def get_payment_amount(self, obj):
        return getattr(obj.payment, 'amount', None)   # contract.payment.amount  through reverse r/n ship

    def get_payment_id(self, obj):
        return getattr(obj.payment, 'id', None)

    def get_deliverable_id(self, obj):
        return getattr(obj.deliverable, 'id', '')

    def get_deliverable_title(self, obj):
        return getattr(obj.deliverable, 'title', '')

    def get_deliverable_description(self, obj):
        return getattr(obj.deliverable, 'description', '')

    def get_deliverable_deadline(self, obj):
        return getattr(obj.deliverable, 'deadline', None)

    def get_deliverable_status(self, obj):
        return getattr(obj.deliverable, 'status', '')
    
    def get_deliverable_submitted_at(self, obj):
        return getattr(obj.deliverable, 'submitted_at', '')




## deliverable
class DeliverableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deliverable
        fields = '__all__'
        read_only_fields = ('submitted_at',)


class DeliverableAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverableAttachment
        fields = ('id', 'file', 'original_filename', 'url')


class DeliverableDetailSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='contract.brand.company_name')
    influencer_name = serializers.ReadOnlyField(source='contract.influencer.display_name')
    attachments = DeliverableAttachmentSerializer(many=True, read_only=True)  # related_name='attachments'

    class Meta:
        model = Deliverable
        fields = '__all__'
        read_only_fields = ('submitted_at',)



class SubmitDeliverableSerializer(serializers.Serializer):
    # content_files and content_urls are serializer fields, but they're not from a model. # content_files is a serializer ListField where its children must be FileFields
    content_files = serializers.ListField(     
        child=serializers.FileField(),
        required=False
    )
    content_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False
    )

    # custom validation
    def validate(self, data):
        if not data.get('content_files') and not data.get('content_urls'):
            raise serializers.ValidationError("At least one file or URL must be provided.")
        return data


# a non model serializer(like above) isn't for creating(via create) or updating(via update) a model instance. it's just used for a custom logic, or for validating incoming data or for formatting a data that is to be returned. 
# so for this kind of case, you manually handle saving or updaing model instances inside the view(not automatically via seralizer.save())



## Payment
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class PaymentDetailSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='contract.brand.company_name')     # in the source, you can reference a field of the given model(so like contract.brand...) 
    influencer_name = serializers.ReadOnlyField(source='contract.influencer.display_name')
    
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

"""
# Note - There is a difference

 for the above code: brand_name = serializers.ReadOnlyField(source='contract.brand.company_name')  - this is a serializer custom field 

 for the below code: reviewer_info = UserSerializer(source='reviewer', read_only=True) - this is a nested serializer field(a readable nested serializer field)
"""




#Review serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email']

class ReviewSerializer(serializers.ModelSerializer):
    reviewer_info = UserSerializer(source='reviewer', read_only=True)   # this returns the reviewer user information(id, username & email)   # reviewer & reviewee are user objects here
    reviewee_info = UserSerializer(source='reviewee', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'contract', 'reviewer', 'reviewee', 
            'rating', 'review_text', 'created_at',
            'reviewer_info', 'reviewee_info'
        ] 
        read_only_fields = ['reviewer', 'created_at']     # here the reviewer is read only b/c we're gonna extract it from the user making the request(the influencer or brand or clients)  # so in the creation(post) of a review, you only pass the reviewee user(its user id)
    
    # when the viewset calls serializer.is_valid(), DRF converts primitives like IDs(contract: 1) into model instances for fields defined as ForeignKey, OneToOneField.
    # So "contract: 1" in JSON request becomes a contract object inside validate(). 

    def validate(self, data):    # this is just a custom validation(object level validation after field level validation)
        contract = data.get('contract')    # this is contract object
        reviewee = data.get('reviewee')    # reviewee = user object  
        
        if not contract:
            raise serializers.ValidationError("Contract is required")
        
        # Ensure reviewee is part of the contract
        if reviewee.id != contract.brand.user.id and reviewee.id != contract.influencer.user.id:
            raise serializers.ValidationError("Reviewee must be a party in the contract")
        
        # Ensure reviewer is also part of the contract  
        reviewer = self.context['request'].user      # this is how you access 'the current user making the request' in the serializer    # reviewer = the current user object
        if reviewer.id != contract.brand.user.id and reviewer.id != contract.influencer.user.id:
            raise serializers.ValidationError("You must be a party in the contract to leave a review")
        
        # Ensure reviewer is not reviewing themselves
        if reviewer.id == reviewee.id:
            raise serializers.ValidationError("You cannot review yourself")
        
        return data
    
    def create(self, validated_data):
        validated_data['reviewer'] = self.context['request'].user    # this is because the returned data(validated_data) from the validate method doesn't include the 'reviewer'
        return super().create(validated_data)



# contract_details = serializers.SerializerMethodField() - this is a serializer method field


#Dispute serializer
class DisputeSerializer(serializers.ModelSerializer):
    initiated_by_name = serializers.CharField(source='initiated_by.username', read_only=True) # serializer custom field
    contract_details = serializers.SerializerMethodField()   # Serializer method fields are read-only by default. They are only used to display computed structured data in the serialized output(dic or json)
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'contract', 'initiated_by', 'dispute_type',
            'description', 'status', 'created_at', 'resolved_at',
            'initiated_by_name', 'contract_details'
        ]
        read_only_fields = ['initiated_by', 'created_at', 'resolved_at', 'status']  # we get 'initiated_by' from the user making the request
    
    def get_contract_details(self, obj):    # obj here is the Dispute instance being serialized(the one that is being serialized to dic or json for client)
        return {
            'id': obj.contract.id,
            'brand': obj.contract.brand.company_name,
            'influencer': obj.contract.influencer.tiktok_username
        }
    
    def validate(self, data):
        # Validate or check that the user is part of the contract
        contract = data.get('contract')
        user = self.context['request'].user
        
        if not contract:
            raise serializers.ValidationError("Contract is required")
            
        # Check if user is part of the contract
        if user.id != contract.brand.user.id and user.id != contract.influencer.user.id:
            raise serializers.ValidationError("You must be a party in the contract to open a dispute on it")
            
        return data
    
    """
    def create(self, validated_data):
        validated_data['initiated_by'] = self.context['request'].user     # in this case, this line logic is done by the 'perform_create' in the viewset
        
        return super().create(validated_data)
    """
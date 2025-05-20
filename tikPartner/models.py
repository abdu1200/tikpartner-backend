from django.db import models
from django.contrib.auth.models import AbstractUser  #not needed here
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)  
    
    def __str__(self):
        return self.name

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name



class InfluencerProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='influencer_profile')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='influencers')
    gender = models.CharField(max_length=6, choices=GENDER_CHOICES, null=True, blank=True)
    languages = models.ManyToManyField(Language, related_name='influencers') 
    budget = models.CharField(max_length=30, blank=True)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)

    # TikTok Specific
    tiktok_username = models.CharField(max_length=30, unique=True)
    avatar_url = models.CharField(max_length=500, blank=True, null=True)
    display_name = models.CharField(max_length=30, unique=True, null=True)
    follower_count = models.IntegerField(default=0)
    video_count = models.IntegerField(default=0)
    likes_count = models.IntegerField(default=0)

    def __str__(self):
        return self.user.email




    
class BrandProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='brand_profile')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='brands')
    
    company_name = models.CharField(max_length=255)
    website = models.URLField(blank=True)
    company_size = models.CharField(max_length=50)
    verification_documents = models.FileField(upload_to='verification_docs/', blank=True)

    def __str__(self):
        return self.user.email




class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation between {', '.join([user.username for user in self.participants.all()])}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username} in Conversation {self.conversation.id}"





class Contract(models.Model):
    brand = models.ForeignKey(BrandProfile, on_delete=models.CASCADE, related_name='contracts')
    influencer = models.ForeignKey(InfluencerProfile, on_delete=models.CASCADE, related_name='contracts')
    title = models.CharField(max_length=255)
    is_signed_by_influencer = models.BooleanField(default=False)
    influencer_signed_at = models.DateTimeField(null=True, blank=True)
    is_signed_by_brand = models.BooleanField(default=False)
    brand_signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Contract between {self.brand.user.username} & {self.influencer.user.username}"





class Deliverable(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('revision', 'Revision Required'),
        ('approved', 'Approved'),
    )

    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, related_name='deliverable') # a contract can only have one deliverable
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    content_url = models.URLField(blank=True)
    content_file = models.FileField(upload_to='deliverables/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    feedback = models.TextField(blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Deliverable: {self.title}"





class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_escrow', 'In Escrow'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
    )

    contract = models.OneToOneField(Contract, on_delete=models.CASCADE, related_name='payment') # a contract can only have one payment
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    transfer_id = models.CharField(max_length=255, blank=True, null=True)
    transfer_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    transfer_date = models.DateTimeField(null=True, blank=True)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment of {self.amount} for Contract ID {self.contract.id}"





class Review(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given')
    reviewee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.reviewee.username} - {self.rating}⭐"





class Dispute(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='disputes') #issues might arise at different stages of the collaboration
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='initiated_disputes')
    dispute_type = models.CharField(max_length=50)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute {self.id} - {self.status}"
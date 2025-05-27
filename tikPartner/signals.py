from django.conf import settings
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from .models import Payment, Deliverable, Contract, Review, Message, MessageNotification



### PAYMENT SIGNALS

_old_status = {}  # this dictionary contains multiple instance.pk to payment status(key-value pairs) for different payment instances


# in pre_save, the instance contains the new/updated data but it has not been saved to the database yet. so The database still holds the old data until the actual save happens.
# In post_save, the instance has the new/updated data and it has already been saved to the database. so now Both the instance and the database reflect the latest changes.


# this is Django signal that listens to pre_save events(signals) on the Payment model
@receiver(pre_save, sender=Payment)
def store_old_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_payment = Payment.objects.get(pk=instance.pk) # This fetches the already existing(old) payment from the database using the current instance's pk
            _old_status[instance.pk] = old_payment.status     
        except Payment.DoesNotExist:
            _old_status[instance.pk] = None


# this is Django signal that listens to post_save events(signals) on the Payment model
@receiver(post_save, sender=Payment)
def notify_payment_status_change(sender, instance, created, **kwargs):
    #Send email notifications to influencer and brand when payment status changes in db

    # If the payment is newly created (created=True), skip sending notifications (you only care about status updates, not creation)
    if kwargs.get('created', False):    # False is a default value if 'created' key is missing in kwargs
        return
        
    old_status = _old_status.pop(instance.pk, None)
        
    # compare the old payment status with the new one
    if old_status == instance.status:           # instance.status is the new (current) payment status.
        return                                # return b/c the changed field is not the 'status' but it is one of the fields of the payment instance 
    
    # Get the related informations
    contract = instance.contract   
    brand = contract.brand
    influencer = contract.influencer
    
    # Handle different status changes
    if instance.status == 'in_escrow':
        # Notify influencer that funds are in escrow
        send_mail(
            subject="Payment is Secured in Escrow",
            message=f"Hello {influencer.user.first_name} from '{influencer.display_name}',\n\nGood news! ${instance.amount} has been placed in escrow for contract: '{contract.title}' by {brand.user.first_name} from '{brand.company_name}'.\n\nThe funds will be released to you once all deliverables are approved.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )

        # Also notify brand
        send_mail(
            subject="Payment is Secured in Escrow",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\nYou have successfully placed ${instance.amount} in escrow for contract: '{contract.title}' to influencer: {influencer.user.first_name} (from '{influencer.display_name}').\n\nThe funds will be released to the influencer once all deliverables are approved.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )

        
    elif instance.status == 'released':
        # Calculate the amount after platform fee
        net_amount = instance.transfer_amount if instance.transfer_amount else instance.amount - (instance.platform_fee or 0)
        
        # Notify influencer that payment has been released
        send_mail(
            subject="Payment Released",
            message=f"Hello {influencer.user.first_name},\n\nGreat news! your deliverables are approved and a payment of net amount: ${net_amount} (cutting 5% platform fee) for contract #{contract.title} with {brand.user.first_name} has been released to your account.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )
        
        #Also notify brands
        send_mail(
            subject="Payment Released to Influencer",
            message=f"Hello {brand.user.first_name},\n\nThis is to confirm that your payment of ${instance.amount} has been released to {influencer.user.first_name} for contract #{contract.title}.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
        
    elif instance.status == 'refunded':
        # Notify brand about the refund
        send_mail(
            subject="Payment Refunded",
            message=f"Hello {brand.user.first_name},\n\nYour payment of ${instance.amount} for contract #{contract.id} has been refunded to your account.\n\nIf you have any questions, please contact our support team.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.contact_email],
            fail_silently=False,
        )
        
        # Notify influencer about the refund
        send_mail(
            subject="Payment Refunded",
            message=f"Hello {influencer.user.first_name},\n\nWe want to inform you that the payment of ${instance.amount} for contract #{contract.id} with {brand.user.first_name} has been refunded.\n\nIf you have any questions, please contact our support team.\n\nThank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )

#do i need in-app notification other than email notification?? nofification model needed?? ask




### CONTRACT SIGNALS

_old_contract_status = {}


@receiver(pre_save, sender=Contract)
def store_old_contract_status(sender, instance, **kwargs):
    """Store the old contract signing status before saving"""
    if instance.pk:
        try:
            old_contract = Contract.objects.get(pk=instance.pk)
            _old_contract_status[instance.pk] = {
                'is_signed_by_brand': old_contract.is_signed_by_brand,
                'is_signed_by_influencer': old_contract.is_signed_by_influencer,
            }
        except Contract.DoesNotExist:
            _old_contract_status[instance.pk] = {
                'is_signed_by_brand': False,
                'is_signed_by_influencer': False,
            }


@receiver(post_save, sender=Contract)
def notify_contract_signing_changes(sender, instance, created, **kwargs):
    """Send email notifications when contract signing status changes"""
    
    # Skip notifications for newly created contracts
    if created:
        return
    
    old_status = _old_contract_status.pop(instance.pk, None)
    if not old_status:
        return
    
    brand = instance.brand
    influencer = instance.influencer
    
    # Check if brand just signed the contract(sent a contract)
    if not old_status['is_signed_by_brand'] and instance.is_signed_by_brand:
        # Notify influencer that brand signed(sent a contract)
        send_mail(
            subject="Contract Sent by Brand",
            message=f"Hello {influencer.user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"Great news! {brand.user.first_name} from '{brand.company_name}' has signed the contract: '{instance.title}'.\n\n"
                   f"Please review and sign/accept the contract to proceed with the collaboration.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )
        
        # Notify brand about their own signing/sending (confirmation)
        send_mail(
            subject="Contract Signing Confirmation",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\n"
                   f"You have successfully signed/sent the contract: '{instance.title}' to {influencer.user.first_name} from '{influencer.display_name}'.\n\n"
                   f"We are now waiting for the influencer to sign/accept the contract.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
    
    # Check if influencer just signed/accepted the contract
    if not old_status['is_signed_by_influencer'] and instance.is_signed_by_influencer:
        # Notify brand that influencer signed/accepted the contract
        send_mail(
            subject="Contract Signed/accepted by Influencer",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\n"
                   f"Excellent! {influencer.user.first_name} from '{influencer.display_name}' has signed/accepted the contract: '{instance.title}'.\n\n"
                   f"Now you can deposit the fund to escrow and the collaboration can begin.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
        
        # Notify influencer about their own signing/accepting (confirmation)
        send_mail(
            subject="Contract Signing/accepting Confirmation",
            message=f"Hello {influencer.user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"You have successfully signed/accepted the contract: '{instance.title}' with {brand.user.first_name} from '{brand.company_name}'.\n\n"
                   f"Once the funds are deposited to escrow and you can begin working on the deliverables.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )
    
    


### DELIVERABLE SIGNALS

_old_deliverable_status = {}


@receiver(pre_save, sender=Deliverable)
def store_old_deliverable_status(sender, instance, **kwargs):
    """Store the old deliverable status before saving"""
    if instance.pk:
        try:
            old_deliverable = Deliverable.objects.get(pk=instance.pk)
            _old_deliverable_status[instance.pk] = old_deliverable.status
        except Deliverable.DoesNotExist:
            _old_deliverable_status[instance.pk] = None


@receiver(post_save, sender=Deliverable)
def notify_deliverable_status_change(sender, instance, created, **kwargs):
    """Send email notifications when deliverable status changes"""
    
    # Skip notifications for newly created deliverables
    if created:
        return
    
    old_status = _old_deliverable_status.pop(instance.pk, None)
    
    # If status hasn't changed, return
    if old_status == instance.status:
        return
    
    contract = instance.contract
    brand = contract.brand
    influencer = contract.influencer
    
    # Handle different status changes
    if instance.status == 'submitted':
        # Notify brand that deliverable has been submitted
        send_mail(
            subject="Deliverable Submitted",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\n"
                   f"{influencer.user.first_name} from '{influencer.display_name}' has submitted the deliverable: '{instance.title}' for contract: '{contract.title}'.\n\n"
                   f"Please review the submission and provide your approval.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
        
        # Notify influencer about successful submission
        send_mail(
            subject="Deliverable Successfully Submitted",
            message=f"Hello {influencer.user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"Your deliverable: '{instance.title}' for contract: '{contract.title}' has been successfully submitted.\n\n"
                   f"We have notified {brand.user.first_name} from '{brand.company_name}' to review your work.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )
    
    elif instance.status == 'revision':
        # Notify influencer that revision is required
        send_mail(
            subject="Revision Required for Your Deliverable",
            message=f"Hello {influencer.user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"{brand.user.first_name} from '{brand.company_name}' has requested revisions for deliverable: '{instance.title}' (Contract: '{contract.title}').\n\n"
                   f"Please revise the work and submit the updated work.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )
        
        # Notify brand that revision request has been sent
        send_mail(
            subject="Revision Request Sent",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\n"
                   f"Your revision request for deliverable: '{instance.title}' (Contract: '{contract.title}') has been sent to {influencer.user.first_name} from '{influencer.display_name}'.\n\n"
                   f"The influencer will resubmit the work with your requested changes.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
    
    
    # Handle resubmission (when status changes from 'revision' back to 'submitted')
    elif instance.status == 'updated':
        # Notify brand about update submission
        send_mail(
            subject="Deliverable Resubmitted After Revision",
            message=f"Hello {brand.user.first_name} (from '{brand.company_name}'),\n\n"
                   f"{influencer.user.first_name} from '{influencer.display_name}' has resubmitted/updated the deliverable: '{instance.title}' for contract: '{contract.title}' with your requested revisions.\n\n"
                   f"Please review the updated submission.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand.user.email],
            fail_silently=False,
        )
        
        # Notify influencer about successful resubmission
        send_mail(
            subject="Deliverable Successfully Resubmitted",
            message=f"Hello {influencer.user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"Your revised deliverable: '{instance.title}' for contract: '{contract.title}' has been successfully resubmitted.\n\n"
                   f"We have notified {brand.user.first_name} from '{brand.company_name}' to review your updated work.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer.user.email],
            fail_silently=False,
        )




## REVIEW SIGNALS


#_old_review_status = {}

# @receiver(pre_save, sender=Review)
# def store_old_review_status(sender, instance, **kwargs):
#     """Store the old review rating before saving"""
#     if instance.pk:
#         try:
#             old_review = Review.objects.get(pk=instance.pk)
#             _old_review_status[instance.pk] = old_review.rating
#         except Review.DoesNotExist:
#             _old_review_status[instance.pk] = None


@receiver(post_save, sender=Review)
def notify_review_changes(sender, instance, created, **kwargs):
    """Send email notifications when review is created """
    
    # old_rating = _old_review_status.pop(instance.pk, None)
    
    contract = instance.contract
    brand_user = instance.reviewer  # Brand user
    influencer_user = instance.reviewee  # Influencer user
    
    # Get brand and influencer profiles
    brand = brand_user.brand_profile
    influencer = influencer_user.influencer_profile
    
    # Handle new review creation signals
    if created and instance.rating:
        # Notify influencer about new review from brand
        stars = "⭐" * instance.rating
        send_mail(
            subject="New Review Received from Brand!",
            message=f"Hello {influencer_user.first_name} (from '{influencer.display_name}'),\n\n"
                   f"You have received a new {instance.rating}-star review {stars} from {brand_user.first_name} ('{brand.company_name}') for the contract: '{contract.title}'.\n\n"
                   f"Review: \"{instance.review_text or 'No review text.'}\"\n\n"
                   f"This review helps build your reputation on our platform.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[influencer_user.email],
            fail_silently=False,
        )
        
        # Send confirmation to brand
        send_mail(
            subject="Review Successfully Submitted",
            message=f"Hello {brand_user.first_name} (from '{brand.company_name}'),\n\n"
                   f"Your {instance.rating}-star review {stars} for {influencer_user.first_name} ('{influencer.display_name}') regarding contract: '{contract.title}' has been successfully submitted.\n\n"
                   f"Your feedback helps other brands make informed decisions and helps influencers improve their services.\n\n"
                   f"Thank you for using our platform!",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[brand_user.email],
            fail_silently=False,
        )



## New message notification(in app notification)

# Signal to create notifications
@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    if created:
        recipients = instance.conversation.participants.exclude(id=instance.sender.id)
        for recipient in recipients:
            MessageNotification.objects.get_or_create(
                recipient=recipient,
                message=instance
            )
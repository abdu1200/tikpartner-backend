import stripe
from django.conf import settings
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import send_mail
from .models import Payment, Deliverable
from .services.escrow_service import EscrowService
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

# this Automatically releases escrow payments when all deliverables are approved, both updating the database status and triggering the actual Stripe transfer.
"""
@receiver(post_save, sender=Deliverable) # receiver is a signal decorator  # it listens for when a Deliverable(model class) object is saved or updated (post_save)  # so Deliverable is the one that triggers the signal(sender) 
def auto_release_payment_on_deliverable_approval(sender, instance, created, **kwargs):   # 'instance' refers to the actual Deliverable object that was saved or updated.   # 'sender' Refers to the model class (Deliverable) that triggered the signal
    # created refers to a boolean value indicating whether the Deliverable object was created (True) or updated (False).

    if not created and instance.status == 'approved':
        # Get all deliverables related to the current deliverable's contract
        contract = instance.contract
        deliverables = Deliverable.objects.filter(contract=contract)
        
        # Check if all deliverables are approved
        all_approved = all(d.status == 'approved' for d in deliverables)
        
        if all_approved:  # if all the deliverables of the given contract are approved

            payment = Payment.objects.get(contract=contract)  # retrieve the payment for the contract
            
            if payment.status != 'in_escrow':
                raise ValueError(f"Payment must be in 'in_escrow' status to be released. Current status: {payment.status}")

            # Get the influencer's Stripe account ID
            influencer_stripe_account = payment.contract.influencer.stripe_account_id
            if not influencer_stripe_account:
                raise ValueError("Influencer does not have a connected Stripe account")
            
            # Convert to cents for Stripe
            amount_cents = int(payment.amount * 100)
            
            # Calculate platform fee 
            platform_fee = int(payment.amount * 0.05 * 100)  # 5% platform fee. for eg, if the payment amount is 30$ then platform fee is 2.7$
            transfer_amount = amount_cents - platform_fee    #would be 27.3$
            
            # Execute the actual Stripe transfer
            try:
                transfer = stripe.Transfer.create(
                    amount=transfer_amount,  
                    currency="usd",
                    destination=influencer_stripe_account,
                    source_transaction=payment.transaction_id,   # payment.transaction_id is the PaymentIntent ID
                    metadata={
                        'payment_id': payment.id,
                        'contract_id': payment.contract.id,
                        'transfer_type': 'escrow_release'
                    }
                )
                
                # Update payment status and add transfer details in the db
                payment = EscrowService.release_payment(payment_id)
                payment.transfer_id = transfer.id
                payment.transfer_amount = transfer_amount / 100  # Convert back to dollars
                payment.platform_fee = platform_fee / 100  # Convert back to dollars
                payment.transfer_date = timezone.now()
                payment.save()

            except stripe.error.StripeError as e:
                 print(f"Stripe error occurred: {str(e)}")

"""

########

_old_status = {}        # this dictionary contains multiple instance.pk to payment status(key-value pairs) for different payment instances


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
            message=f"Hello {influencer.user.first_name},\n\nGreat news! A payment of net amount: ${net_amount} (cutting 5% platform fee) for contract #{contract.title} with {brand.user.first_name} has been released to your account.\n\nThank you for using our platform!",
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
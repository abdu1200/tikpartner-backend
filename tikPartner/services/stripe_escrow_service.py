import stripe
from django.conf import settings
from django.utils import timezone
from ..models import Payment
from .escrow_service import EscrowService

stripe.api_key = settings.STRIPE_SECRET_KEY   #this connects our app/platform to our platform's Stripe account. and then our platform/app can interact with our platform's Stripe using 'stripe' package

class StripeEscrowService:

    #This class handles the actual money movement with Stripe’s API, while coordinating with the EscrowService to update payment statuses in your database.
    
    @staticmethod
    def create_payment_intent(payment_id):
        
        payment = Payment.objects.get(id=payment_id)   #retrieve payment instance from db
        
        # Convert to cents for Stripe
        amount_cents = int(payment.amount * 100)
        
        # Create/generate a payment intent in Stripe(in our platform's stripe account or in our stripe)
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,      #tells Stripe how much to charge the brand
            currency='usd',           #in what currency
            metadata={                #extra infos to help you track or link this payment inside your system
                'payment_id': payment.id,
                'contract_id': payment.contract.id,
                'type': 'escrow'
            }
        )
        
        return {
            'client_secret': intent.client_secret, #the client_secret is sent to the frontend to render the Stripe Checkout form. so client_secret is sent to the frontend to collect card/payment details. so now the Stripe Checkout form on the frontend is directly connected to a PaymentIntent. and so that form uses the client_secret to complete the payment through the PaymentIntent.
            'payment_intent_id': intent.id         #the payment_intent_id is sent to the frontend so it can access details/infos about the PaymentIntent, including metadata, if needed.
                                                   #payment_intent_id helps the frontend confirm the payment's success. and on a successful payment, the frontend can make a request to the backend to save the payment details in the database or do anything in the db
        }
    
    @staticmethod
    def confirm_payment_to_escrow(payment_id, payment_intent_id):
        #Checks if the payment on Stripe succeeded, then moves funds into escrow(status in the db)

        payment = Payment.objects.get(id=payment_id)  
        
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)   #Retrieves the PaymentIntent from Stripe using payment_intent_id
        
        #verify if the payment succeeded
        if intent.status == 'succeeded':
            # Use the EscrowService to update the payment status in the db
            payment = EscrowService.deposit_to_escrow(
                payment_id,
                payment_method='stripe',
                transaction_id=payment_intent_id
            )
            return payment
        else:
            raise ValueError(f"Payment not successful. Status: {intent.status}")
    


    @staticmethod
    def transfer_to_influencer(payment_id):
        #this method releases funds from escrow(to the influencer), it transfers an actual money(fund) from the platform's stripe account to the influencer's stripe account using Stripe's transfer API while deducting a platform fee

        payment = Payment.objects.get(id=payment_id)
        
        # First check if payment can be released
        EscrowService.can_release_payment(payment_id)
        
        # Get the influencer's Stripe account ID
        influencer_stripe_account = payment.contract.influencer.stripe_account_id
        if not influencer_stripe_account:
            raise ValueError("Influencer does not have a connected Stripe account")
        
        # Convert to cents for Stripe
        amount_cents = int(payment.amount * 100)
        
        # Calculate platform fee 
        platform_fee = int(payment.amount * 0.05 * 100)  # 5% platform fee. for eg, if the payment amount is 30$ then platform fee is 2.7$
        transfer_amount = amount_cents - platform_fee    #would be 27.3$
        
        # Creates & processes the transfer request to the influencer's connected account
        transfer = stripe.Transfer.create(     #When stripe.Transfer.create() is called, it both creates the transfer record and actually moves the money to the influencer’s connected Stripe account in real-time.
            amount=transfer_amount,
            currency="usd",
            destination=influencer_stripe_account,
            source_transaction=payment.transaction_id,  # payment.transaction_id is the PaymentIntent ID, w/h refers to the original payment that deposited money into the platform’s Stripe account. #this links the source payment to this transfer. 
            metadata={
                'payment_id': payment.id,
                'contract_id': payment.contract.id,
                'transfer_type': 'escrow_release'
            }
        )

        # line 86: It links the brand's payment (to the platform's Stripe account) with the transfer (from the platform’s Stripe account to the influencer's connected account).
        # Line 86: It creates a clear relationship between the original deposit and the payout to the influencer.
        
        # Update payment status and add transfer details in the db
        payment = EscrowService.release_payment(payment_id)
        payment.transfer_id = transfer.id
        payment.transfer_amount = transfer_amount / 100  # Convert back to dollars
        payment.platform_fee = platform_fee / 100  # Convert back to dollars
        payment.transfer_date = timezone.now()
        payment.save()
        
        return payment


    
    @staticmethod
    def refund_payment(payment_id):
        # this method refunds the money from your platform's Stripe account (escrow) directly back to the brand’s original payment method (e.g., card) using stripe's refund API.
        # Stripe handles returning it to the exact source used during the initial payment.

        payment = Payment.objects.get(id=payment_id)
        
        if payment.status != 'in_escrow':
            raise ValueError(f"Payment must be in 'in_escrow' status to be refunded. Current status: {payment.status}")
        
        # Verify transaction_id exists   # payment.transaction_id is the PaymentIntent ID, w/h refers to the original payment that deposited money into the platform’s Stripe account(from the brand). 
        if not payment.transaction_id:
            raise ValueError("Cannot refund payment without transaction ID")
        
        # Create the refund in Stripe
        stripe.Refund.create(   # this creates a refund request(& refund record) in Stripe and processes the refund request, which sends the money back to the original payer’s card or payment method.
            payment_intent=payment.transaction_id
        )
        
        # Update payment status in the db using EscrowService
        return EscrowService.refund_payment(payment_id)
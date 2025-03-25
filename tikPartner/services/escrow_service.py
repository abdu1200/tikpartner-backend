# services/escrow_service.py
from django.utils import timezone
from django.db import transaction
from ..models import Payment, Deliverable

class EscrowService:
    
    #This is a plain Service class w/h is responsible for handling escrow operations like Depositing funds into escrow, Releasing funds from escrow(to the recipient), Refunding funds from escrow(to the sender), Providing escrow status summaries
    
    @staticmethod        
    @transaction.atomic
    def deposit_to_escrow(payment_id, payment_method=None, transaction_id=None):
        
        payment = Payment.objects.select_for_update().get(id=payment_id)  #This locks the payment row/instance in the db using select_for_update() to prevent race conditions b/n transactions
        
        if payment.status != 'pending':
            raise ValueError(f"Payment must be in 'pending' status to deposit to escrow. Current status: {payment.status}")
        
        payment.status = 'in_escrow'
        payment.payment_method = payment_method or 'credit_card'
        payment.transaction_id = transaction_id or f'txn-{timezone.now().timestamp()}'    #Generates fallback transaction_id if 'None' is provided
        payment.updated_at = timezone.now()
        payment.save()
        
        return payment



    @staticmethod
    def can_release_payment(payment_id):
        
        payment = Payment.objects.get(id=payment_id)
        
        if payment.status != 'in_escrow':
            raise ValueError(f"Payment must be in 'in_escrow' status to be released. Current status: {payment.status}")
        
        # Add extra validation: Check if all deliverables are approved
        deliverables = Deliverable.objects.filter(contract=payment.contract)
        if deliverables.exists() and not all(d.status == 'approved' for d in deliverables):
            raise ValueError("Cannot release payment - not all deliverables have been approved")
        
        return True
    
    
    @staticmethod
    @transaction.atomic
    def release_payment(payment_id):   
       
        payment = Payment.objects.select_for_update().get(id=payment_id)
        
        # First verify that payment can be released
        EscrowService.can_release_payment(payment_id)
        
        payment.status = 'released'
        payment.updated_at = timezone.now()
        payment.save()
        
        return payment

    
    @staticmethod
    @transaction.atomic
    def refund_payment(payment_id):
    
        payment = Payment.objects.select_for_update().get(id=payment_id)
        
        if payment.status != 'in_escrow':
            raise ValueError(f"Payment must be in 'in_escrow' status to be refunded. Current status: {payment.status}")
        
        payment.status = 'refunded'
        payment.updated_at = timezone.now()
        payment.save()
        
        return payment


    """
    ## this is to be used for when a contract has multiple payments. 

    @staticmethod
    def get_escrow_summary(contract_id):
        #Gives a summary of how much money(amount) is in escrow, released, refunded, or pending for a specific contract.

        payments = Payment.objects.filter(contract_id=contract_id)     #Fetches all payments linked to a given contract_id
        
        total = sum(payment.amount for payment in payments)             #Sum of all payment amounts
        in_escrow = sum(payment.amount for payment in payments if payment.status == 'in_escrow')
        released = sum(payment.amount for payment in payments if payment.status == 'released')
        refunded = sum(payment.amount for payment in payments if payment.status == 'refunded')
        pending = sum(payment.amount for payment in payments if payment.status == 'pending')
        
        return {
            'total': total,
            'in_escrow': in_escrow,
            'released': released,
            'refunded': refunded,
            'pending': pending,
            'contract_id': contract_id
        }
    """
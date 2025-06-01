"""
Payment service utility for Stripe integration.
"""
import os
import stripe
from flask import current_app

# Set Stripe API key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def create_checkout_session(user_email, success_url, cancel_url):
    """
    Create a Stripe checkout session for subscription payment.
    
    Args:
        user_email (str): User's email for the checkout session
        success_url (str): URL to redirect to after successful payment
        cancel_url (str): URL to redirect to if payment is cancelled
        
    Returns:
        str: Checkout session ID or None on error
    """
    try:
        # Create a checkout session for the subscription
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=user_email,
            line_items=[{
                'price': os.environ.get('STRIPE_PRICE_ID'),  # Your monthly subscription price ID
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=cancel_url,
        )
        return checkout_session.id
    except Exception as e:
        current_app.logger.error(f"Error creating checkout session: {e}")
        return None

def get_subscription_status(subscription_id):
    """
    Get the status of a subscription.
    
    Args:
        subscription_id (str): Stripe subscription ID
        
    Returns:
        dict: Subscription status information
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return {
            'status': subscription.status,
            'current_period_end': subscription.current_period_end,
            'cancel_at_period_end': subscription.cancel_at_period_end
        }
    except Exception as e:
        current_app.logger.error(f"Error getting subscription status: {e}")
        return None

def cancel_subscription(subscription_id):
    """
    Cancel a subscription.
    
    Args:
        subscription_id (str): Stripe subscription ID
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        stripe.Subscription.delete(subscription_id)
        return True
    except Exception as e:
        current_app.logger.error(f"Error cancelling subscription: {e}")
        return False

def handle_webhook_event(payload, sig_header):
    """
    Handle Stripe webhook events.
    
    Args:
        payload (bytes): Request payload
        sig_header (str): Stripe signature header
        
    Returns:
        dict: Event data or None on error
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET')
        )
        
        # Handle the event based on its type
        if event['type'] == 'checkout.session.completed':
            # Payment was successful, activate the subscription
            session = event['data']['object']
            customer_email = session.get('customer_email')
            subscription_id = session.get('subscription')
            
            # Update user subscription status in your database
            # This is just a placeholder - implement based on your database structure
            return {
                'success': True,
                'type': 'subscription_created',
                'customer_email': customer_email,
                'subscription_id': subscription_id
            }
            
        elif event['type'] == 'customer.subscription.updated':
            # Subscription was updated
            subscription = event['data']['object']
            return {
                'success': True,
                'type': 'subscription_updated',
                'subscription_id': subscription.id,
                'status': subscription.status
            }
            
        elif event['type'] == 'customer.subscription.deleted':
            # Subscription was cancelled
            subscription = event['data']['object']
            return {
                'success': True,
                'type': 'subscription_cancelled',
                'subscription_id': subscription.id
            }
            
        # Return the event for other event types
        return {
            'success': True,
            'type': event['type'],
            'event': event
        }
    except Exception as e:
        current_app.logger.error(f"Error handling webhook: {e}")
        return {'success': False, 'error': str(e)}
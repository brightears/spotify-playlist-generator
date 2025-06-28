"""Skeleton Stripe billing blueprint – to be fleshed out later."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user

from .. import db
from ..models import User
import os
from datetime import datetime, timedelta
import traceback

import stripe

billing_bp = Blueprint('billing', __name__, template_folder='templates')

# Initialize Stripe with our secret key (from environment variables)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

@billing_bp.route('/subscription')
@login_required
def subscription():
    """Render the subscription page."""
    return render_template(
        'billing/subscription.html',
        current_user=current_user,
        stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
        monthly_price_id=os.environ.get('STRIPE_MONTHLY_PRICE_ID', ''),
        yearly_price_id=os.environ.get('STRIPE_YEARLY_PRICE_ID', ''),
    )


@billing_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe checkout session for subscription payment."""
    try:
        # Ensure Stripe API key is set
        stripe_secret_key = os.environ.get('STRIPE_SECRET_KEY', '')
        if not stripe_secret_key:
            current_app.logger.error("Stripe API key not configured")
            return jsonify(error="Payment system not configured"), 500
            
        stripe.api_key = stripe_secret_key
            
        plan_type = request.json.get('plan_type', 'monthly')  # monthly or yearly
        
        # Get the appropriate price ID
        if plan_type == 'yearly':
            price_id = os.environ.get('STRIPE_YEARLY_PRICE_ID', '')
        else:
            price_id = os.environ.get('STRIPE_MONTHLY_PRICE_ID', '')
        
        if not price_id:
            current_app.logger.error(f"Missing Stripe {plan_type} price ID")
            return jsonify(error=f"Configuration error: Missing Stripe {plan_type} price ID"), 500
        
        current_app.logger.info(f"Creating checkout session for {plan_type} plan with price ID: {price_id}")
        
        # Create a new customer or get existing one
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': str(current_user.id)},
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()
            current_app.logger.info(f"Created new Stripe customer: {customer.id}")
            customer_id = customer.id
        else:
            customer_id = current_user.stripe_customer_id
            current_app.logger.info(f"Using existing Stripe customer: {customer_id}")

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('billing.success', _external=True) + f'?plan={plan_type}',
            cancel_url=url_for('billing.subscription', _external=True),
            metadata={'plan_type': plan_type},
        )
        current_app.logger.info(f"Created checkout session: {checkout_session.id}")
        return jsonify(id=checkout_session.id)
        
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return jsonify(error=f"Payment error: {str(e)}"), 500
    except Exception as e:
        current_app.logger.error(f"Unexpected error in create_checkout_session: {str(e)}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify(error="An unexpected error occurred. Please try again."), 500


@billing_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """Cancel the user's active Stripe subscription."""
    # Check if user is a test user with hardcoded access
    if current_user.email in ['norli@gmail.com', 'platzer.norbert@gmail.com']:
        flash('Test account subscription cannot be cancelled. Please contact support.', 'info')
        return redirect(url_for('billing.subscription'))
    
    if not current_user.subscription_id:
        flash('No active subscription found.', 'warning')
        return redirect(url_for('billing.subscription'))

    try:
        stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=True,
        )
        
        # Update local user record
        current_user.subscription_status = 'canceled'
        db.session.commit()
        
        # No flash message - the subscription page will show the cancellation confirmation
    except Exception as e:
        flash(f'Failed to cancel subscription: {e}', 'danger')

    return redirect(url_for('billing.subscription'))


@billing_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks to keep subscription status in sync."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        current_app.logger.error('Missing Stripe webhook secret')
        return jsonify(success=False), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        return jsonify(success=False, error='Invalid signature'), 400
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

    # Handle specific events
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_completed(session)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)

    return jsonify(success=True)


@billing_bp.route('/success')
@login_required
def success():
    """Handle successful subscription."""
    plan_type = request.args.get('plan', 'monthly')
    
    # Try to retrieve the subscription immediately if we have a customer ID
    if current_user.stripe_customer_id:
        try:
            # Get the customer's subscriptions
            subscriptions = stripe.Subscription.list(
                customer=current_user.stripe_customer_id,
                limit=1
            )
            
            if subscriptions.data:
                subscription = subscriptions.data[0]
                # Update user's subscription info immediately
                current_user.subscription_id = subscription.id
                current_user.subscription_status = subscription.status
                current_user.subscription_plan = plan_type
                
                if subscription.current_period_end:
                    current_user.subscription_current_period_end = datetime.fromtimestamp(
                        subscription.current_period_end
                    )
                
                db.session.commit()
                current_app.logger.info(f"Updated subscription for user {current_user.id} immediately after checkout")
        except Exception as e:
            # Log the error but don't block the redirect
            current_app.logger.error(f"Error retrieving subscription after checkout: {e}")
    
    # No flash message needed - dashboard will show active subscription status
    return redirect(url_for('main.dashboard'))


# Webhook handlers
def handle_checkout_completed(session):
    """Handle checkout.session.completed webhook event."""
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    plan_type = session.get('metadata', {}).get('plan_type', 'monthly')
    
    if not customer_id or not subscription_id:
        return
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    user.subscription_id = subscription_id
    user.subscription_status = 'active'
    user.subscription_plan = plan_type
    
    # Get subscription details to set end date
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        if subscription and subscription.current_period_end:
            end_date = datetime.fromtimestamp(subscription.current_period_end)
            user.subscription_current_period_end = end_date
    except Exception as e:
        current_app.logger.error(f'Error retrieving subscription: {e}')
    
    db.session.commit()


def handle_subscription_updated(subscription):
    """Handle customer.subscription.updated webhook event."""
    customer_id = subscription.get('customer')
    status = subscription.get('status')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    if status == 'active':
        user.subscription_status = 'active'
    elif status == 'canceled' or status == 'unpaid':
        user.subscription_status = 'canceled'
    
    # Update subscription end date
    if subscription.get('current_period_end'):
        end_date = datetime.fromtimestamp(subscription.current_period_end)
        user.subscription_current_period_end = end_date
    
    db.session.commit()


def handle_subscription_deleted(subscription):
    """Handle customer.subscription.deleted webhook event."""
    customer_id = subscription.get('customer')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    user.subscription_status = 'canceled'
    db.session.commit()

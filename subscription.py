"""Subscription management and Stripe integration for the app."""

import os
import stripe
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user

from models import db, User

subscription_bp = Blueprint('subscription', __name__, template_folder='templates')

# Initialize Stripe with the API key
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_your_test_key')

@subscription_bp.route('/subscription')
@login_required
def subscription():
    """Show subscription management page."""
    publishable_key = os.environ.get('STRIPE_PUBLISHABLE_KEY', 'pk_test_your_test_key')
    price_id = os.environ.get('STRIPE_PRICE_ID', 'price_test_id')
    return render_template(
        'subscription.html',
        publishable_key=publishable_key,
        price_id=price_id,
        user=current_user
    )

@subscription_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe checkout session for subscription payment."""
    price_id = os.environ.get('STRIPE_PRICE_ID')
    if not price_id:
        flash('Subscription system is not properly configured.', 'danger')
        return redirect(url_for('subscription.subscription'))

    # Create a customer if the user doesn't have one
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={'user_id': current_user.id}
        )
        current_user.stripe_customer_id = customer.id
        db.session.commit()
    
    # Create the checkout session
    try:
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription.success', _external=True),
            cancel_url=url_for('subscription.subscription', _external=True),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        flash(f'Error creating checkout session: {str(e)}', 'danger')
        return redirect(url_for('subscription.subscription'))

@subscription_bp.route('/webhook', methods=['POST'])
def webhook():
    """Handle Stripe webhook events for subscription management."""
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Verify webhook signature
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return jsonify({'error': str(e)}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return jsonify({'error': str(e)}), 400
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)
    
    return jsonify({'status': 'success'})

def handle_checkout_session(session):
    """Process a completed checkout session."""
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    
    if customer_id and subscription_id:
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            # Get subscription details from Stripe
            subscription = stripe.Subscription.retrieve(subscription_id)
            current_period_end = datetime.fromtimestamp(subscription.current_period_end)
            
            user.stripe_subscription_id = subscription_id
            user.subscription_status = 'active'
            user.subscription_end_date = current_period_end
            db.session.commit()

def handle_subscription_updated(subscription):
    """Process a subscription update event."""
    customer_id = subscription.get('customer')
    subscription_id = subscription.get('id')
    status = subscription.get('status')
    current_period_end = datetime.fromtimestamp(subscription.get('current_period_end', 0))
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        user.stripe_subscription_id = subscription_id
        user.subscription_status = status
        user.subscription_end_date = current_period_end
        db.session.commit()

def handle_subscription_deleted(subscription):
    """Process a subscription deletion event."""
    customer_id = subscription.get('customer')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        user.subscription_status = 'canceled'
        db.session.commit()

@subscription_bp.route('/success')
@login_required
def success():
    """Handle successful subscription payment."""
    flash('Thank you for subscribing!', 'success')
    return redirect(url_for('dashboard'))

@subscription_bp.route('/cancel', methods=['POST'])
@login_required
def cancel():
    """Cancel the user's subscription."""
    if current_user.stripe_subscription_id:
        try:
            stripe.Subscription.modify(
                current_user.stripe_subscription_id,
                cancel_at_period_end=True
            )
            flash('Your subscription will be canceled at the end of the billing period.', 'info')
        except Exception as e:
            flash(f'Error canceling subscription: {str(e)}', 'danger')
    else:
        flash('You do not have an active subscription to cancel.', 'warning')
    
    return redirect(url_for('subscription.subscription'))

# <!-- explainer: This subscription blueprint provides integration with Stripe for handling premium subscriptions. It includes routes for displaying subscription info, creating checkout sessions, processing webhooks, and managing subscription status changes. -->
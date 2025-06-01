"""Subscription management blueprint for the Spotify Playlist Generator app."""

import os
from datetime import datetime, timedelta

import stripe
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, User

subscription_bp = Blueprint('subscription', __name__, template_folder='templates')

# Initialize Stripe with our secret key (from environment variables)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


@subscription_bp.route('/subscription')
@login_required
def subscription():
    """Render the subscription page."""
    return render_template(
        'subscription.html',
        price="3",
        period="mo",
        stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    )


@subscription_bp.route('/stripe/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create a Stripe checkout session for subscription payment."""
    # Create a new customer or get existing one
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={'user_id': current_user.id},
        )
        current_user.stripe_customer_id = customer.id
        db.session.commit()
    else:
        customer = stripe.Customer.retrieve(current_user.stripe_customer_id)

    # Create the checkout session
    price_id = os.environ.get('STRIPE_PRICE_ID', '')
    if not price_id:
        return jsonify(error="Configuration error: Missing Stripe price ID"), 500

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription.success', _external=True),
            cancel_url=url_for('subscription.subscription', _external=True),
        )
        return jsonify(id=checkout_session.id)
    except Exception as e:
        return jsonify(error=str(e)), 500


@subscription_bp.route('/subscription/cancel', methods=['POST'])
@login_required
def cancel():
    """Cancel the user's active Stripe subscription."""
    if not current_user.stripe_subscription_id:
        flash('No active subscription found.', 'warning')
        return redirect(url_for('subscription.subscription'))

    try:
        stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        
        # Update local user record
        current_user.subscription_status = 'canceled'
        db.session.commit()
        
        flash('Your subscription has been canceled. You will have access until the end of the current billing period.', 'success')
    except Exception as e:
        flash(f'Failed to cancel subscription: {e}', 'danger')

    return redirect(url_for('subscription.subscription'))


@subscription_bp.route('/stripe/webhook', methods=['POST'])

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


@subscription_bp.route('/subscription/success')
@login_required
def success():
    """Handle successful subscription."""
    flash('Subscription successful! Thank you for subscribing.', 'success')
    return redirect(url_for('dashboard'))


# Webhook handlers
def handle_checkout_completed(session):
    """Handle checkout.session.completed webhook event."""
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    
    if not customer_id or not subscription_id:
        return
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    user.stripe_subscription_id = subscription_id
    user.subscription_status = 'active'
    
    # Get subscription details to set end date
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        if subscription and subscription.current_period_end:
            end_date = datetime.fromtimestamp(subscription.current_period_end)
            user.subscription_end_date = end_date
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
        user.subscription_end_date = end_date
    
    db.session.commit()


def handle_subscription_deleted(subscription):
    """Handle customer.subscription.deleted webhook event."""
    customer_id = subscription.get('customer')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return
    
    user.subscription_status = 'canceled'
    db.session.commit()

# explainer: Created a subscription blueprint to handle user subscriptions, payment processing with Stripe, and webhook handling for subscription events. -->
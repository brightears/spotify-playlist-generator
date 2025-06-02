"""Skeleton Stripe billing blueprint – to be fleshed out later."""
from flask import Blueprint, current_app, redirect, url_for
import stripe

from .. import db
from ..models import User

billing_bp = Blueprint("billing", __name__)

@billing_bp.before_app_first_request
def _init_stripe():
    stripe.api_key = current_app.config.get("STRIPE_API_KEY")

@billing_bp.route("/subscribe")
def subscribe():
    # TODO: Implement Stripe Checkout session creation
    return "Stripe Subscribe placeholder", 200

@billing_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    # TODO: Verify signature & handle events
    return "Webhook placeholder", 200

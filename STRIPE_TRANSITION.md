# Stripe Live Mode Transition Checklist

## Current Status (January 5, 2025)
- ✅ All UI/UX improvements complete  
- ✅ Platform is production-ready
- ❌ Stripe still in test/sandbox mode

## Steps to Complete

### 1. Stripe Dashboard Setup
- [ ] Log into Stripe dashboard (live mode)
- [ ] Create Pro Monthly product ($3/month)
- [ ] Create Pro Yearly product ($24/year)
- [ ] Note the new price IDs

### 2. Environment Variables to Update
```env
# Replace these test keys with live keys
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_MONTHLY_PRICE_ID=price_...
STRIPE_YEARLY_PRICE_ID=price_...
```

### 3. Render.com Updates
- [ ] Update all Stripe environment variables in Render dashboard
- [ ] Trigger manual deploy or push commit to redeploy

### 4. Webhook Configuration
- [ ] Add webhook endpoint in Stripe: https://brightears.io/stripe/webhook
- [ ] Configure webhook to send these events:
  - checkout.session.completed
  - customer.subscription.created
  - customer.subscription.updated
  - customer.subscription.deleted
  - invoice.payment_succeeded
  - invoice.payment_failed

### 5. Testing
- [ ] Test monthly subscription purchase
- [ ] Test yearly subscription purchase
- [ ] Test subscription cancellation
- [ ] Verify webhook handling
- [ ] Check subscription status updates

### 6. Test User Cleanup
- [ ] Remove hardcoded Pro access for:
  - norli@gmail.com
  - platzer.norbert@gmail.com
- [ ] These are in `src/flasksaas/models.py` User.has_active_subscription property

### 7. Final Verification
- [ ] Ensure payments are processing correctly
- [ ] Check Stripe dashboard for successful transactions
- [ ] Verify user subscription statuses update properly
- [ ] Confirm Pro features unlock after payment

## Notes
- Current test products work perfectly, just need live mode equivalents
- All subscription logic is already implemented and tested
- No code changes needed, only environment variable updates
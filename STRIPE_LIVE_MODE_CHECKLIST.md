# Stripe Live Mode Activation Checklist

## Prerequisites
- [ ] Stripe account activated and verified
- [ ] Bank account connected for payouts
- [ ] Business details completed in Stripe dashboard

## Step 1: Create Products in Live Mode

1. Go to https://dashboard.stripe.com/ and switch to **Live mode** (toggle in top right)

2. Create the Pro subscription product:
   - Navigate to Products → Add product
   - Name: "Bright Ears Pro"
   - Description: "Unlimited custom sources, all export formats, and playlist history"

3. Add pricing:
   - **Monthly**: $3.00 USD, recurring monthly
   - **Yearly**: $24.00 USD, recurring yearly (save 33%)

4. Copy the price IDs:
   - Monthly price ID: `price_XXXXXXXXXXXXXXXX`
   - Yearly price ID: `price_YYYYYYYYYYYYYYYY`

## Step 2: Get Live API Keys

1. In Stripe dashboard (Live mode), go to Developers → API keys
2. Copy these keys:
   - Publishable key: `pk_live_XXXXXXXXXXXXXXXX`
   - Secret key: `sk_live_XXXXXXXXXXXXXXXX` (reveal and copy)

3. Go to Developers → Webhooks
4. Click on your webhook endpoint
5. Copy the signing secret: `whsec_XXXXXXXXXXXXXXXX`

## Step 3: Update Render Environment Variables

1. Go to https://dashboard.render.com/
2. Select your Bright Ears service
3. Go to Environment tab
4. Update these variables:

```
STRIPE_PUBLISHABLE_KEY=pk_live_XXXXXXXXXXXXXXXX
STRIPE_SECRET_KEY=sk_live_XXXXXXXXXXXXXXXX
STRIPE_WEBHOOK_SECRET=whsec_XXXXXXXXXXXXXXXX
STRIPE_MONTHLY_PRICE_ID=price_XXXXXXXXXXXXXXXX
STRIPE_YEARLY_PRICE_ID=price_YYYYYYYYYYYYYYYY
```

5. Save changes (this will trigger a redeploy)

## Step 4: Remove Test User Hardcoding

After confirming live mode works:

1. Edit `src/flasksaas/models.py`
2. Remove or comment out the hardcoded test user Pro access:
   ```python
   # Remove this block:
   if self.email.lower() in ['norli@gmail.com', 'platzer.norbert@gmail.com']:
       return True
   ```

## Step 5: Test Live Payment Flow

1. Visit https://brightears.io in an incognito window
2. Sign up with a new account
3. Click "Upgrade to Pro"
4. Use a real credit card to test:
   - Monthly subscription
   - Yearly subscription
   - Cancellation flow

## Step 6: Verify Webhook Events

1. In Stripe dashboard, go to Developers → Webhooks
2. Check that these events are being received:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

## Post-Launch Monitoring

- [ ] Monitor Stripe dashboard for successful payments
- [ ] Check Render logs for any payment errors
- [ ] Verify users are getting Pro features after payment
- [ ] Test cancellation flow works correctly
- [ ] Ensure webhook events are processing

## Rollback Plan

If issues arise:
1. Switch back to test keys in Render
2. Refund any live transactions
3. Debug the issue
4. Try again

## Important Notes

- Stripe test keys start with `sk_test_` and `pk_test_`
- Stripe live keys start with `sk_live_` and `pk_live_`
- Always use live mode webhook secrets for live mode
- Keep test mode active for development
- Never commit live keys to git
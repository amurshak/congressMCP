# Setting Up Live Environment Variables

## Backend Environment Variables

Add these to your `.env` file in the backend directory:

```bash
# Stripe Live Configuration
STRIPE_PRO_MONTHLY_PRICE_ID=price_1RVXcoCrAoNgWc5ERnPyOTTG
STRIPE_PRO_ANNUAL_PRICE_ID=price_1RVXdnCrAoNgWc5EJSOposRL

# Make sure you also have your live Stripe keys:
STRIPE_SECRET_KEY=sk_live_your_live_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_live_webhook_secret_here
```

## Summary

✅ **Live Product Created:**
- Product ID: `prod_SQOPNNGRopjq65`
- Monthly Price: `price_1RVXcoCrAoNgWc5ERnPyOTTG` ($29/month)
- Annual Price: `price_1RVXdnCrAoNgWc5EJSOposRL` ($299/year)

✅ **Live Payment Links:**
- Monthly: `https://buy.stripe.com/dRm28q8nV9ou7Or2Plawo01`
- Annual: `https://buy.stripe.com/6oU6oG5bJeIOgkX4Xtawo00`

✅ **Frontend Environment:**
- Production environment already updated with live payment links

✅ **Backend Environment:**
- Price IDs now configured as environment variables
- More maintainable and flexible configuration

## Next Steps

1. Add the price ID environment variables to your backend `.env` file
2. Set up live Stripe webhook endpoint in Stripe Dashboard
3. Deploy to production and test live payments

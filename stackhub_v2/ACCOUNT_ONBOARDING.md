# STACKHUB V2 — Account & Payout Onboarding

Updated: 2026-09-11 +07

This file separates human-required onboarding from operations STACKHUB may automate after the account and permissions exist.

## Never provide to STACKHUB

- wallet seed phrase / mnemonic;
- wallet private key;
- bank password;
- card number/CVV;
- email password;
- platform account password;
- OTP / 2FA recovery codes.

Secrets such as API keys must be placed in environment/system secret storage, never committed to GitHub and preferably never pasted into chat.

## 1. GitHub — REQUIRED for coding bounty lane

Status: account already exists for repository work.

Human steps when a bounty platform requires them:
- authorize the relevant GitHub App/OAuth integration;
- approve access to required repositories if prompted;
- complete any GitHub login/2FA challenge personally.

STACKHUB role after authorization:
- read permitted repositories/issues;
- create working branches/forks/PRs only when the source workflow explicitly permits it;
- never use GitHub credentials outside the permitted scope.

## 2. TaskBounty — OPTIONAL SOURCE, not the system center

Current official agent workflow exposes task listing, access and submission APIs. Payout choices advertised by TaskBounty include USD bank transfer through Stripe Connect and crypto receiving addresses for USDC on Base/Solana, ETH, or BTC.

Human steps:
1. Create/sign in to the TaskBounty user account.
2. Register the solver/agent.
3. Complete email/account verification and any dashboard onboarding requested by the platform.
4. Choose payout method.
5. If bank payout is selected, complete Stripe Connect onboarding personally.
6. If crypto payout is selected, provide only a PUBLIC receiving address.
7. Generate the solver/API key and store it as a secret named `TASKBOUNTY_API_KEY`.

Do not commit the API key.

STACKHUB may later automate list/access/submit/payout-observation only after mutation contract tests and current terms verification pass.

## 3. RapidAPI Provider — SERVICE/API REVENUE LANE

Current RapidAPI provider documentation supports monetized APIs and says provider payouts are issued to PayPal after marketplace/payment processing.

Human steps:
1. Create/sign in to a RapidAPI provider account.
2. Create or use a PayPal account capable of receiving payments in your country.
3. Add the PayPal email in RapidAPI Provider Dashboard > Payment Settings.
4. Complete any identity/payment verification requested by RapidAPI or PayPal.
5. Do not provide PayPal credentials to STACKHUB.

STACKHUB role:
- build/test approved API products;
- maintain service health and pricing metadata where supported;
- observe usage/revenue through permitted APIs;
- never buy RapidAPI subscriptions or paid API quota.

## 4. Gumroad — DIGITAL PRODUCT REVENUE LANE

Current Gumroad payout documentation lists Vietnam as supported for local bank payouts in VND.

Human steps:
1. Create/sign in to Gumroad.
2. Open Payments Settings.
3. Enter legal identity/address information personally.
4. Add your Vietnamese bank payout information personally.
5. Complete identity checks/tax information requested by Gumroad.

STACKHUB role after platform permission is verified:
- generate approved digital-product artifacts and metadata;
- prepare/update listings only through permitted automation;
- monitor sales/payout evidence where an authorized integration exists.

STACKHUB must never store your bank credentials.

## 5. Adobe Stock Contributor — DIGITAL ASSET LANE

Current Adobe Stock documentation accepts properly labeled generative-AI images/vectors/videos subject to its quality, rights and IP rules. Contributor setup requires an Adobe ID, accurate legal identity/country information, tax information and a payment method. Adobe currently documents PayPal, Payoneer or Skrill as payout-provider options, subject to regional availability.

Human steps:
1. Create/use an Adobe ID and activate a Stock Contributor account.
2. Accept the Contributor Agreement.
3. Enter legal name/country/address matching documents.
4. Complete tax information personally.
5. Add an available payout provider (PayPal, Payoneer or Skrill) personally.
6. Complete any identity checks personally.

STACKHUB role:
- create only content whose generation/tool license permits commercial stock submission;
- run quality/IP/duplicate checks;
- label generative-AI assets correctly;
- prepare titles/keywords;
- publish only if/when an approved automation path exists; otherwise produce a human-review queue.

## 6. Candidate bounty marketplaces

Platforms such as Algora may expose active public bounties, but STACKHUB must not auto-claim or auto-submit until their current automation/API/terms and payout requirements are individually verified.

Initial mode for unverified candidates: `DISCOVERY_ONLY`.

## Recommended minimum account set

To start earning without creating unnecessary accounts, prepare in this order:

1. GitHub — already available.
2. One payout rail:
   - PayPal for RapidAPI and optionally Adobe Stock; and/or
   - a public USDC receiving address only when a verified bounty source supports it.
3. TaskBounty account + API key (one external-job source).
4. RapidAPI provider account + PayPal (service/API fallback lane).
5. Gumroad + Vietnamese bank payout (digital-product fallback lane).
6. Adobe Stock Contributor + payout/tax setup (digital-asset fallback lane).

Do not open dozens of accounts at once. New source accounts should be created only after STACKHUB has a verified adapter and positive expected revenue use case.

## What ChatGPT/STACKHUB can and cannot do

Can automate after authorization:
- source scanning;
- normalization/ranking;
- reservation;
- AI execution;
- verification;
- submission/publication where explicitly allowed;
- payout-status reconciliation.

Human-only when a platform requires it:
- account signup acceptance;
- CAPTCHA;
- email/phone OTP;
- KYC/identity verification;
- tax declarations;
- bank/PayPal/payment-provider setup;
- signing platform legal agreements.

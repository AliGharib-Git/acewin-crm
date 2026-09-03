"""
BillingProvider: the seam a real payment gateway (Stripe, a local
Iranian gateway like ZarinPal, etc.) plugs into later without any
other part of the app -- routers, entitlement checks, the pricing page
-- needing to change. Nothing in this file talks to a real payment API
yet; see NullBillingProvider below.

This mirrors the AI provider abstraction pattern already used in
app/ai/client.py: one interface, swapped via configuration, never
hard-coded into business logic.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

from app.models import Organization, Subscription, SubscriptionPlan


@dataclass
class CheckoutSession:
    """What a provider hands back after starting a checkout -- a URL
    to redirect the admin to, and a reference id to reconcile the
    resulting webhook against."""

    checkout_url: str
    provider_reference: str


class BillingProviderError(Exception):
    """Raised by any BillingProvider method that can't complete --
    including, deliberately, by NullBillingProvider for every method,
    since 'no provider configured' is itself a real error a caller
    must handle, not a silent no-op."""


class BillingProvider(abc.ABC):
    """Everything a payment gateway integration must implement. Kept
    deliberately small: the actual plan/entitlement logic lives in
    app/billing/plans.py and app/billing/entitlements.py and does NOT
    depend on any of this -- a BillingProvider only needs to answer
    "start paying" / "stop paying", nothing about what paying unlocks.
    """

    @abc.abstractmethod
    def start_checkout(
        self, org: Organization, plan: SubscriptionPlan, billing_cycle: str, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        """Begin a new paid subscription (or plan change) for `org`.
        Must not mutate the Subscription row itself -- that only
        happens once the provider confirms payment (via webhook in a
        real integration, see docs in this module's docstring)."""

    @abc.abstractmethod
    def cancel_subscription(self, subscription: Subscription) -> None:
        """Cancel at the provider. The caller is responsible for
        updating the local Subscription row's status afterward."""


class NullBillingProvider(BillingProvider):
    """The only BillingProvider actually wired up right now.
    Deliberately refuses to pretend a checkout exists -- every method
    raises BillingProviderError with a clear, honest message, since
    fabricating a fake checkout URL or silently no-op'ing a cancel
    request would be worse than an explicit "not configured" error.

    Plan changes today happen the honest way instead: an org admin
    calls PATCH /api/billing/subscription directly (see
    routers/billing.py), no payment collected -- appropriate for a
    product that hasn't integrated a real payment gateway yet, and
    explicitly flagged as such in every response.
    """

    def start_checkout(self, org, plan, billing_cycle, success_url, cancel_url) -> CheckoutSession:  # noqa: D102
        raise BillingProviderError(
            "No payment provider is configured yet. Plan changes are handled by an "
            "organization admin directly (PATCH /api/billing/subscription) until a "
            "real payment gateway (e.g. Stripe or a local gateway) is integrated."
        )

    def cancel_subscription(self, subscription) -> None:  # noqa: D102
        raise BillingProviderError("No payment provider is configured yet; there is nothing to cancel at a gateway.")


def get_billing_provider() -> BillingProvider:
    """The one place that decides which BillingProvider implementation
    is active. A future PAYMENT_PROVIDER env var (mirroring AI_PROVIDER
    in app/ai/config.py) would branch here -- e.g.
    `if settings.payment_provider == "stripe": return StripeBillingProvider(...)`
    -- without any caller needing to change."""
    return NullBillingProvider()

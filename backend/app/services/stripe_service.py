"""
Stripe service for payment processing.
Handles checkout session creation and credit packages.
"""
import stripe
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class CreditPackage:
    """Represents a purchasable credit package."""
    id: str
    name: str
    credits: int
    price_cents: int  # Price in cents (e.g., 999 = $9.99)
    currency: str = "usd"
    description: Optional[str] = None
    popular: bool = False  # Mark as "most popular" in UI


# Available credit packages
CREDIT_PACKAGES: List[CreditPackage] = [
    CreditPackage(
        id="starter",
        name="Starter Pack",
        credits=10,
        price_cents=499,
        description="Perfect for trying out SecondBrain",
    ),
    CreditPackage(
        id="popular",
        name="Popular Pack",
        credits=50,
        price_cents=1999,
        description="Best value for regular users",
        popular=True,
    ),
    CreditPackage(
        id="pro",
        name="Pro Pack",
        credits=100,
        price_cents=3499,
        description="For power users",
    ),
    CreditPackage(
        id="enterprise",
        name="Enterprise Pack",
        credits=500,
        price_cents=14999,
        description="Maximum credits for heavy usage",
    ),
]


class StripeService:
    """Service for Stripe payment operations."""
    
    def __init__(self):
        """Initialize Stripe with API key."""
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            logger.info("Stripe initialized with secret key")
        else:
            logger.warning("Stripe secret key not configured")
    
    @staticmethod
    def get_packages() -> List[Dict[str, Any]]:
        """
        Get list of available credit packages from Stripe.
        
        Fetches active products and prices from Stripe and maps them
        to credit packages based on metadata.
        
        Returns:
            List of package dictionaries with pricing info
        """
        if not settings.stripe_secret_key:
            logger.warning("Stripe not configured, returning empty packages list")
            return []
        
        try:
            # Ensure Stripe API key is set
            if not stripe.api_key or stripe.api_key != settings.stripe_secret_key:
                stripe.api_key = settings.stripe_secret_key
            
            # Fetch active products with metadata
            products = stripe.Product.list(active=True, limit=100)
            logger.info(f"Found {len(products.data)} active products in Stripe")
            
            packages = []
            for product in products.data:
                metadata = product.metadata or {}
                
                # Try to get credits from metadata first
                credits = None
                if 'credits' in metadata:
                    try:
                        credits = int(metadata.get('credits', 0))
                    except (ValueError, TypeError):
                        credits = None
                
                # If no metadata credits, try to extract from product name
                if credits is None or credits == 0:
                    try:
                        # Try to parse product name as integer (e.g., "100", "50", "25", "10")
                        product_name_clean = product.name.strip()
                        credits = int(product_name_clean)
                        logger.info(f"Extracted credits from product name '{product.name}': {credits}")
                    except (ValueError, TypeError):
                        # If name is not a number, skip this product
                        logger.debug(f"Skipping product '{product.name}' - no credits metadata and name is not a number")
                        continue
                
                if credits <= 0:
                    logger.debug(f"Skipping product '{product.name}' - invalid credits value: {credits}")
                    continue
                
                # Get the default price for this product
                default_price_id = product.default_price
                if not default_price_id:
                    # Try to get the first active price
                    prices = stripe.Price.list(product=product.id, active=True, limit=1)
                    if not prices.data:
                        logger.debug(f"Skipping product '{product.name}' - no active prices")
                        continue
                    default_price_id = prices.data[0].id
                
                # Get price details
                price = stripe.Price.retrieve(default_price_id)
                
                price_cents = price.unit_amount or 0
                currency = price.currency or 'usd'
                
                packages.append({
                    "id": product.id,
                    "name": product.name,
                    "credits": credits,
                    "price_cents": price_cents,
                    "price_formatted": f"${price_cents / 100:.2f}",
                    "currency": currency,
                    "description": product.description or metadata.get('description', ''),
                    "popular": metadata.get('popular', 'false').lower() == 'true',
                    "price_per_credit": round(price_cents / credits, 2) if credits > 0 else 0,
                    "price_id": price.id,
                    "product_id": product.id,
                })
            
            # Sort by price_cents
            packages.sort(key=lambda x: x['price_cents'])
            
            logger.info(f"Retrieved {len(packages)} packages from Stripe (out of {len(products.data)} products)")
            if len(packages) == 0 and len(products.data) > 0:
                logger.warning("No packages found but products exist. Check product names/metadata.")
                for product in products.data:
                    logger.debug(f"Product: {product.name}, metadata: {product.metadata}, default_price: {product.default_price}")
            
            return packages
            
        except stripe.error.StripeError as e:
            logger.error(f"Error fetching packages from Stripe: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching packages: {e}")
            return []
    
    @staticmethod
    def get_package(package_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific credit package by ID from Stripe.
        
        Args:
            package_id: Stripe Product ID
            
        Returns:
            Package dictionary or None if not found
        """
        if not settings.stripe_secret_key:
            return None
        
        try:
            # Ensure Stripe API key is set
            if not stripe.api_key or stripe.api_key != settings.stripe_secret_key:
                stripe.api_key = settings.stripe_secret_key
            
            # Retrieve product from Stripe
            product = stripe.Product.retrieve(package_id)
            
            # Get price
            default_price_id = product.default_price
            if not default_price_id:
                prices = stripe.Price.list(product=product.id, active=True, limit=1)
                if not prices.data:
                    return None
                default_price_id = prices.data[0].id
            
            price = stripe.Price.retrieve(default_price_id)
            
            metadata = product.metadata or {}
            
            # Try to get credits from metadata first
            credits = None
            if 'credits' in metadata:
                try:
                    credits = int(metadata.get('credits', 0))
                except (ValueError, TypeError):
                    credits = None
            
            # If no metadata credits, try to extract from product name
            if credits is None or credits == 0:
                try:
                    # Try to parse product name as integer (e.g., "100", "50", "25", "10")
                    product_name_clean = product.name.strip()
                    credits = int(product_name_clean)
                    logger.info(f"Extracted credits from product name '{product.name}': {credits}")
                except (ValueError, TypeError):
                    # If name is not a number, return None
                    logger.debug(f"Product '{product.name}' - no credits metadata and name is not a number")
                    return None
            
            if credits <= 0:
                logger.debug(f"Product '{product.name}' - invalid credits value: {credits}")
                return None
            
            price_cents = price.unit_amount or 0
            currency = price.currency or 'usd'
            
            return {
                "id": product.id,
                "name": product.name,
                "credits": credits,
                "price_cents": price_cents,
                "price_formatted": f"${price_cents / 100:.2f}",
                "currency": currency,
                "description": product.description or metadata.get('description', ''),
                "popular": metadata.get('popular', 'false').lower() == 'true',
                "price_per_credit": round(price_cents / credits, 2) if credits > 0 else 0,
                "price_id": price.id,
                "product_id": product.id,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Error fetching package {package_id} from Stripe: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching package: {e}")
            return None
    
    @staticmethod
    async def create_checkout_session(
        db: AsyncSession,
        user_id: str,
        package_id: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for credit purchase.
        
        Args:
            db: Database session
            user_id: User ID making the purchase
            package_id: ID of the credit package
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is cancelled
            
        Returns:
            Dict with checkout_url and session_id
            
        Raises:
            ValueError: If package not found or Stripe not configured
        """
        if not settings.stripe_secret_key:
            raise ValueError("Stripe is not configured")
        
        # Get the package from Stripe
        package = StripeService.get_package(package_id)
        if not package:
            raise ValueError(f"Package '{package_id}' not found")
        
        price_id = package.get('price_id')
        if not price_id:
            raise ValueError(f"Package '{package_id}' has no price_id")
        
        # Verify user exists
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        
        try:
            # Create Stripe Checkout Session using price_id
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "credits": str(package['credits']),
                    "package_id": package_id,
                    "product_id": package.get('product_id', package_id),
                },
                # Customer email for receipt
                customer_email=user.email if user.email else None,
            )
            
            # Create pending payment record
            payment = Payment(
                user_id=str(user_id),
                stripe_checkout_session_id=checkout_session.id,
                amount_cents=package['price_cents'],
                currency=package['currency'],
                credits_amount=package['credits'],
                status=PaymentStatus.PENDING,
                package_id=package_id,
            )
            db.add(payment)
            await db.commit()
            
            logger.info(
                f"Created checkout session {checkout_session.id} for user {user_id}, "
                f"package {package_id} ({package['credits']} credits)"
            )
            
            return {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
                "expires_at": checkout_session.expires_at,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise ValueError(f"Payment service error: {str(e)}")
    
    @staticmethod
    async def create_payment_intent(
        db: AsyncSession,
        user_id: str,
        package_id: str,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Intent for credit purchase.
        
        This method is used for mobile apps with Payment Sheet integration.
        It creates a Payment Intent that can be used with Stripe Payment Sheet
        for native in-app payments.
        
        Args:
            db: Database session
            user_id: User ID making the purchase
            package_id: ID of the credit package
            
        Returns:
            Dict with client_secret and payment_intent_id
            
        Raises:
            ValueError: If package not found or Stripe not configured
        """
        if not settings.stripe_secret_key:
            logger.error("Stripe secret key not configured")
            raise ValueError("Stripe is not configured")
        
        # Ensure Stripe API key is set (in case it wasn't initialized)
        if not stripe.api_key or stripe.api_key != settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
            logger.info("Stripe API key configured")
        
        logger.info(f"Creating payment intent for package {package_id}, user {user_id}")
        
        # Get the package from Stripe
        package = StripeService.get_package(package_id)
        if not package:
            logger.error(f"Package '{package_id}' not found in Stripe")
            raise ValueError(f"Package '{package_id}' not found")
        
        price_id = package.get('price_id')
        if not price_id:
            logger.error(f"Package '{package_id}' has no price_id")
            raise ValueError(f"Package '{package_id}' has no valid price")
        
        logger.info(f"Package found: {package['name']}, price: {package['price_cents']} cents, price_id: {price_id}")
        
        # Verify user exists
        try:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_id} not found")
                raise ValueError("User not found")
            
            logger.info(f"User found: {user.email if user.email else user_id}, user_id type: {type(user_id)}")
        except Exception as user_error:
            logger.error(f"Error querying user: {user_error}")
            raise ValueError(f"Error finding user: {str(user_error)}")
        
        try:
            logger.info(f"Calling Stripe API to create payment intent with price_id: {price_id}...")
            # Create Stripe Payment Intent using price_id
            # Note: Payment Intent doesn't directly support price_id, so we use amount
            # But we store the price_id in metadata for reference
            payment_intent = stripe.PaymentIntent.create(
                amount=package['price_cents'],
                currency=package['currency'],
                payment_method_types=["card"],
                metadata={
                    "user_id": str(user_id),
                    "credits": str(package['credits']),
                    "package_id": package_id,
                    "product_id": package.get('product_id', package_id),
                    "price_id": price_id,
                },
                description=f"SecondBrain {package['name']} - {package['credits']} AI Credits",
                receipt_email=user.email if user.email else None,
            )
            logger.info(f"Stripe payment intent created: {payment_intent.id}")
            
            if not payment_intent.client_secret:
                logger.error(f"Payment intent created but missing client_secret: {payment_intent.id}")
                raise ValueError("Payment intent created but missing client_secret")
            
            # Create pending payment record
            try:
                payment = Payment(
                    user_id=str(user_id),
                    stripe_payment_intent_id=payment_intent.id,
                    amount_cents=package['price_cents'],
                    currency=package['currency'],
                    credits_amount=package['credits'],
                    status=PaymentStatus.PENDING,
                    package_id=package_id,
                )
                db.add(payment)
                await db.commit()
                logger.info(f"Payment record created in database: {payment.id}")
            except Exception as db_error:
                logger.error(f"Error saving payment to database: {db_error}")
                await db.rollback()
                raise ValueError(f"Failed to save payment record: {str(db_error)}")
            
            logger.info(
                f"Created payment intent {payment_intent.id} for user {user_id}, "
                f"package {package_id} ({package.credits} credits)"
            )
            
            return {
                "client_secret": payment_intent.client_secret,
                "payment_intent_id": payment_intent.id,
            }
            
        except stripe.error.StripeError as e:
            error_msg = f"Stripe API error: {str(e)}"
            if hasattr(e, 'user_message'):
                error_msg = f"{error_msg} - {e.user_message}"
            logger.error(f"Stripe error creating payment intent: {error_msg}")
            await db.rollback()
            raise ValueError(error_msg)
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Unexpected error creating payment intent: {e}\n{error_trace}")
            await db.rollback()
            raise ValueError(f"Unexpected error: {str(e)}")
    
    @staticmethod
    async def mark_payment_completed(
        db: AsyncSession,
        stripe_checkout_session_id: str,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Optional[Payment]:
        """
        Mark a payment as completed (called from webhook).
        Returns the payment if found and updated, None if already processed.
        
        Args:
            db: Database session
            stripe_checkout_session_id: Stripe checkout session ID
            stripe_payment_intent_id: Stripe payment intent ID
            
        Returns:
            Payment record or None if already completed
        """
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_checkout_session_id == stripe_checkout_session_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            logger.warning(f"Payment not found for session {stripe_checkout_session_id}")
            return None
        
        # Idempotency check - already completed
        if payment.status == PaymentStatus.COMPLETED:
            logger.info(f"Payment {payment.id} already completed, skipping")
            return None
        
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()
        if stripe_payment_intent_id:
            payment.stripe_payment_intent_id = stripe_payment_intent_id
        
        # Don't commit here - let caller handle transaction
        return payment
    
    @staticmethod
    async def mark_payment_completed_by_intent(
        db: AsyncSession,
        stripe_payment_intent_id: str,
    ) -> Optional[Payment]:
        """
        Mark a payment as completed by payment intent ID (called from webhook).
        Returns the payment if found and updated, None if already processed.
        
        Args:
            db: Database session
            stripe_payment_intent_id: Stripe payment intent ID
            
        Returns:
            Payment record or None if already completed
        """
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == stripe_payment_intent_id
            )
        )
        payment = result.scalar_one_or_none()
        
        if not payment:
            logger.warning(f"Payment not found for intent {stripe_payment_intent_id}")
            return None
        
        # Idempotency check - already completed
        if payment.status == PaymentStatus.COMPLETED:
            logger.info(f"Payment {payment.id} already completed, skipping")
            return None
        
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()
        
        # Don't commit here - let caller handle transaction
        return payment
    
    @staticmethod
    async def get_user_payments(
        db: AsyncSession,
        user_id: str,
        limit: int = 20,
    ) -> List[Payment]:
        """
        Get payment history for a user.
        
        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of records
            
        Returns:
            List of Payment records
        """
        result = await db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def ensure_stripe_customer(
        email: str,
        name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Ensure a Stripe customer exists for the given email.
        If customer doesn't exist, creates one. If exists, returns existing customer ID.
        
        Args:
            email: User email address
            name: Optional user name
            
        Returns:
            Stripe customer ID or None if Stripe is not configured
            
        Raises:
            ValueError: If email is not provided
        """
        if not email:
            raise ValueError("Email is required to create Stripe customer")
        
        if not settings.stripe_secret_key:
            logger.debug("Stripe not configured, skipping customer creation")
            return None
        
        try:
            # Ensure Stripe API key is set
            if not stripe.api_key or stripe.api_key != settings.stripe_secret_key:
                stripe.api_key = settings.stripe_secret_key
            
            # Search for existing customer by email
            customers = stripe.Customer.list(
                email=email,
                limit=1
            )
            
            if customers.data:
                # Customer already exists
                customer_id = customers.data[0].id
                logger.info(f"Found existing Stripe customer {customer_id} for email {email}")
                return customer_id
            
            # Create new customer
            customer_data = {
                "email": email,
            }
            if name:
                customer_data["name"] = name
            
            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created new Stripe customer {customer.id} for email {email}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error ensuring customer for {email}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error ensuring Stripe customer: {e}")
            return None


# Singleton instance
stripe_service = StripeService()


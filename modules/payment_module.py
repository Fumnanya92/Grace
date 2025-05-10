import os
import json
import random
import logging
import aiosqlite
from datetime import datetime
from typing import Dict, Optional, Any
from twilio.rest import Client
from config import config

class PaymentHandler:
    def __init__(self, db_path: str = 'memory.db'):
        """Initialize with an async database connection."""
        # Access Twilio credentials from the centralized config
        self.twilio_client = Client(config.TWILIO['account_sid'], config.TWILIO['auth_token'])
        self.whatsapp_number = config.TWILIO['whatsapp_number']
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database path does not exist: {self.db_path}")
        
    async def _get_db_connection(self):
        """Async method to get a DB connection."""
        return await aiosqlite.connect(self.db_path)

    async def process_payment_request(self, sender: str, message: str) -> str:
        """Handle the complete payment flow."""
        try:
            # Check if user is asking for account details
            if any(keyword in message.lower() for keyword in ["account", "payment", "deposit"]):
                return await self._handle_new_payment(sender)
                
            # Check if user is submitting payment proof
            elif self._is_payment_proof(message):
                return await self._handle_payment_proof(sender, message)
                
            return config.RESPONSES['payment']['default']
            
        except Exception as e:
            logging.error(f"Payment processing error: {e}")
            return config.RESPONSES['errors']['payment_processing']

    async def verify_payment(self, verification_code: str) -> Dict[str, Any]:
        """Verify a payment using the verification code."""
        try:
            db = await self._get_db_connection()
            cursor = await db.cursor()
            query = '''
                SELECT * FROM payments 
                WHERE verification_code = ? AND deposit_paid = 0
            '''
            await cursor.execute(query, (verification_code,))
            payment = await cursor.fetchone()

            if payment:
                # Mark as paid
                await cursor.execute(''' 
                    UPDATE payments SET 
                    deposit_paid = 1, 
                    payment_date = ? 
                    WHERE verification_code = ? 
                ''', (datetime.now(), verification_code))

                query = '''
                    SELECT name FROM user_memory 
                    WHERE sender = ? 
                '''
                await cursor.execute(query, (payment['sender'],))
                customer = await cursor.fetchone()

                # Notify customer
                await self._send_payment_confirmation(payment['sender'], customer['name'] if customer else None)

                await db.commit()
                return {
                    'status': 'success',
                    'customer': payment['sender'],
                    'name': customer['name'] if customer else None
                }

            return {'status': 'not_found'}
                
        except Exception as e:
            logging.error(f"Payment verification error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _handle_new_payment(self, sender: str) -> str:
        """Process new payment request."""
        db = await self._get_db_connection()
        cursor = await db.cursor()
        query = '''
            SELECT deposit_paid FROM payments 
            WHERE sender = ? AND deposit_paid = 0
        '''
        await cursor.execute(query, (sender,))
        existing = await cursor.fetchone()

        if existing:
            return config.RESPONSES['payment']['pending']
        
        # Generate verification code
        verification_code = ''.join(random.choices('0123456789', k=config.PAYMENT_DETAILS.get('verification_code_length', 4)))
        
        # Save payment record
        await cursor.execute(''' 
            INSERT OR REPLACE INTO payments 
            (sender, deposit_paid, verification_code, payment_date)
            VALUES (?, 0, ?, ?) 
        ''', (sender, verification_code, datetime.now()))

        # Alert accountant (can be async)
        await self._alert_accountant(sender, verification_code)

        await db.commit()

        return config.RESPONSES['payment']['instructions'].format(
            account_name=config.PAYMENT_DETAILS['account_name'],
            account_number=config.PAYMENT_DETAILS['account_number'],
            bank_name=config.PAYMENT_DETAILS['bank_name'],
            amount=int(config.PAYMENT_DETAILS['total_amount'] * config.PAYMENT_DETAILS.get('deposit_percentage', 0.5))
        )

    async def _handle_payment_proof(self, sender: str, proof: str) -> str:
        """Process payment proof submission."""
        db = await self._get_db_connection()
        cursor = await db.cursor()
        await cursor.execute(''' 
            UPDATE payments SET 
            payment_proof = ? 
            WHERE sender = ? AND deposit_paid = 0 
        ''', (proof, sender))

        await db.commit()

        return config.RESPONSES['payment']['verification_sent']

    async def _alert_accountant(self, sender: str, verification_code: str) -> None:
        """Send payment verification alert to accountant."""
        try:
            db = await self._get_db_connection()
            cursor = await db.cursor()
            query = '''SELECT name FROM user_memory WHERE sender = ?'''
            await cursor.execute(query, (sender,))
            result = await cursor.fetchone()
            
            customer_name = result[0] if result else "Unknown"
            
            message = config.RESPONSES['payment']['accountant_alert'].format(
                customer_name=customer_name,
                phone=sender.replace("whatsapp:", ""),
                amount=int(config.PAYMENT_DETAILS['total_amount'] * config.PAYMENT_DETAILS.get('deposit_percentage', 0.5)),
                timestamp=datetime.now().strftime("%H:%M %d/%m"),
                shortcode=verification_code
            )
            
            await self.twilio_client.messages.create(
                body=message,
                from_=self.whatsapp_number,
                to=config.BUSINESS_RULES['accountant_contact']
            )
            logging.info(f"Alert sent to accountant for sender: {sender}, verification code: {verification_code}")
        except Exception as e:
            logging.error(f"Failed to alert accountant: {e}")

    async def _send_payment_confirmation(self, sender: str, name: Optional[str] = None) -> None:
        """Send payment confirmation to customer."""
        try:
            greeting = f"Dear {name}," if name else "Hello,"
            message = f"{greeting}\n\n{config.RESPONSES['payment']['confirmed']}"
            
            await self.twilio_client.messages.create(
                body=message,
                from_=self.whatsapp_number,
                to=sender
            )
        except Exception as e:
            logging.error(f"Failed to send payment confirmation: {e}")

    def _is_payment_proof(self, message: str) -> bool:
        """Check if message contains payment proof."""
        keywords = ["paid", "sent", "proof", "receipt"]
        return any(keyword in message.lower() for keyword in keywords)

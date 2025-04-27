import os
import json
import sqlite3
import random
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from twilio.rest import Client
from config import config

class PaymentHandler:
    def __init__(self):
        self.twilio_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        self.db_path = config.DATABASE.get('path', 'memory.db')  # Default to 'memory.db'
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database path does not exist: {self.db_path}")

    def process_payment_request(self, sender: str, message: str) -> str:
        """Handle the complete payment flow"""
        try:
            # Check if user is asking for account details
            if any(keyword in message.lower() for keyword in ["account", "payment", "deposit"]):
                return self._handle_new_payment(sender)
                
            # Check if user is submitting payment proof
            elif self._is_payment_proof(message):
                return self._handle_payment_proof(sender, message)
                
            return config.RESPONSES['payment']['default']
            
        except Exception as e:
            logging.error(f"Payment processing error: {e}")
            return config.RESPONSES['errors']['payment_processing']

    def verify_payment(self, verification_code: str) -> Dict[str, Any]:
        """Verify a payment using the verification code"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Find pending payment
                cursor.execute('''
                    SELECT * FROM payments 
                    WHERE verification_code = ? AND deposit_paid = 0
                ''', (verification_code,))
                payment = cursor.fetchone()
                
                if payment:
                    # Mark as paid
                    cursor.execute('''
                        UPDATE payments SET 
                        deposit_paid = 1, 
                        payment_date = ?
                        WHERE verification_code = ?
                    ''', (datetime.now(), verification_code))
                    
                    # Get customer info
                    cursor.execute('''
                        SELECT name FROM user_memory 
                        WHERE sender = ?
                    ''', (payment['sender'],))
                    customer = cursor.fetchone()
                    
                    conn.commit()
                    
                    # Notify customer
                    self._send_payment_confirmation(
                        payment['sender'],
                        customer['name'] if customer else None
                    )
                    
                    return {
                        'status': 'success',
                        'customer': payment['sender'],
                        'name': customer['name'] if customer else None
                    }
                
                return {'status': 'not_found'}
                
        except Exception as e:
            logging.error(f"Payment verification error: {e}")
            return {'status': 'error', 'message': str(e)}

    def _handle_new_payment(self, sender: str) -> str:
        """Process new payment request"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check for existing pending payment
            cursor.execute('''
                SELECT deposit_paid FROM payments 
                WHERE sender = ? AND deposit_paid = 0
            ''', (sender,))
            existing = cursor.fetchone()
            
            if existing:
                return config.RESPONSES['payment']['pending']
            
            # Generate verification code
            verification_code = ''.join(random.choices('0123456789', k=config.PAYMENT_DETAILS.get('verification_code_length', 4)))
            
            # Save payment record
            cursor.execute('''
                INSERT OR REPLACE INTO payments 
                (sender, deposit_paid, verification_code, payment_date)
                VALUES (?, 0, ?, ?)
            ''', (sender, verification_code, datetime.now()))
            
            conn.commit()
        
        # Alert accountant
        self._alert_accountant(sender, verification_code)
        
        return config.RESPONSES['payment']['instructions'].format(
            account_name=config.PAYMENT_DETAILS['account_name'],
            account_number=config.PAYMENT_DETAILS['account_number'],
            bank_name=config.PAYMENT_DETAILS['bank_name'],
            amount=int(config.PAYMENT_DETAILS['total_amount'] * config.PAYMENT_DETAILS.get('deposit_percentage', 0.5))
        )

    def _handle_payment_proof(self, sender: str, proof: str) -> str:
        """Process payment proof submission"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Update payment record with proof
            cursor.execute('''
                UPDATE payments SET 
                payment_proof = ?
                WHERE sender = ? AND deposit_paid = 0
            ''', (proof, sender))
            
            conn.commit()
        
        return config.RESPONSES['payment']['verification_sent']

    def _alert_accountant(self, sender: str, verification_code: str) -> None:
        """Send payment verification alert to accountant"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name FROM user_memory WHERE sender = ?
                ''', (sender,))
                result = cursor.fetchone()
                
            customer_name = result[0] if result else "Unknown"
            
            message = config.RESPONSES['payment']['accountant_alert'].format(
                customer_name=customer_name,
                phone=sender.replace("whatsapp:", ""),
                amount=int(config.PAYMENT_DETAILS['total_amount'] * config.PAYMENT_DETAILS.get('deposit_percentage', 0.5)),
                timestamp=datetime.now().strftime("%H:%M %d/%m"),
                shortcode=verification_code
            )
            
            self.twilio_client.messages.create(
                body=message,
                from_=config.WHATSAPP_NUMBER,
                to=config.BUSINESS_RULES['accountant_contact']
            )
            logging.info(f"Alert sent to accountant for sender: {sender}, verification code: {verification_code}")
        except Exception as e:
            logging.error(f"Failed to alert accountant: {e}")

    def _send_payment_confirmation(self, sender: str, name: Optional[str] = None) -> None:
        """Send payment confirmation to customer"""
        try:
            greeting = f"Dear {name}," if name else "Hello,"
            message = f"{greeting}\n\n{config.RESPONSES['payment']['confirmed']}"
            
            self.twilio_client.messages.create(
                body=message,
                from_=config.WHATSAPP_NUMBER,
                to=sender
            )
        except Exception as e:
            logging.error(f"Failed to send payment confirmation: {e}")

    def _is_payment_proof(self, message: str) -> bool:
        """Check if message contains payment proof"""
        # Enhanced logic to detect payment proof
        keywords = ["paid", "sent", "proof", "receipt"]
        return any(keyword in message.lower() for keyword in keywords)
"""
Email service utility for sending emails.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to_email, subject, html_content):
    """
    Send an email with the given parameters.
    
    For development, this prints the email to the console.
    In production, configure with a real email service like SendGrid, Mailgun, etc.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML content of the email
    """
    # For development purposes, just print the email
    if os.environ.get('FLASK_ENV') == 'development':
        print(f"\n--- Email to: {to_email} ---")
        print(f"Subject: {subject}")
        print(f"Content: {html_content}")
        print("--- End of email ---\n")
        return True
    
    # For production, use SMTP or email service API
    try:
        # This is a placeholder - replace with your actual email service
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.environ.get('EMAIL_SENDER', 'noreply@example.com')
        msg['To'] = to_email
        
        # Attach HTML content
        part = MIMEText(html_content, 'html')
        msg.attach(part)
        
        # Example using SMTP - adjust based on your email provider
        server = smtplib.SMTP(os.environ.get('SMTP_SERVER', 'smtp.gmail.com'), 
                             int(os.environ.get('SMTP_PORT', 587)))
        server.starttls()
        server.login(os.environ.get('EMAIL_USER'), os.environ.get('EMAIL_PASSWORD'))
        server.sendmail(msg['From'], to_email, msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
import nodemailer, { Transporter } from 'nodemailer';
import config from '../config';
import logger from './logger';

class EmailService {
  private transporter: Transporter;

  constructor() {
    this.transporter = nodemailer.createTransport(config.email.smtp);
  }

  /**
   * Send email verification
   */
  async sendVerificationEmail(email: string, token: string, name: string): Promise<void> {
    const verificationUrl = `${config.frontendUrl}/verify-email?token=${token}`;

    const mailOptions = {
      from: config.email.from,
      to: email,
      subject: 'Verify Your Email - GraphCeylon',
      html: `
        <!DOCTYPE html>
        <html>
          <head>
            <style>
              body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
              .container { max-width: 600px; margin: 0 auto; padding: 20px; }
              .header { background: #4CAF50; color: white; padding: 20px; text-align: center; }
              .content { padding: 20px; background: #f9f9f9; }
              .button { display: inline-block; padding: 12px 24px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
              .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h1>Welcome to GraphCeylon!</h1>
              </div>
              <div class="content">
                <h2>Hello ${name},</h2>
                <p>Thank you for registering with GraphCeylon. Please verify your email address by clicking the button below:</p>
                <a href="${verificationUrl}" class="button">Verify Email</a>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all;">${verificationUrl}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account, please ignore this email.</p>
              </div>
              <div class="footer">
                <p>&copy; ${new Date().getFullYear()} GraphCeylon. All rights reserved.</p>
              </div>
            </div>
          </body>
        </html>
      `,
    };

    try {
      await this.transporter.sendMail(mailOptions);
      logger.info(`Verification email sent to ${email}`);
    } catch (error) {
      logger.error('Failed to send verification email', error);
      throw error;
    }
  }

  /**
   * Send password reset email
   */
  async sendPasswordResetEmail(email: string, token: string, name: string): Promise<void> {
    const resetUrl = `${config.frontendUrl}/reset-password?token=${token}`;

    const mailOptions = {
      from: config.email.from,
      to: email,
      subject: 'Password Reset Request - GraphCeylon',
      html: `
        <!DOCTYPE html>
        <html>
          <head>
            <style>
              body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
              .container { max-width: 600px; margin: 0 auto; padding: 20px; }
              .header { background: #FF5722; color: white; padding: 20px; text-align: center; }
              .content { padding: 20px; background: #f9f9f9; }
              .button { display: inline-block; padding: 12px 24px; background: #FF5722; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
              .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
              .warning { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 20px 0; }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h1>Password Reset Request</h1>
              </div>
              <div class="content">
                <h2>Hello ${name},</h2>
                <p>We received a request to reset your password. Click the button below to reset it:</p>
                <a href="${resetUrl}" class="button">Reset Password</a>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all;">${resetUrl}</p>
                <div class="warning">
                  <strong>⚠️ Security Notice:</strong>
                  <p>This link will expire in 1 hour. If you didn't request a password reset, please ignore this email or contact support if you have concerns.</p>
                </div>
              </div>
              <div class="footer">
                <p>&copy; ${new Date().getFullYear()} GraphCeylon. All rights reserved.</p>
              </div>
            </div>
          </body>
        </html>
      `,
    };

    try {
      await this.transporter.sendMail(mailOptions);
      logger.info(`Password reset email sent to ${email}`);
    } catch (error) {
      logger.error('Failed to send password reset email', error);
      throw error;
    }
  }

  /**
   * Send welcome email
   */
  async sendWelcomeEmail(email: string, name: string): Promise<void> {
    const mailOptions = {
      from: config.email.from,
      to: email,
      subject: 'Welcome to GraphCeylon!',
      html: `
        <!DOCTYPE html>
        <html>
          <head>
            <style>
              body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
              .container { max-width: 600px; margin: 0 auto; padding: 20px; }
              .header { background: #2196F3; color: white; padding: 20px; text-align: center; }
              .content { padding: 20px; background: #f9f9f9; }
              .button { display: inline-block; padding: 12px 24px; background: #2196F3; color: white; text-decoration: none; border-radius: 4px; margin: 20px 0; }
              .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
          </head>
          <body>
            <div class="container">
              <div class="header">
                <h1>Welcome to GraphCeylon! 🎉</h1>
              </div>
              <div class="content">
                <h2>Hello ${name},</h2>
                <p>Your email has been verified successfully! Welcome to the GraphCeylon community.</p>
                <p>You can now access all features of our tourism intelligence platform for Sri Lanka.</p>
                <a href="${config.frontendUrl}/dashboard" class="button">Go to Dashboard</a>
                <h3>What's Next?</h3>
                <ul>
                  <li>Explore Sri Lankan tourism knowledge graph</li>
                  <li>Get personalized recommendations</li>
                  <li>Access multilingual content</li>
                  <li>Plan your sustainable travel</li>
                </ul>
              </div>
              <div class="footer">
                <p>&copy; ${new Date().getFullYear()} GraphCeylon. All rights reserved.</p>
              </div>
            </div>
          </body>
        </html>
      `,
    };

    try {
      await this.transporter.sendMail(mailOptions);
      logger.info(`Welcome email sent to ${email}`);
    } catch (error) {
      logger.error('Failed to send welcome email', error);
      throw error;
    }
  }
}

export default new EmailService();

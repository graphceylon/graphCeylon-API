import express, { Application, Request, Response } from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import morgan from 'morgan';
import config from './config';
import redisClient from './config/redis';
import authRoutes from './routes/auth.routes';
import { errorHandler, notFoundHandler } from './middlewares/error.middleware';
import { requestLogger } from './middlewares/requestLogger.middleware';
import { generalLimiter } from './middlewares/rateLimit.middleware';
import { morganStream } from './utils/logger';
import logger from './utils/logger';
import { AuthController } from './controllers/auth.controller';

const authController = new AuthController();

class App {
  public app: Application;

  constructor() {
    this.app = express();
    this.initializeMiddlewares();
    this.initializeRoutes();
    this.initializeErrorHandling();
  }

  private initializeMiddlewares(): void {
    // Security middleware
    this.app.use(helmet());

    // CORS
    this.app.use(
      cors({
        origin: config.cors.origin,
        credentials: true,
      })
    );

    // Compression
    this.app.use(compression());

    // Body parser
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Request logging
    this.app.use(morgan('combined', { stream: morganStream }));
    this.app.use(requestLogger);

    // Rate limiting
    this.app.use(generalLimiter);
  }

  private initializeRoutes(): void {
    // Health check
    this.app.get('/health', authController.healthCheck.bind(authController));

    // API routes
    this.app.use(config.apiPrefix, authRoutes);

    // Root route
    this.app.get('/', (_req: Request, res: Response) => {
      res.json({
        service: 'GraphCeylon Auth Service',
        version: '1.0.0',
        status: 'running',
        timestamp: new Date().toISOString(),
      });
    });
  }

  private initializeErrorHandling(): void {
    // 404 handler
    this.app.use(notFoundHandler);

    // Global error handler
    this.app.use(errorHandler);
  }

  public async initialize(): Promise<void> {
    try {
      // Connect to Redis
      await redisClient.connect();
      logger.info('Redis connected successfully');
    } catch (error) {
      logger.error('Failed to initialize application:', error);
      throw error;
    }
  }

  public async shutdown(): Promise<void> {
    try {
      await redisClient.disconnect();
      logger.info('Application shutdown complete');
    } catch (error) {
      logger.error('Error during shutdown:', error);
      throw error;
    }
  }
}

export default App;

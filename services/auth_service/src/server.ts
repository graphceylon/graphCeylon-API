import App from './app';
import config from './config';
import logger from './utils/logger';

const app = new App();

const startServer = async (): Promise<void> => {
  try {
    // Initialize application
    await app.initialize();

    // Start server
    const server = app.app.listen(config.port, () => {
      logger.info(`
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🚀 GraphCeylon Auth Service                             ║
║                                                           ║
║   Environment: ${config.env.padEnd(40)}                   ║
║   Port:        ${config.port.toString().padEnd(40)}       ║
║   API Prefix:  ${config.apiPrefix.padEnd(40)}             ║
║   Status:      Running ✓                                 ║
║                                                           ║
║   Endpoints:                                              ║
║   - http://localhost:${config.port}/health                ║
║   - http://localhost:${config.port}${config.apiPrefix}                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
      `);
    });

    // Graceful shutdown
    const gracefulShutdown = async (signal: string): Promise<void> => {
      logger.info(`${signal} received. Starting graceful shutdown...`);

      server.close(async () => {
        logger.info('HTTP server closed');

        try {
          await app.shutdown();
          process.exit(0);
        } catch (error) {
          logger.error('Error during shutdown:', error);
          process.exit(1);
        }
      });

      // Force shutdown after 10 seconds
      setTimeout(() => {
        logger.error('Forced shutdown due to timeout');
        process.exit(1);
      }, 10000);
    };

    // Handle shutdown signals
    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));

    // Handle uncaught errors
    process.on('uncaughtException', (error) => {
      logger.error('Uncaught Exception:', error);
      gracefulShutdown('uncaughtException');
    });

    process.on('unhandledRejection', (reason, promise) => {
      logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
      gracefulShutdown('unhandledRejection');
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
};

startServer();

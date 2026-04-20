import 'reflect-metadata';
import { DataSource } from 'typeorm';
import config from './index';
import { User } from '../entities/User.entity';

export const AppDataSource = new DataSource({
  type: config.database.type,
  host: config.database.host,
  port: config.database.port,
  username: config.database.username,
  password: config.database.password,
  database: config.database.database,
  synchronize: config.database.synchronize,
  logging: config.database.logging,
  entities: [User],
  migrations: ['src/migrations/**/*.ts'],
  subscribers: [],
  ssl: process.env.DB_SSL === 'false' ? false : (config.env === 'production' ? { rejectUnauthorized: false } : false),
});

export const initializeDatabase = async (): Promise<void> => {
  try {
    await AppDataSource.initialize();
    console.log('✓ Database connection initialized');
  } catch (error) {
    console.error('✗ Error initializing database connection:', error);
    throw error;
  }
};

export const closeDatabase = async (): Promise<void> => {
  if (AppDataSource.isInitialized) {
    await AppDataSource.destroy();
    console.log('✓ Database connection closed');
  }
};

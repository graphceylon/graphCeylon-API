import { createClient, RedisClientType } from 'redis';
import config from './index';
import logger from '../utils/logger';

class RedisClient {
  private static instance: RedisClient;
  private client: RedisClientType;
  private isConnected: boolean = false;

  private constructor() {
    this.client = createClient({
      socket: {
        host: config.redis.host,
        port: config.redis.port,
      },
      password: config.redis.password,
      database: config.redis.db,
    });

    this.client.on('error', (err) => {
      logger.error('Redis Client Error', err);
      this.isConnected = false;
    });

    this.client.on('connect', () => {
      logger.info('Redis Client Connected');
      this.isConnected = true;
    });

    this.client.on('ready', () => {
      logger.info('Redis Client Ready');
    });

    this.client.on('end', () => {
      logger.info('Redis Client Connection Closed');
      this.isConnected = false;
    });
  }

  public static getInstance(): RedisClient {
    if (!RedisClient.instance) {
      RedisClient.instance = new RedisClient();
    }
    return RedisClient.instance;
  }

  public async connect(): Promise<void> {
    if (!this.isConnected) {
      await this.client.connect();
    }
  }

  public async disconnect(): Promise<void> {
    if (this.isConnected) {
      await this.client.quit();
    }
  }

  public getClient(): RedisClientType {
    return this.client;
  }

  public async set(key: string, value: string, expiresIn?: number): Promise<void> {
    if (expiresIn) {
      await this.client.setEx(key, expiresIn, value);
    } else {
      await this.client.set(key, value);
    }
  }

  public async get(key: string): Promise<string | null> {
    return await this.client.get(key);
  }

  public async del(key: string): Promise<void> {
    await this.client.del(key);
  }

  public async exists(key: string): Promise<boolean> {
    const result = await this.client.exists(key);
    return result === 1;
  }

  public async incr(key: string): Promise<number> {
    return await this.client.incr(key);
  }

  public async expire(key: string, seconds: number): Promise<void> {
    await this.client.expire(key, seconds);
  }

  public async ttl(key: string): Promise<number> {
    return await this.client.ttl(key);
  }
}

export default RedisClient.getInstance();

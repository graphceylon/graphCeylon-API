import { Repository, FindOptionsWhere } from 'typeorm';
import { AppDataSource } from '../config/database';
import { User } from '../entities/User.entity';
import { SearchUsersDto, UserRole } from '../types';
import { calculateOffset } from '../utils/helpers';

export class UserRepository {
  private repository: Repository<User>;

  constructor() {
    this.repository = AppDataSource.getRepository(User);
  }

  /**
   * Find user by ID
   */
  async findById(id: string): Promise<User | null> {
    return this.repository.findOne({ where: { id } });
  }

  /**
   * Find user by email
   */
  async findByEmail(email: string): Promise<User | null> {
    return this.repository.findOne({ where: { email } });
  }

  /**
   * Find all users with pagination
   */
  async findAll(page: number = 1, limit: number = 20): Promise<[User[], number]> {
    const offset = calculateOffset(page, limit);
    return this.repository.findAndCount({
      skip: offset,
      take: limit,
      order: { createdAt: 'DESC' },
    });
  }

  /**
   * Search users
   */
  async search(params: SearchUsersDto): Promise<[User[], number]> {
    const {
      query,
      role,
      isActive,
      page = 1,
      limit = 20,
      sortBy = 'createdAt',
      sortOrder = 'DESC',
    } = params;

    const where: FindOptionsWhere<User> = {};

    if (role) {
      where.role = role;
    }

    if (isActive !== undefined) {
      where.isActive = isActive;
    }

    const queryBuilder = this.repository.createQueryBuilder('user');

    // Apply filters
    if (role) {
      queryBuilder.andWhere('user.role = :role', { role });
    }

    if (isActive !== undefined) {
      queryBuilder.andWhere('user.isActive = :isActive', { isActive });
    }

    if (query) {
      queryBuilder.andWhere(
        '(user.firstName ILIKE :query OR user.lastName ILIKE :query OR user.email ILIKE :query)',
        { query: `%${query}%` }
      );
    }

    // Apply sorting
    const allowedSortFields = ['createdAt', 'updatedAt', 'email', 'firstName', 'lastName'];
    const sortField = allowedSortFields.includes(sortBy) ? sortBy : 'createdAt';
    queryBuilder.orderBy(`user.${sortField}`, sortOrder);

    // Apply pagination
    const offset = calculateOffset(page, limit);
    queryBuilder.skip(offset).take(limit);

    return queryBuilder.getManyAndCount();
  }

  /**
   * Create user
   */
  async create(userData: Partial<User>): Promise<User> {
    const user = this.repository.create(userData);
    return this.repository.save(user);
  }

  /**
   * Update user
   */
  async update(id: string, userData: Partial<User>): Promise<User | null> {
    await this.repository.update(id, userData);
    return this.findById(id);
  }

  /**
   * Delete user
   */
  async delete(id: string): Promise<boolean> {
    const result = await this.repository.delete(id);
    return result.affected !== 0;
  }

  /**
   * Count users
   */
  async count(): Promise<number> {
    return this.repository.count();
  }

  /**
   * Count by role
   */
  async countByRole(role: UserRole): Promise<number> {
    return this.repository.count({ where: { role } });
  }

  /**
   * Count active users
   */
  async countActive(): Promise<number> {
    return this.repository.count({ where: { isActive: true } });
  }

  /**
   * Find recently created users
   */
  async findRecent(limit: number = 10): Promise<User[]> {
    return this.repository.find({
      take: limit,
      order: { createdAt: 'DESC' },
    });
  }

  /**
   * Update last login
   */
  async updateLastLogin(id: string): Promise<void> {
    await this.repository.update(id, { lastLoginAt: new Date() });
  }

  /**
   * Check if email exists
   */
  async emailExists(email: string, excludeId?: string): Promise<boolean> {
    const where: FindOptionsWhere<User> = { email };

    if (excludeId) {
      const user = await this.repository.findOne({ where });
      return user !== null && user.id !== excludeId;
    }

    return (await this.repository.count({ where })) > 0;
  }

  /**
   * Get users by role
   */
  async findByRole(role: UserRole, page: number = 1, limit: number = 20): Promise<[User[], number]> {
    const offset = calculateOffset(page, limit);
    return this.repository.findAndCount({
      where: { role },
      skip: offset,
      take: limit,
      order: { createdAt: 'DESC' },
    });
  }
}

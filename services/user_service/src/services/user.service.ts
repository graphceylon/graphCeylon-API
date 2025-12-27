import { UserRepository } from '../repositories/user.repository';
import {
  CreateUserDto,
  UpdateUserDto,
  UpdateProfileDto,
  SearchUsersDto,
  UserResponse,
  PaginatedResponse,
  UserRole,
} from '../types';
import { User } from '../entities/User.entity';
import { NotFoundError, ConflictError } from '../utils/errors';
import { sanitizeEmail, sanitizeString, calculateTotalPages } from '../utils/helpers';
import config from '../config';
import logger from '../utils/logger';

export class UserService {
  private userRepository: UserRepository;

  constructor() {
    this.userRepository = new UserRepository();
  }

  /**
   * Get all users with pagination
   */
  async getAllUsers(page: number = 1, limit: number = config.pagination.defaultPageSize): Promise<PaginatedResponse<UserResponse>> {
    // Validate pagination params
    if (limit > config.pagination.maxPageSize) {
      limit = config.pagination.maxPageSize;
    }

    const [users, total] = await this.userRepository.findAll(page, limit);

    return this.buildPaginatedResponse(users, total, page, limit);
  }

  /**
   * Get user by ID
   */
  async getUserById(id: string): Promise<UserResponse> {
    const user = await this.userRepository.findById(id);

    if (!user) {
      throw new NotFoundError('User');
    }

    return this.toUserResponse(user);
  }

  /**
   * Get user by email
   */
  async getUserByEmail(email: string): Promise<UserResponse> {
    const sanitizedEmail = sanitizeEmail(email);
    const user = await this.userRepository.findByEmail(sanitizedEmail);

    if (!user) {
      throw new NotFoundError('User');
    }

    return this.toUserResponse(user);
  }

  /**
   * Create new user
   */
  async createUser(data: CreateUserDto): Promise<UserResponse> {
    const email = sanitizeEmail(data.email);

    // Check if email already exists
    const existingUser = await this.userRepository.findByEmail(email);
    if (existingUser) {
      throw new ConflictError('User with this email already exists');
    }

    // Create user
    const user = await this.userRepository.create({
      email,
      firstName: sanitizeString(data.firstName),
      lastName: sanitizeString(data.lastName),
      role: data.role || UserRole.USER,
      bio: data.bio ? sanitizeString(data.bio) : undefined,
      avatar: data.avatar,
      preferences: {},
    });

    logger.info(`User created: ${user.email}`);

    return this.toUserResponse(user);
  }

  /**
   * Update user
   */
  async updateUser(id: string, data: UpdateUserDto): Promise<UserResponse> {
    const user = await this.userRepository.findById(id);

    if (!user) {
      throw new NotFoundError('User');
    }

    // Build update data
    const updateData: Partial<User> = {};

    if (data.firstName) {
      updateData.firstName = sanitizeString(data.firstName);
    }

    if (data.lastName) {
      updateData.lastName = sanitizeString(data.lastName);
    }

    if (data.bio !== undefined) {
      updateData.bio = data.bio ? sanitizeString(data.bio) : undefined;
    }

    if (data.avatar !== undefined) {
      updateData.avatar = data.avatar;
    }

    if (data.role) {
      updateData.role = data.role;
    }

    if (data.isActive !== undefined) {
      updateData.isActive = data.isActive;
    }

    const updatedUser = await this.userRepository.update(id, updateData);

    logger.info(`User updated: ${id}`);

    return this.toUserResponse(updatedUser!);
  }

  /**
   * Delete user
   */
  async deleteUser(id: string): Promise<void> {
    const user = await this.userRepository.findById(id);

    if (!user) {
      throw new NotFoundError('User');
    }

    await this.userRepository.delete(id);

    logger.info(`User deleted: ${id}`);
  }

  /**
   * Get user profile
   */
  async getUserProfile(id: string): Promise<UserResponse> {
    return this.getUserById(id);
  }

  /**
   * Update user profile
   */
  async updateUserProfile(id: string, data: UpdateProfileDto): Promise<UserResponse> {
    const user = await this.userRepository.findById(id);

    if (!user) {
      throw new NotFoundError('User');
    }

    const updateData: Partial<User> = {};

    if (data.firstName) {
      updateData.firstName = sanitizeString(data.firstName);
    }

    if (data.lastName) {
      updateData.lastName = sanitizeString(data.lastName);
    }

    if (data.bio !== undefined) {
      updateData.bio = data.bio ? sanitizeString(data.bio) : undefined;
    }

    if (data.avatar !== undefined) {
      updateData.avatar = data.avatar;
    }

    if (data.preferences) {
      updateData.preferences = { ...user.preferences, ...data.preferences };
    }

    const updatedUser = await this.userRepository.update(id, updateData);

    logger.info(`User profile updated: ${id}`);

    return this.toUserResponse(updatedUser!);
  }

  /**
   * Search users
   */
  async searchUsers(params: SearchUsersDto): Promise<PaginatedResponse<UserResponse>> {
    const page = params.page || 1;
    const limit = Math.min(params.limit || config.pagination.defaultPageSize, config.pagination.maxPageSize);

    const [users, total] = await this.userRepository.search({ ...params, page, limit });

    return this.buildPaginatedResponse(users, total, page, limit);
  }

  /**
   * Get users by role
   */
  async getUsersByRole(role: UserRole, page: number = 1, limit: number = config.pagination.defaultPageSize): Promise<PaginatedResponse<UserResponse>> {
    const [users, total] = await this.userRepository.findByRole(role, page, limit);

    return this.buildPaginatedResponse(users, total, page, limit);
  }

  /**
   * Get user statistics
   */
  async getUserStatistics() {
    const totalUsers = await this.userRepository.count();
    const activeUsers = await this.userRepository.countActive();
    const adminCount = await this.userRepository.countByRole(UserRole.ADMIN);
    const moderatorCount = await this.userRepository.countByRole(UserRole.MODERATOR);
    const regularUserCount = await this.userRepository.countByRole(UserRole.USER);
    const recentUsers = await this.userRepository.findRecent(5);

    return {
      total: totalUsers,
      active: activeUsers,
      inactive: totalUsers - activeUsers,
      byRole: {
        admin: adminCount,
        moderator: moderatorCount,
        user: regularUserCount,
      },
      recent: recentUsers.map((user) => this.toUserResponse(user)),
    };
  }

  /**
   * Update last login
   */
  async updateLastLogin(id: string): Promise<void> {
    await this.userRepository.updateLastLogin(id);
  }

  /**
   * Convert User entity to UserResponse
   */
  private toUserResponse(user: User): UserResponse {
    return {
      id: user.id,
      email: user.email,
      firstName: user.firstName,
      lastName: user.lastName,
      role: user.role,
      isActive: user.isActive,
      avatar: user.avatar,
      bio: user.bio,
      preferences: user.preferences,
      createdAt: user.createdAt,
      updatedAt: user.updatedAt,
      lastLoginAt: user.lastLoginAt,
    };
  }

  /**
   * Build paginated response
   */
  private buildPaginatedResponse(
    users: User[],
    total: number,
    page: number,
    limit: number
  ): PaginatedResponse<UserResponse> {
    const totalPages = calculateTotalPages(total, limit);

    return {
      items: users.map((user) => this.toUserResponse(user)),
      pagination: {
        page,
        limit,
        total,
        totalPages,
        hasNext: page < totalPages,
        hasPrev: page > 1,
      },
    };
  }
}

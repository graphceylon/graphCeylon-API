import { Request, Response, NextFunction } from 'express';
import { UserService } from '../services/user.service';
import {
  ApiResponse,
  CreateUserDto,
  UpdateUserDto,
  UpdateProfileDto,
  SearchUsersDto,
  UserRole,
} from '../types';

const userService = new UserService();

export class UserController {
  /**
   * Get current user's profile
   */
  async getCurrentUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const userEmail = req.user?.email;
      
      if (!userEmail) {
        res.status(401).json({
          success: false,
          message: 'User not authenticated',
          timestamp: new Date().toISOString(),
          requestId: req.requestId,
        });
        return;
      }

      const user = await userService.getUserByEmail(userEmail);

      const response: ApiResponse = {
        success: true,
        message: 'Current user retrieved successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get all users
   */
  async getAllUsers(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;

      const result = await userService.getAllUsers(page, limit);

      const response: ApiResponse = {
        success: true,
        message: 'Users retrieved successfully',
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get user by ID
   */
  async getUserById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const user = await userService.getUserById(id);

      const response: ApiResponse = {
        success: true,
        message: 'User retrieved successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Create new user
   */
  async createUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const data: CreateUserDto = req.body;
      const user = await userService.createUser(data);

      const response: ApiResponse = {
        success: true,
        message: 'User created successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(201).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Update user
   */
  async updateUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const data: UpdateUserDto = req.body;

      const user = await userService.updateUser(id, data);

      const response: ApiResponse = {
        success: true,
        message: 'User updated successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Delete user
   */
  async deleteUser(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      await userService.deleteUser(id);

      const response: ApiResponse = {
        success: true,
        message: 'User deleted successfully',
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get user profile
   */
  async getUserProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const user = await userService.getUserProfile(id);

      const response: ApiResponse = {
        success: true,
        message: 'User profile retrieved successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Update user profile
   */
  async updateUserProfile(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { id } = req.params;
      const data: UpdateProfileDto = req.body;

      const user = await userService.updateUserProfile(id, data);

      const response: ApiResponse = {
        success: true,
        message: 'User profile updated successfully',
        data: user,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Search users
   */
  async searchUsers(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const params: SearchUsersDto = {
        query: req.query.query as string,
        role: req.query.role as UserRole,
        isActive: req.query.isActive === 'true' ? true : req.query.isActive === 'false' ? false : undefined,
        page: parseInt(req.query.page as string) || 1,
        limit: parseInt(req.query.limit as string) || 20,
        sortBy: req.query.sortBy as string,
        sortOrder: (req.query.sortOrder as 'ASC' | 'DESC') || 'DESC',
      };

      const result = await userService.searchUsers(params);

      const response: ApiResponse = {
        success: true,
        message: 'Users searched successfully',
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get users by role
   */
  async getUsersByRole(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const { role } = req.params;
      const page = parseInt(req.query.page as string) || 1;
      const limit = parseInt(req.query.limit as string) || 20;

      const result = await userService.getUsersByRole(role as UserRole, page, limit);

      const response: ApiResponse = {
        success: true,
        message: 'Users retrieved successfully',
        data: result,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Get user statistics
   */
  async getUserStatistics(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      const stats = await userService.getUserStatistics();

      const response: ApiResponse = {
        success: true,
        message: 'User statistics retrieved successfully',
        data: stats,
        timestamp: new Date().toISOString(),
        requestId: req.requestId,
      };

      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
  }

  /**
   * Health check
   */
  async healthCheck(_req: Request, res: Response): Promise<void> {
    const response: ApiResponse = {
      success: true,
      message: 'User service is healthy',
      data: {
        service: 'user-service',
        status: 'running',
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
      },
      timestamp: new Date().toISOString(),
    };

    res.status(200).json(response);
  }
}

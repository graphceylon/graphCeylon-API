import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  Index,
} from 'typeorm';
import { UserRole, UserPreferences } from '../types';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ unique: true, length: 255 })
  @Index()
  email: string;

  @Column({ name: 'first_name', length: 100 })
  firstName: string;

  @Column({ name: 'last_name', length: 100 })
  lastName: string;

  @Column({
    type: 'enum',
    enum: UserRole,
    default: UserRole.USER,
  })
  @Index()
  role: UserRole;

  @Column({ name: 'is_active', default: true })
  @Index()
  isActive: boolean;

  @Column({ nullable: true, length: 500 })
  avatar?: string;

  @Column({ type: 'text', nullable: true })
  bio?: string;

  @Column({
    type: 'jsonb',
    default: {},
  })
  preferences: UserPreferences;

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;

  @Column({ name: 'last_login_at', type: 'timestamp', nullable: true })
  lastLoginAt?: Date;

  // Virtual field - full name
  get fullName(): string {
    return `${this.firstName} ${this.lastName}`;
  }
}

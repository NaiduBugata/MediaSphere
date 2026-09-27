import { IsEmail, IsIn, IsOptional, IsString, MinLength } from 'class-validator';

export const WORKSPACE_SECTIONS = ['grievances', 'projects', 'people', 'campaigns'] as const;
export type WorkspaceSection = (typeof WORKSPACE_SECTIONS)[number];

export class RegisterDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(8)
  password: string;

  @IsOptional()
  @IsString()
  name?: string;
}

export class LoginDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(8)
  password: string;
}

export class CreateRecordDto {
  @IsIn(WORKSPACE_SECTIONS)
  section: WorkspaceSection;

  @IsString()
  @MinLength(1)
  title: string;

  @IsOptional()
  @IsString()
  detail?: string;

  @IsOptional()
  @IsString()
  status?: string;
}

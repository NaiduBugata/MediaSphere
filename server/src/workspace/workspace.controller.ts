import { Body, Controller, Get, Headers, Post, Query, UnauthorizedException } from '@nestjs/common';
import { CreateRecordDto, LoginDto, RegisterDto, WORKSPACE_SECTIONS, type WorkspaceSection } from './workspace.dto';
import { WorkspaceService } from './workspace.service';

@Controller('api/workspace')
export class WorkspaceController {
  constructor(private readonly workspace: WorkspaceService) {}

  @Post('register')
  register(@Body() body: RegisterDto) {
    return this.workspace.register(body.email, body.password, body.name);
  }

  @Post('login')
  login(@Body() body: LoginDto) {
    return this.workspace.login(body.email, body.password);
  }

  @Get('me')
  me(@Headers('authorization') authorization?: string) {
    return this.workspace.me(bearer(authorization));
  }

  @Get('summary')
  summary(@Headers('authorization') authorization?: string) {
    this.workspace.verify(bearer(authorization));
    return this.workspace.summary();
  }

  @Get('records')
  records(@Query('section') section: string, @Headers('authorization') authorization?: string) {
    this.workspace.verify(bearer(authorization));
    if (!WORKSPACE_SECTIONS.includes(section as WorkspaceSection)) {
      throw new UnauthorizedException('Unknown section');
    }
    return this.workspace.list(section as WorkspaceSection);
  }

  @Post('records')
  async create(@Body() body: CreateRecordDto, @Headers('authorization') authorization?: string) {
    const user = await this.workspace.me(bearer(authorization));
    return this.workspace.create({
      section: body.section,
      title: body.title,
      detail: body.detail,
      status: body.status,
      createdBy: user.email,
    });
  }
}

function bearer(authorization?: string): string {
  const match = /^Bearer\s+(.+)$/i.exec(authorization || '');
  if (!match) throw new UnauthorizedException('Sign in required');
  return match[1].trim();
}

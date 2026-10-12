import { Body, Controller, Delete, Get, Param, Put } from '@nestjs/common';
import { IsBoolean, IsString, MaxLength } from 'class-validator';
import { AdminOnly } from '../../common/decorators/admin.decorator';
import { AdminDeskService, MP_NAME } from './admin-desk.service';

export class GrantMpDto {
  @IsString()
  @MaxLength(20)
  phone: string;
}

export class DemoDataDto {
  @IsBoolean()
  enabled: boolean;
}

@Controller('api/admin/desk')
@AdminOnly()
export class AdminDeskController {
  constructor(private readonly desk: AdminDeskService) {}

  @Get('mp')
  async mp() {
    return { name: MP_NAME, numbers: await this.desk.mpNumbers() };
  }

  @Put('mp')
  grant(@Body() body: GrantMpDto) {
    return this.desk.grantMp(body.phone);
  }

  @Delete('mp/:id')
  async revoke(@Param('id') id: string) {
    await this.desk.revokeMp(id);
    return { removed: true };
  }

  @Get('demo')
  demo() {
    return this.desk.demo();
  }

  @Put('demo')
  demoSwitch(@Body() body: DemoDataDto) {
    return this.desk.setDemo(body.enabled);
  }
}

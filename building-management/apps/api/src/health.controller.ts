import { Controller, Get } from '@nestjs/common';

@Controller()
export class HealthController {
  @Get('healthz')
  healthz() {
    return {
      status: 'ok',
      service: 'building-management-api',
      ts: new Date().toISOString(),
      version: process.env.SERVICE_VERSION ?? 'dev',
    };
  }
}

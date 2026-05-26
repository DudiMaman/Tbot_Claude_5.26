import { Module } from '@nestjs/common';
import { BulletinController } from './bulletin.controller';
import { BulletinService } from './bulletin.service';

@Module({ controllers: [BulletinController], providers: [BulletinService], exports: [BulletinService] })
export class BulletinModule {}

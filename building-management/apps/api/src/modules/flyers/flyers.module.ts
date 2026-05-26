import { Module } from '@nestjs/common';
import { FlyersController } from './flyers.controller';
import { FlyersService } from './flyers.service';

@Module({ controllers: [FlyersController], providers: [FlyersService] })
export class FlyersModule {}

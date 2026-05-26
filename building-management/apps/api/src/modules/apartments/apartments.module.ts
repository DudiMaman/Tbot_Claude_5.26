import { Module } from '@nestjs/common';
import { ApartmentsController } from './apartments.controller';
import { ApartmentsService } from './apartments.service';
import { AssignmentService } from './assignment.service';

@Module({
  controllers: [ApartmentsController],
  providers: [ApartmentsService, AssignmentService],
  exports: [ApartmentsService, AssignmentService],
})
export class ApartmentsModule {}

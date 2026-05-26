import { PipeTransform, BadRequestException } from '@nestjs/common';
import type { ZodSchema } from 'zod';

export class ZodPipe<T = unknown> implements PipeTransform<unknown, T> {
  constructor(private readonly schema: ZodSchema<T>) {}

  transform(value: unknown): T {
    const result = this.schema.safeParse(value);
    if (!result.success) {
      throw new BadRequestException({
        code: 'validation_error',
        issues: result.error.issues,
      });
    }
    return result.data;
  }
}
